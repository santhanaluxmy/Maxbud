from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from app.core.config import get_settings

hasher = PasswordHash.recommended()

def session_version(db, user_id):
    from sqlalchemy import inspect
    from app.models.access import SessionVersion
    # Existing installations keep working before the additive migration.
    if not inspect(db.connection()).has_table(SessionVersion.__tablename__):
        return 0
    row = db.get(SessionVersion, user_id)
    return row.version if row else 0

def hash_password(password):
    return hasher.hash(password)

def verify_password(password, hashed):
    try:
        return hasher.verify(password, hashed)
    except (UnknownHashError, ValueError, TypeError):
        return False

def make_token(user_id, version=0):
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "ver": version, "iat": now, "exp": now + timedelta(minutes=s.JWT_MINUTES)}, s.JWT_SECRET, algorithm="HS256")

def token_claims(token):
    return jwt.decode(token, get_settings().JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})

def read_token(token):
    return int(token_claims(token)["sub"])
