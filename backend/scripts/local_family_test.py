"""Private local-only Family Pack sandbox. Never opens the configured MySQL DB.

Run from backend: PYTHONPATH=. .venv/bin/python scripts/local_family_test.py --help
The fixed sandbox is created once; there is deliberately no reset/delete command.
"""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from datetime import timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

OWNER_EMAIL = 'family-owner@maxbud.example.com'
MEMBER_EMAILS = [f'roommate{i}@maxbud.example.com' for i in range(1, 6)]
ROOT = Path(__file__).resolve().parents[1] / '.local-family-test'
APPLICATION_ID = 0x4D425446
LABEL = 'MAXBUD LOCAL FAMILY TEST ONLY'


class LocalTestError(ValueError):
    pass


def require_local(settings):
    if settings.ENVIRONMENT not in {'development', 'test'}:
        raise LocalTestError('Local Family Pack tools are forbidden in beta/production. No changes made.')


def load_settings():
    try:
        settings = get_settings()
    except Exception:
        raise LocalTestError('Cannot load backend configuration. Check it privately; no database was opened.') from None
    require_local(settings)
    return settings


class Sandbox:
    def __init__(self, root, settings):
        require_local(settings)
        self.root = Path(root).absolute()
        self.settings = settings
        self.database = self.root / 'sandbox.db'
        self.marker = self.root / 'instance.json'

    def _private(self, path, directory=False):
        if path.is_symlink() or not path.exists():
            raise LocalTestError('Missing or symlinked sandbox path; refusing to open it.')
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise LocalTestError('Sandbox files must belong to you and be private (directory700/files600).')
        if directory != path.is_dir() or (not directory and not stat.S_ISREG(info.st_mode)):
            raise LocalTestError('Unexpected sandbox path type.')

    def manifest(self):
        require_local(self.settings)
        self._private(self.root, directory=True)
        self._private(self.marker)
        try:
            data = json.loads(self.marker.read_text())
        except (ValueError, OSError):
            raise LocalTestError('Invalid sandbox marker; refusing access.') from None
        if (data.get('label') != LABEL or data.get('owner_email') != OWNER_EMAIL
                or data.get('member_emails') != MEMBER_EMAILS
                or not isinstance(data.get('owner_id'), int)
                or not isinstance(data.get('jwt_secret'), str) or len(data['jwt_secret']) < 48):
            raise LocalTestError('This is not the designated synthetic Family Pack sandbox.')
        return data

    def engine(self):
        self.manifest()
        self._private(self.database)
        # SQLite URI mode=rw prevents accidental creation of a replacement DB.
        engine = create_engine(f'sqlite:///file:{self.database}?mode=rw&uri=true',
                               connect_args={'check_same_thread': False}, hide_parameters=True)
        with engine.connect() as connection:
            if connection.execute(text('PRAGMA application_id')).scalar() != APPLICATION_ID:
                engine.dispose()
                raise LocalTestError('Database is not marked as the isolated test instance.')
        return engine

    def initialize(self, password):
        require_local(self.settings)
        from app.schemas.auth import RegisterIn
        from app.core.security import hash_password
        from app.database import Base
        from app.models.user import User, AuthIdentity
        from app.models.family import Subscription
        # Register all current models without starting the FastAPI lifespan.
        import app.main  # noqa: F401
        try:
            RegisterIn(full_name='Local Test Owner', email=OWNER_EMAIL,
                       password=password, confirm_password=password)
        except ValueError:
            raise LocalTestError('Use a new test-only password with 8–128 characters, uppercase, lowercase, number and symbol.') from None
        if self.root.exists() or self.root.is_symlink():
            raise LocalTestError('Sandbox directory already exists. It will never be overwritten or reset.')
        os.umask(0o077)
        self.root.mkdir(mode=0o700, parents=False)
        engine = create_engine(f'sqlite:///{self.database}', hide_parameters=True)
        try:
            Base.metadata.create_all(engine)
            with engine.begin() as connection:
                connection.execute(text(f'PRAGMA application_id = {APPLICATION_ID}'))
            with Session(engine, expire_on_commit=False) as db:
                owner_id = None
                for index, email in enumerate([OWNER_EMAIL, *MEMBER_EMAILS]):
                    user = User(full_name='Local Test Owner' if index == 0 else f'Local Roommate {index}', email=email)
                    db.add(user); db.flush()
                    if index == 0:
                        owner_id = user.id
                    db.add(AuthIdentity(user_id=user.id, provider='password', password_hash=hash_password(password)))
                    db.add(Subscription(user_id=user.id, plan='free', status='active', source='local_test_baseline'))
                db.commit()
            manifest = {'label': LABEL, 'owner_email': OWNER_EMAIL, 'owner_id': owner_id,
                        'member_emails': MEMBER_EMAILS, 'jwt_secret': secrets.token_urlsafe(48)}
            with self.marker.open('x') as file:
                json.dump(manifest, file)
            self.marker.chmod(0o600)
            self.database.chmod(0o600)
        finally:
            engine.dispose()
        return {'owner_email': OWNER_EMAIL, 'members': MEMBER_EMAILS}

    def _owner(self, db, email, confirmation=None, password=None):
        from app.models.user import User, AuthIdentity
        from app.core.security import verify_password
        data = self.manifest()
        if email.strip().lower() != OWNER_EMAIL:
            raise LocalTestError('Only the designated synthetic household owner may receive this grant.')
        user = db.scalar(select(User).where(User.id == data['owner_id'], User.email == OWNER_EMAIL).with_for_update())
        if user is None or not user.is_active or user.role == 'admin':
            raise LocalTestError('Designated active synthetic owner was not found; no changes made.')
        if confirmation is not None or password is not None:
            if confirmation != OWNER_EMAIL:
                raise LocalTestError('Account confirmation did not match; no changes made.')
            identity = db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user.id, AuthIdentity.provider == 'password'))
            if not identity or not verify_password(password, identity.password_hash):
                raise LocalTestError('Test-owner password verification failed; no changes made.')
        return user

    def status(self, email=OWNER_EMAIL):
        from app.models.family import Subscription
        engine = self.engine()
        try:
            with Session(engine) as db:
                user = self._owner(db, email)
                sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
                return {'label': 'TEST ACCESS — NOT A PAYMENT', 'database': str(self.database),
                        'owner_email': user.email, 'plan': sub.plan, 'source': sub.source,
                        'status': sub.status, 'expires_at_utc': sub.expires_at.isoformat() + 'Z' if sub.expires_at else None}
        finally:
            engine.dispose()

    def change(self, action, email, confirmation, password, hours=24):
        require_local(self.settings)
        if confirmation is None or password is None:
            raise LocalTestError('Explicit account confirmation and password are required.')
        if action not in {'grant', 'revoke'}:
            raise LocalTestError('Unknown test-access action.')
        if not isinstance(hours, int) or isinstance(hours, bool) or not 1 <= hours <= 168:
            raise LocalTestError('Temporary access must last between1 and168 hours.')
        from app.models.family import Subscription
        from app.models.platform import PlatformEvent
        from app.models.user import now_utc
        engine = self.engine()
        try:
            with Session(engine, expire_on_commit=False) as db:
                user = self._owner(db, email, confirmation, password)
                sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id).with_for_update())
                baseline = sub is not None and sub.plan == 'free' and sub.source == 'local_test_baseline' and sub.status == 'active'
                managed = sub is not None and sub.plan == 'family_pack' and sub.source == 'test_access'
                if not (baseline or managed):
                    raise LocalTestError('Subscription is not owned by this test mechanism; refusing to overwrite it.')
                if action == 'grant':
                    sub.plan = 'family_pack'; sub.status = 'active'; sub.source = 'test_access'
                    sub.period_started_at = now_utc().replace(microsecond=0)
                    sub.expires_at = sub.period_started_at + timedelta(hours=hours)
                else:
                    sub.plan = 'free'; sub.status = 'active'; sub.source = 'local_test_baseline'
                    sub.period_started_at = None; sub.expires_at = None
                sub.billing_cycle = None; sub.cancel_at_period_end = False
                sub.pending_plan = None; sub.pending_cycle = None
                db.add(PlatformEvent(user_id=user.id, kind='local_test_family_' + action,
                                     target=str(sub.id), details={'label': 'TEST ACCESS', 'payment': False,
                                     'expires_at': sub.expires_at.isoformat() if sub.expires_at else None}))
                db.commit()
        finally:
            engine.dispose()
        return self.status(email)

    def prepare_app(self):
        require_local(self.settings)
        marker = self.manifest()
        engine = self.engine()
        # Process-only settings and an unrelated signing key isolate this server
        # from the normal app. No .env or production setting is written.
        self.settings.JWT_SECRET = marker['jwt_secret']
        self.settings.DEMO_PAYMENTS_ENABLED = False
        self.settings.FAMILY_PACK_MEMBER_LIMIT = 6
        self.settings.GOOGLE_CLIENT_ID = ''
        self.settings.GROQ_API_KEY = ''; self.settings.OPENAI_API_KEY = ''
        self.settings.RECEIPT_STORAGE_DIR = str(self.root / 'receipts')
        self.settings.FRONTEND_ORIGIN = 'http://127.0.0.1:5184'
        import app.database as database
        import app.main as main
        database.engine.dispose()
        database.engine = engine
        database.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        main.engine = engine
        return main.app


def private_terminal():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise LocalTestError('Use a private interactive terminal for --apply; no passwords in arguments, pipes or environment variables.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init', help='Create six NEW synthetic accounts in a new isolated SQLite database')
    init.add_argument('--apply', action='store_true')
    commands.add_parser('status', help='Inspect the designated local test entitlement')
    serve = commands.add_parser('serve', help='Serve only the isolated database on loopback, with its own signing key')
    serve.add_argument('--port', type=int, default=8011)
    for action in ['grant', 'revoke']:
        command = commands.add_parser(action)
        command.add_argument('--email', required=True)
        command.add_argument('--apply', action='store_true')
        if action == 'grant':
            command.add_argument('--hours', type=int, default=24)
    args = parser.parse_args(argv)
    try:
        sandbox = Sandbox(ROOT, load_settings())
        if args.action == 'init':
            if not args.apply:
                print(f'Preview only: create a NEW isolated database at {ROOT}; owner {OWNER_EMAIL} and five synthetic members. Add --apply to confirm. MySQL will not be opened.')
                return
            private_terminal()
            if input('Type CREATE LOCAL TEST DATABASE to continue: ') != 'CREATE LOCAL TEST DATABASE':
                raise LocalTestError('Initialization canceled; no changes made.')
            password = getpass('New test-only password for the six synthetic accounts: ')
            if password != getpass('Confirm test-only password: '):
                raise LocalTestError('Passwords did not match; no changes made.')
            print(json.dumps(sandbox.initialize(password), indent=2))
        elif args.action == 'status':
            print(json.dumps(sandbox.status(), indent=2))
        elif args.action == 'serve':
            if not 1024 <= args.port <= 65535:
                raise LocalTestError('Use a loopback test-server port between1024 and65535.')
            app = sandbox.prepare_app()
            print(f'LOCAL TEST DATABASE ONLY: {sandbox.database}\nTEST ACCESS is not a payment. API: http://127.0.0.1:{args.port}', flush=True)
            import uvicorn
            uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='info')
        else:
            preview = sandbox.status(args.email)
            if not args.apply:
                print(json.dumps(preview, indent=2))
                print(f'Preview only: {args.action}. Add --apply for account confirmation and private password verification. No changes made.')
                return
            private_terminal()
            confirmation = input(f'Type the intended test-owner email ({OWNER_EMAIL}): ')
            password = getpass('Synthetic test-owner password: ')
            print(json.dumps(sandbox.change(args.action, args.email, confirmation, password, getattr(args, 'hours', 24)), indent=2))
    except LocalTestError as error:
        raise SystemExit(str(error)) from None


if __name__ == '__main__':
    main()
