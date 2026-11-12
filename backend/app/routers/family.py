from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import current_user
from app.core.plans import PLAN_LIMITS
from app.core.security import hash_password
from app.database import get_db
from app.models.family import FamilyMembership
from app.models.user import AuthIdentity, User
from app.routers.auth import insert_user
from app.schemas.family import FamilyOut, MemberCreate, MemberOut
from app.services.family import active_users, family_plan, get_family, member_details, overview

router = APIRouter(prefix="/family", tags=["Family"])


@router.get("", response_model=FamilyOut)
def read_family(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return overview(db, get_family(db, user), user)


@router.get("/members", response_model=list[MemberOut])
def list_members(user: User = Depends(current_user), db: Session = Depends(get_db)):
    family = get_family(db, user)
    permitted = active_users(db, family) if family.owner_user_id == user.id else [user]
    return [member_details(member, family) for member in permitted]


@router.post("/members", response_model=MemberOut, status_code=201)
def add_member(data: MemberCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        family = get_family(db, user, owner_only=True, lock=True)
        if len(active_users(db, family, lock=True)) >= PLAN_LIMITS[family_plan(db, family)]["family_members"]:
            raise HTTPException(409, "Family member limit reached for your plan")
        email = str(data.email).strip().lower()
        if len(email) > 254:
            raise HTTPException(422, "Email must be at most 254 characters")
        if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
            raise HTTPException(409, "Email already registered")
        encrypted = hash_password(data.password)
        member = insert_user(db, data.full_name, email, encrypted)
        member.role = "member"
        member.currency = "LKR"
        db.add(AuthIdentity(user_id=member.id, provider="password", password_hash=encrypted))
        db.add(FamilyMembership(family_id=family.id, user_id=member.id, status="active"))
        db.flush()
        result = member_details(member, family)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered or membership conflict") from None
    except Exception:
        db.rollback()
        raise


@router.delete("/members/{member_id}")
def remove_member(member_id: int = Path(gt=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        family = get_family(db, user, owner_only=True, lock=True)
        if member_id == family.owner_user_id:
            raise HTTPException(403, "The family owner cannot remove themselves")
        memberships = db.scalars(select(FamilyMembership).where(
            FamilyMembership.family_id == family.id, FamilyMembership.user_id == member_id,
            FamilyMembership.status == "active").with_for_update()).all()
        if not memberships:
            raise HTTPException(404, "Family member not found")
        for membership in memberships:
            membership.status = "removed"
        db.commit()
        return {"message": "Family membership removed. Personal records are preserved.", "id": member_id}
    except Exception:
        db.rollback()
        raise
