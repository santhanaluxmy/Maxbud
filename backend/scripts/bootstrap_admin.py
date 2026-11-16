"""Private operator CLI. Never a public signup or password-reset endpoint.

Preview: PYTHONPATH=. .venv/bin/python scripts/bootstrap_admin.py --email EMAIL --create
Apply:   add --apply, then enter a new password twice in a private terminal.
Without --create, promotion requires the existing account's current password.
"""
import argparse
from getpass import getpass
import sys
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.user import User, AuthIdentity
from app.models.platform import PlatformEvent
from app.core.security import hash_password
from app.routers.auth import insert_user, password_matches, legacy_password_hash
from app.schemas.auth import RegisterIn


class ProvisionError(ValueError):
    pass


def normalized_email(email):
    try:
        return str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    except ValidationError:
        raise ProvisionError('Enter a valid administrator email.') from None


def provision(db, email, password, *, create=False, name='Platform Administrator'):
    """Stage one audited change; caller controls commit/rollback. Never reset hashes."""
    email=normalized_email(email)
    user=db.scalar(select(User).where(User.email==email).with_for_update().execution_options(populate_existing=True))
    if create:
        if user is not None: raise ProvisionError('Email already exists. Creation cannot overwrite an existing account.')
        try:
            data=RegisterIn(full_name=name,email=email,password=password,confirm_password=password)
            if len(data.full_name)>100: raise ValueError()
        except (ValidationError,ValueError):
            raise ProvisionError('Use a name of 2–100 characters and a password of 8–128 characters with uppercase, lowercase, number and symbol.') from None
        encrypted=hash_password(password)
        user=insert_user(db,data.full_name,email,encrypted)
        user.role='admin';user.onboarding_completed=True
        db.add(AuthIdentity(user_id=user.id,provider='password',password_hash=encrypted))
        mode='created'
    else:
        if user is None or not user.is_active: raise ProvisionError('An existing active account is required, or use --create with a new email.')
        identity=db.scalar(select(AuthIdentity).where(AuthIdentity.user_id==user.id,AuthIdentity.provider=='password'))
        stored=identity.password_hash if identity else legacy_password_hash(db,user.id)
        if not password_matches(password,stored): raise ProvisionError('Current password verification failed. No changes were made.')
        if user.role=='admin': return 'already_admin'
        user.role='admin';mode='promoted'
    db.flush()
    db.add(PlatformEvent(user_id=user.id,kind='operator_admin_bootstrap',target=str(user.id),details={'mode':mode}))
    return mode


def secret(prompt):
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ProvisionError('Use a private interactive terminal; passwords cannot be supplied in arguments, pipes or environment variables.')
    return getpass(prompt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',default='Platform Administrator')
    parser.add_argument('--create',action='store_true',help='Create a new admin using an unused email; never overwrite existing users')
    parser.add_argument('--apply',action='store_true',help='Explicitly authorize the reviewed creation/promotion')
    args=parser.parse_args()
    try:
        email=normalized_email(args.email)
        with SessionLocal() as db:
            existing=db.scalar(select(User).where(User.email==email))
            if args.create and existing is not None: raise ProvisionError('Email already exists; choose a new operator email. No password was changed.')
            if not args.create and (existing is None or not existing.is_active): raise ProvisionError('An existing active account is required, or use --create with a new email.')
            if not args.apply:
                print('Dry run passed. No account or role changed. Add --apply to enter the password securely and authorize this operation.')
                return
            password=secret('New administrator password: ' if args.create else 'Existing account current password: ')
            if args.create and password!=secret('Confirm new password: '): raise ProvisionError('Passwords do not match. No changes were made.')
            mode=provision(db,email,password,create=args.create,name=args.name)
            db.commit()
            print('Administrator '+mode+'. No existing passwords or financial records were changed.')
    except ProvisionError as exc:
        raise SystemExit(str(exc)) from None
    except IntegrityError:
        raise SystemExit('Account conflict; no changes committed. Review the target email and retry.') from None


if __name__=='__main__': main()
