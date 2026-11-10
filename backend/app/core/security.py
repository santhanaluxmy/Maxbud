from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

hasher = PasswordHash.recommended()

def hash_password(password):
    return hasher.hash(password)

def verify_password(password, hashed):
    try:
        return hasher.verify(password, hashed)
    except (ValueError, TypeError):
        return False

def make_token(user_id):
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=s.JWT_MINUTES)}, s.JWT_SECRET, algorithm="HS256")

def read_token(token):
    data = jwt.decode(token, get_settings().JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})
    return int(data["sub"])
