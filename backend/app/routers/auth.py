
from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import current_user
from app.core.security import (
    hash_password,
    make_token,
    verify_password,
)
from app.database import get_db
from app.models.user import AuthIdentity, User
from app.schemas.auth import (
    AuthOut,
    GoogleIn,
    LoginIn,
    RegisterIn,
    UserOut,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def auth_result(user: User) -> dict:
    return {
        "access_token": make_token(user.id),
        "token_type": "bearer",
        "user": user,
        "onboarding_completed": user.onboarding_completed,
    }


def legacy_password_column(db: Session):
    """Check whether the old users password column exists."""
    return next(
        (
            column
            for column in inspect(db.get_bind()).get_columns("users")
            if column["name"] == "hashed_password"
        ),
        None,
    )


def legacy_password_hash(
    db: Session,
    user_id: int,
) -> str | None:
    if legacy_password_column(db) is None:
        return None

    return db.execute(
        text(
            "SELECT hashed_password "
            "FROM users WHERE id = :user_id"
        ),
        {"user_id": user_id},
    ).scalar_one_or_none()


def insert_user(
    db: Session,
    full_name: str,
    email: str,
    password_hash: str | None,
):
    """Support existing and older MaxBud user table formats."""
    old_column = legacy_password_column(db)

    if old_column and not old_column["nullable"]:
        # Old database requires a password hash in users.
        # Google accounts receive an unguessable placeholder hash.
        stored_hash = password_hash or hash_password(
            secrets.token_urlsafe(48)
        )

        result = db.execute(
            text(
                "INSERT INTO users "
                "(full_name, email, role, is_active, "
                "onboarding_completed, onboarding_step, "
                "currency, created_at, hashed_password) "
                "VALUES "
                "(:full_name, :email, 'user', 1, "
                "0, 1, 'LKR', :created_at, :hashed_password)"
            ),
            {
                "full_name": full_name,
                "email": email,
                "created_at": datetime.now(
                    timezone.utc
                ).replace(tzinfo=None),
                "hashed_password": stored_hash,
            },
        )

        return db.get(User, result.lastrowid)

    user = User(
        full_name=full_name,
        email=email,
    )

    db.add(user)
    db.flush()

    return user


def password_matches(
    password: str,
    hashed: str | None,
) -> bool:
    if not hashed:
        return False

    if verify_password(password, hashed):
        return True

    # Support existing bcrypt hashes when bcrypt is installed.
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt

            return bcrypt.checkpw(
                password.encode("utf-8"),
                hashed.encode("utf-8"),
            )
        except (ImportError, ValueError, TypeError):
            return False

    return False


@router.post(
    "/register",
    response_model=AuthOut,
    status_code=201,
)
def register(
    data: RegisterIn,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()

    existing = db.scalar(
        select(User).where(
            func.lower(User.email) == email
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    encrypted = hash_password(data.password)

    try:
        user = insert_user(
            db,
            data.full_name,
            email,
            encrypted,
        )

        db.add(
            AuthIdentity(
                user_id=user.id,
                provider="password",
                password_hash=encrypted,
            )
        )

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    except Exception:
        db.rollback()
        raise

    return auth_result(user)


@router.post(
    "/login",
    response_model=AuthOut,
)
def login(
    data: LoginIn,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()

    invalid = HTTPException(
        status_code=401,
        detail="Invalid email or password",
    )

    user = db.scalar(
        select(User).where(
            func.lower(User.email) == email
        )
    )

    if not user:
        raise invalid

    identity = db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == "password",
        )
    )

    if identity and identity.password_hash:
        # Current MaxBud password authentication.
        if not password_matches(
            data.password,
            identity.password_hash,
        ):
            raise invalid

    else:
        # Older MaxBud account:
        # password may exist in users.hashed_password.
        old_hash = legacy_password_hash(db, user.id)

        if not password_matches(
            data.password,
            old_hash,
        ):
            raise invalid

        # Migrate only after the correct password is verified.
        try:
            if identity is None:
                db.add(
                    AuthIdentity(
                        user_id=user.id,
                        provider="password",
                        password_hash=hash_password(
                            data.password
                        ),
                    )
                )
            else:
                identity.password_hash = hash_password(
                    data.password
                )

            db.commit()

        except IntegrityError:
            db.rollback()

            # A simultaneous request may have migrated the user.
            identity = db.scalar(
                select(AuthIdentity).where(
                    AuthIdentity.user_id == user.id,
                    AuthIdentity.provider == "password",
                )
            )

            if (
                not identity
                or not password_matches(
                    data.password,
                    identity.password_hash,
                )
            ):
                raise invalid

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account disabled",
        )

    return auth_result(user)


@router.post(
    "/google",
    response_model=AuthOut,
)
def google_login(
    data: GoogleIn,
    db: Session = Depends(get_db),
):
    client_id = get_settings().GOOGLE_CLIENT_ID.strip()

    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured",
        )

    try:
        payload = id_token.verify_oauth2_token(
            data.credential,
            Request(),
            client_id,
        )

    except (ValueError, GoogleAuthError):
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token",
        )

    if (
        payload.get("email_verified") is not True
        or not payload.get("sub")
        or not payload.get("email")
    ):
        raise HTTPException(
            status_code=401,
            detail="Google email must be verified",
        )

    subject = str(payload["sub"])

    identity = db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "google",
            AuthIdentity.provider_subject == subject,
        )
    )

    if identity:
        user = db.get(User, identity.user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Account unavailable",
            )

        return auth_result(user)

    email = str(payload["email"]).strip().lower()

    existing = db.scalar(
        select(User).where(
            func.lower(User.email) == email
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "Email already registered. "
                "Sign in using your existing method. "
                "Secure account linking is not enabled."
            ),
        )

    full_name = str(
        payload.get("name") or "Google User"
    ).strip()[:150]

    if len(full_name) < 2:
        full_name = "Google User"

    try:
        user = insert_user(
            db,
            full_name,
            email,
            password_hash=None,
        )

        db.add(
            AuthIdentity(
                user_id=user.id,
                provider="google",
                provider_subject=subject,
            )
        )

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Google account exists; retry",
        )

    except Exception:
        db.rollback()
        raise

    return auth_result(user)


@router.get(
    "/me",
    response_model=UserOut,
)
def me(
    user: User = Depends(current_user),
):
    return user
