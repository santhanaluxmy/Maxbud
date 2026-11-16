import calendar
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.core.plans import PLAN_LIMITS
from app.models.family import Subscription, Family, FamilyMembership
from app.models.user import now_utc


def add_months(value, months):
    year, index = divmod(value.year * 12 + value.month - 1 + months, 12)
    return value.replace(year=year, month=index+1, day=min(value.day,calendar.monthrange(year,index+1)[1]))


def start_trial(db, user):
    now = now_utc().replace(microsecond=0)
    db.add(Subscription(user_id=user.id, plan="trial", status="trialing", source="trial",
                        trial_started_at=now, trial_ends_at=add_months(now,3), expires_at=add_months(now,3)))


def subscription_valid(sub, now=None):
    now = now or now_utc()
    return bool(sub and sub.status in {"active","trialing","canceled"} and
                (sub.status != "canceled" or sub.cancel_at_period_end) and
                (sub.expires_at is None or sub.expires_at > now))


def entitlement(db, user):
    sub = db.scalar(select(Subscription).where(Subscription.user_id==user.id))
    now=now_utc()
    legacy = bool(sub and sub.plan in {"free","premium"} and sub.source is None)
    valid = subscription_valid(sub,now)
    plan = (sub.plan if valid else "read_only") if sub else "legacy_free"
    if legacy:
        plan="read_only" if sub.status in {"past_due","suspended"} else ("premium" if valid and sub.plan=="premium" else "free")
    sponsored_by=None
    memberships=select(FamilyMembership.family_id).where(FamilyMembership.user_id==user.id,FamilyMembership.status=="active")
    families=db.scalars(select(Family).where(Family.id.in_(memberships), Family.is_active.is_(True))).all()
    for family in families:
        sponsor=db.scalar(select(Subscription).where(Subscription.user_id==(family.sponsor_user_id or family.owner_user_id)))
        if sponsor and sponsor.plan=="family_pack" and subscription_valid(sponsor,now):
            plan="family_pack" if family.owner_user_id==user.id else "premium_individual"
            sponsored_by=sponsor.user_id
            break
    if plan=="legacy_free": plan="free"
    status=(sub.status if valid or legacy or sub.status in {"past_due","suspended"} else "expired") if sub else "legacy"
    result={"plan":plan,"billing_plan":sub.plan if sub else "free","status":status,
            "can_edit":plan!="read_only","household_allowed":sponsored_by is not None or plan=="family_pack",
            "sponsored_by":sponsored_by,"source":sub.source if sub else "legacy",
            "trial_started_at":sub.trial_started_at if sub else None,"trial_ends_at":sub.trial_ends_at if sub else None,
            "expires_at":sub.expires_at if sub else None,"cancel_at_period_end":bool(sub and sub.cancel_at_period_end),
            "pending_plan":sub.pending_plan if sub else None,"limits":PLAN_LIMITS[plan]}
    result["billing_status"]=status
    if sponsored_by is not None: result["status"]="active"
    remaining=(sub.trial_ends_at-now) if sub and sub.trial_ends_at and sub.trial_ends_at>now else timedelta(0)
    result["trial_days_remaining"]=remaining.days + int(bool(remaining.seconds or remaining.microseconds))
    return result


def require_edit(db,user):
    if not entitlement(db,user)["can_edit"]:
        raise HTTPException(403,"Your access period has ended. History and export remain available; upgrade to add or edit financial records.")


def family_access(db,family,write=False):
    statement = select(Subscription).where(Subscription.user_id == (family.sponsor_user_id or family.owner_user_id))
    if write:
        # Recheck the committed subscription after the household lock, rather
        # than using an earlier repeatable-read snapshot or cached ORM object.
        statement = statement.with_for_update().execution_options(populate_existing=True)
    sub = db.scalar(statement)
    valid=bool(sub and sub.plan=="family_pack" and subscription_valid(sub))
    if write and not valid:
        raise HTTPException(403,"An active Family Pack sponsor is required for shared editing. Household history is preserved.")
    if write:
        from app.services.family import active_users
        if len(active_users(db, family, lock=True, include_inactive=True)) > PLAN_LIMITS['family_pack']['family_members']:
            raise HTTPException(409, 'Family Pack supports one owner and up to five other people. Remove extra memberships to resume shared editing; history is preserved.')
    return False, valid


def family_capacity(db,family):
    # Callers enforce subscription access before adding/accepting members.
    # Reporting the limit must remain possible for oversized legacy households.
    return PLAN_LIMITS['family_pack']['family_members']


def catalog():
    settings=get_settings()
    try:
        raw=json.loads(settings.PLAN_PRICES_JSON)
        prices={plan:{cycle:(str(Decimal(str(raw.get(plan,{}).get(cycle))).quantize(Decimal('.01'))) if raw.get(plan,{}).get(cycle) is not None else None) for cycle in ['monthly','yearly']} for plan in ['premium_individual','family_pack']}
        if any(Decimal(v)<0 or not Decimal(v).is_finite() for p in prices.values() for v in p.values() if v is not None): raise ValueError()
    except (ValueError,InvalidOperation,TypeError,AttributeError):
        raise HTTPException(503,"Plan price configuration is invalid")
    return {"currency":"LKR","trial_months":3,"demo_enabled":settings.DEMO_PAYMENTS_ENABLED and settings.ENVIRONMENT!="production",
            "plans":[{"id":"trial","name":"Free Trial","duration":"3 calendar months","prices":{"monthly":"0.00"},"limits":PLAN_LIMITS['trial']},
                     *[{"id":p,"name":"Premium Individual" if p=='premium_individual' else "Family Pack","prices":prices[p],"limits":PLAN_LIMITS[p]} for p in prices]]}
