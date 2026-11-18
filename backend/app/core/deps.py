
import jwt

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.core.security import token_claims, session_version


bearer = HTTPBearer()


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    try:
        claims = token_claims(credentials.credentials)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user = db.get(User, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Inactive or unknown user",
        )

    if claims.get("ver", 0) != session_version(db, user_id):
        raise HTTPException(401, "Session ended. Please sign in again.")
    return user


def writable_user(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.services.subscriptions import require_edit
    require_edit(db, user)
    return user
