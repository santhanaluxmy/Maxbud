from datetime import timedelta
import hashlib
import hmac
import secrets
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import func, select, update, inspect
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import hash_password
from app.database import get_db
from app.models.access import PasswordRecovery, SessionVersion
from app.models.user import User, AuthIdentity, now_utc
from app.schemas.auth import RegisterIn
from app.services import recovery as delivery

router = APIRouter(prefix='/auth/recovery', tags=['Password recovery'])


def digest(value):
    return hmac.new(get_settings().JWT_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


class Email(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr


class Verify(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: str = Field(min_length=40, max_length=64)
    code: str = Field(pattern=r'^\d{6}$')


class Reset(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: str = Field(min_length=40, max_length=64)
    reset_token: str = Field(min_length=40, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode='after')
    def strong_password(self):
        RegisterIn(full_name='Recovery User', email='recovery@example.com', password=self.password, confirm_password=self.confirm_password)
        return self


def dispatch(email, code):
    try:
        delivery.send_code(email, code)
    except Exception:
        # No account enumeration or sensitive SMTP exception/message logging.
        # Failed delivery is not represented as successful delivery to the user.
        logging.getLogger(__name__).warning('Recovery email delivery failed; check SMTP connectivity and provider configuration privately.')


def ready(db):
    if not inspect(db.connection()).has_table('password_recoveries') or not inspect(db.connection()).has_table('auth_session_versions'):
        raise HTTPException(503, 'Password recovery setup requires the additive access migration.')


@router.post('/request')
def request(data: Email, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ready(db)
    if not delivery.configured():
        raise HTTPException(503, 'Password recovery email delivery is not configured. Contact support.')
    email = str(data.email).strip().lower()
    now = now_utc()
    key, code = secrets.token_urlsafe(32), f'{secrets.randbelow(1000000):06d}'
    fingerprint = digest(email)
    # Durable per-identity request limit, plus the normal per-IP auth limit.
    user = db.scalar(select(User).where(func.lower(User.email) == email, User.is_active.is_(True)).with_for_update())
    recent = db.scalar(select(func.count()).select_from(PasswordRecovery).where(PasswordRecovery.email_hash == fingerprint, PasswordRecovery.created_at > now - timedelta(minutes=15)))
    if recent < 3:
        identity = db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user.id, AuthIdentity.provider == 'password')) if user else None
        from app.routers.auth import legacy_password_hash
        eligible = bool(identity and identity.password_hash) or bool(user and legacy_password_hash(db, user.id))
        db.add(PasswordRecovery(id=key, user_id=user.id if eligible else None, email_hash=fingerprint,
                                code_hash=digest(key + ':' + code), expires_at=now + timedelta(minutes=10)))
        db.commit()
        if eligible:
            tasks.add_task(dispatch, email, code)
    return {'challenge_id': key, 'message': 'If this account is eligible, a recovery code will arrive by email. Delivery may take a few minutes.'}


@router.post('/verify')
def verify(data: Verify, db: Session = Depends(get_db)):
    ready(db)
    row = db.scalar(select(PasswordRecovery).where(PasswordRecovery.id == data.challenge_id).with_for_update().execution_options(populate_existing=True))
    if not row or row.used_at or row.verified_at or row.expires_at <= now_utc() or row.attempts >= 5:
        raise HTTPException(400, 'Recovery code is invalid or expired. Request a new code.')
    row.attempts += 1
    if not row.user_id or not hmac.compare_digest(row.code_hash, digest(row.id + ':' + data.code)):
        db.commit()
        raise HTTPException(400, 'Recovery code is invalid or expired. Request a new code.')
    proof = secrets.token_urlsafe(32)
    row.proof_hash = digest(proof)
    row.verified_at = now_utc()
    db.commit()
    return {'reset_token': proof}


@router.post('/reset')
def reset(data: Reset, db: Session = Depends(get_db)):
    ready(db)
    initial = db.get(PasswordRecovery, data.challenge_id)
    if not initial or not initial.user_id:
        raise HTTPException(400, 'Recovery request is invalid or expired.')
    user = db.scalar(select(User).where(User.id == initial.user_id).with_for_update().execution_options(populate_existing=True))
    row = db.scalar(select(PasswordRecovery).where(PasswordRecovery.id == data.challenge_id).with_for_update().execution_options(populate_existing=True))
    if not user or not user.is_active or row.used_at or not row.verified_at or row.expires_at <= now_utc() or not row.proof_hash or not hmac.compare_digest(row.proof_hash, digest(data.reset_token)):
        raise HTTPException(400, 'Recovery request is invalid or expired.')
    identity = db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user.id, AuthIdentity.provider == 'password').with_for_update())
    if not identity:
        from app.routers.auth import legacy_password_hash
        if not legacy_password_hash(db, user.id):
            raise HTTPException(400, 'Recovery request is invalid or expired.')
        identity = AuthIdentity(user_id=user.id, provider='password')
        db.add(identity)
    identity.password_hash = hash_password(data.password)
    # Invalidate every old recovery request and existing JWT for this account.
    db.execute(update(PasswordRecovery).where(PasswordRecovery.user_id == user.id).values(used_at=now_utc()))
    version = db.get(SessionVersion, user.id)
    if version:
        version.version += 1
    else:
        db.add(SessionVersion(user_id=user.id, version=1))
    db.commit()
    return {'message': 'Password updated. Sign in again with your new password.'}
