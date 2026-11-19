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
    if sub and sub.source in {'demo', 'stripe_test'} and get_settings().ENVIRONMENT == 'production':
        return False
    if sub and sub.source == 'stripe_test' and sub.expires_at is None:
        return False
    if sub and sub.source == 'test_access':
        if get_settings().ENVIRONMENT not in {'development', 'test'} or sub.plan != 'family_pack' or sub.expires_at is None:
            return False
    return bool(sub and sub.status in {"active","trialing","canceled"} and
                (sub.status != "canceled" or sub.cancel_at_period_end) and
                (sub.expires_at is None or sub.expires_at > now))


def entitlement(db, user):
    sub = db.scalar(select(Subscription).where(Subscription.user_id==user.id))
    now=now_utc()
    legacy = bool(sub and sub.plan in {"free","premium"} and sub.source is None)
    valid = subscription_valid(sub,now)
    plan = (sub.plan if valid else "read_only") if sub else "legacy_free"
    # A purchase never resets the original calendar trial. If paid access ends
    # while that original trial remains, its personal allowance still applies.
    trial_remaining = bool(sub and sub.source == 'stripe_test' and not valid and sub.trial_ends_at and sub.trial_ends_at > now)
    if trial_remaining:
        plan = 'trial'
    if legacy:
        plan="read_only" if sub.status in {"past_due","suspended"} else ("premium" if valid and sub.plan=="premium" else "free")
    sponsored_by=None
    test_access = bool(sub and sub.source == 'test_access')
    test_access_expires = sub.expires_at if test_access else None
    memberships=select(FamilyMembership.family_id).where(FamilyMembership.user_id==user.id,FamilyMembership.status=="active")
    families=db.scalars(select(Family).where(Family.id.in_(memberships), Family.is_active.is_(True))).all()
    for family in families:
        sponsor=db.scalar(select(Subscription).where(Subscription.user_id==(family.sponsor_user_id or family.owner_user_id)))
        if sponsor and sponsor.plan=="family_pack" and subscription_valid(sponsor,now):
            sponsored_by=sponsor.user_id
            if sponsor.source == 'test_access':
                test_access = True
                test_access_expires = sponsor.expires_at
            break
    if plan=="legacy_free": plan="free"
    status=(sub.status if valid or legacy or sub.status in {"past_due","suspended"} else "expired") if sub else "legacy"
    billing_status = status
    if trial_remaining:
        status = 'trialing'
    result={"plan":plan,"billing_plan":sub.plan if sub else "free","status":status,
            "can_edit":plan!="read_only","household_allowed":sponsored_by is not None or plan=="family_pack",
            "sponsored_by":sponsored_by,"source":sub.source if sub else "legacy",
            "billing_cycle":sub.billing_cycle if sub else None,"period_started_at":sub.period_started_at if sub else None,
            "trial_started_at":sub.trial_started_at if sub else None,"trial_ends_at":sub.trial_ends_at if sub else None,
            "expires_at":sub.expires_at if sub else None,"cancel_at_period_end":bool(sub and sub.cancel_at_period_end),
            "pending_plan":sub.pending_plan if sub else None,"limits":PLAN_LIMITS[plan]}
    result["billing_status"]=billing_status
    result['test_access'] = test_access
    result['test_access_expires_at'] = test_access_expires
    # Membership never changes the personal subscription status or limits.
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
            raise HTTPException(409, 'Family Pack supports one owner and up to four other people (five total). Remove extra memberships to resume shared editing; history is preserved.')
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
    prices["premium_individual"]["monthly"] = "650.00"
    prices["family_pack"]["monthly"] = "900.00"
    stripe_ready = settings.ENVIRONMENT in {'development', 'test', 'beta'} and settings.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")) and bool(settings.STRIPE_WEBHOOK_SECRET)
    return {"stripe_test_enabled":stripe_ready,"available_billing_cycles":['monthly'],"checkout_available":{p: stripe_ready and getattr(settings, 'STRIPE_PRICE_' + ('PREMIUM' if p == 'premium_individual' else 'FAMILY') + '_MONTHLY').startswith('price_') for p in prices},"currency":"LKR","trial_months":3,"demo_enabled":settings.DEMO_PAYMENTS_ENABLED and settings.ENVIRONMENT!="production",
            "plans":[{"id":"trial","name":"Free Trial","duration":"3 calendar months","prices":{"monthly":"0.00"},"limits":PLAN_LIMITS['trial']},
                     *[{"id":p,"name":"Premium Individual" if p=='premium_individual' else "Family Pack","prices":prices[p],"limits":PLAN_LIMITS[p]} for p in prices]]}
