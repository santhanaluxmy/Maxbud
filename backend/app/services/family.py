from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.core.plans import PLAN_LIMITS
from app.models.family import Family, FamilyMembership, Subscription
from app.models.user import User


def create_owner_family(db: Session, user: User) -> Family:
    """Called only for new registrations or explicitly approved legacy backfill."""
    family = Family(owner_user_id=user.id, name=f"{user.full_name}'s Family"[:100])
    db.add(family)
    db.flush()
    db.add(FamilyMembership(family_id=family.id, user_id=user.id, status="active"))
    db.add(Subscription(user_id=user.id, plan="free", status="active"))
    user.role = "owner"
    return family


def get_family(db: Session, user: User, *, owner_only=False, lock=False) -> Family:
    # Membership, rather than the JWT's age or client role, controls access.
    memberships = select(FamilyMembership.family_id).where(
        FamilyMembership.user_id == user.id, FamilyMembership.status == "active"
    )
    statement = select(Family).where(Family.is_active.is_(True), or_(Family.owner_user_id == user.id, Family.id.in_(memberships)))
    if owner_only:
        statement = statement.where(Family.owner_user_id == user.id)
    if lock:
        statement = statement.with_for_update()
    families = db.scalars(statement.execution_options(populate_existing=True)).all()
    if not families:
        raise HTTPException(403 if owner_only else 404,
                            "Family owner access required" if owner_only else
                            "No active family membership. Legacy accounts require the documented family backfill.")
    if len(families) != 1:
        raise HTTPException(409, "Multiple family relationships require administrator review")
    return families[0]


def active_users(db: Session, family: Family, *, lock=False, include_inactive=False) -> list[User]:
    memberships = select(FamilyMembership.user_id).where(
        FamilyMembership.family_id == family.id, FamilyMembership.status == "active"
    )
    if lock:
        memberships = memberships.with_for_update()
    statement = select(User).where(
        or_(User.id == family.owner_user_id, User.id.in_(memberships))).order_by(User.id)
    if not include_inactive:
        statement = statement.where(User.is_active.is_(True))
    # A current read after the family row lock avoids stale MySQL RR snapshots.
    if lock:
        statement = statement.with_for_update()
    return list(db.scalars(statement.execution_options(populate_existing=True)).all())


def family_plan(db: Session, family: Family) -> str:
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == (family.sponsor_user_id or family.owner_user_id)))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if subscription and subscription.plan == "family_pack":
        from app.services.subscriptions import subscription_valid
        return "family_pack" if subscription_valid(subscription) else "read_only"
    if subscription and subscription.source is not None:
        return "read_only"
    if (subscription and subscription.plan.lower() == "premium" and subscription.status.lower() == "active"
            and (subscription.expires_at is None or subscription.expires_at > now)):
        return "premium"
    return "free"


def overview(db: Session, family: Family, user: User) -> dict:
    from app.services.subscriptions import family_capacity
    plan = family_plan(db, family)
    total = len(active_users(db, family, include_inactive=True))
    maximum = family_capacity(db, family) if plan in {"free","premium","family_pack"} else 0
    owner = db.get(User, family.owner_user_id)
    from app.services.subscriptions import family_access
    legacy, sponsored = family_access(db,family)
    membership=db.scalar(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id,FamilyMembership.status=='active'))
    is_owner=family.owner_user_id==user.id
    from app.models.platform import FamilyInvitation
    pending=len(db.scalars(select(FamilyInvitation.id).where(FamilyInvitation.family_id==family.id,FamilyInvitation.status=='pending',FamilyInvitation.expires_at>datetime.now(timezone.utc).replace(tzinfo=None))).all())
    return {"can_view_shared":is_owner or bool(membership and membership.can_view_shared),
            "can_add_shared":is_owner or bool(membership and membership.can_add_shared),
            "can_edit_shared":legacy or sponsored,"legacy_member_creation":legacy,
            "id": family.id, "name": family.name, "plan": plan, "currency": "LKR",
            "owner_name": owner.full_name, "owner_id": owner.id,
            "role": "owner" if user.id == owner.id else "member",
            "total_active_members": total, "max_members": maximum,
            "reserved_slots":pending,"available_slots": max(0, maximum - total - pending)}


def member_details(user: User, family: Family) -> dict:
    # Membership table has no joined date; do not substitute account creation.
    return {"id": user.id, "full_name": user.full_name, "email": user.email,
            "role": "owner" if user.id == family.owner_user_id else "member",
            "is_active": user.is_active, "joined_at": None}
