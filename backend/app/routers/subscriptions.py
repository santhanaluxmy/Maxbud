"""Demo-only checkout adapter around server-owned subscription periods."""
from datetime import timedelta
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.deps import current_user
from app.database import get_db
from app.models.family import Subscription
from app.models.platform import DemoCheckout, PlatformEvent
from app.models.user import User, now_utc
from app.services.subscriptions import add_months, catalog, entitlement

router=APIRouter(prefix='/subscriptions',tags=['Subscriptions'])


def demo_only():
    settings=get_settings()
    if not settings.DEMO_PAYMENTS_ENABLED or settings.ENVIRONMENT=='production':
        raise HTTPException(403,'Demo checkout is disabled. No subscription was activated.')


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan: Literal['premium_individual','family_pack']
    billing_cycle: Literal['monthly','yearly']
    request_id: str=Field(min_length=1,max_length=36)


def checkout_out(row):
    return {'id':row.id,'plan':row.plan,'billing_cycle':row.billing_cycle,'amount':str(row.amount) if row.amount is not None else None,'currency':row.currency,'status':row.status,'expires_at':row.expires_at}


@router.get('/plans')
def plans(): return catalog()


@router.get('')
def current(user: User=Depends(current_user),db:Session=Depends(get_db)):
    from sqlalchemy import inspect
    from app.models.access import StripeAccount
    account = db.get(StripeAccount,user.id) if inspect(db.connection()).has_table('stripe_test_accounts') else None
    portal = False
    if account and account.subscription_id:
        from app.routers.billing import validate_portal_configuration
        try:
            validate_portal_configuration()
            portal = True
        except HTTPException:
            pass
    return {**entitlement(db,user),'catalog':catalog(),'billing_portal_available':portal,
            'stripe_subscription_exists':bool(account and account.subscription_id),
            'checkout_pending':bool(account and account.checkout_id and not account.subscription_id)}


@router.post('/checkout',status_code=201)
def checkout(data:Selection,user:User=Depends(current_user),db:Session=Depends(get_db)):
    demo_only()
    if data.billing_cycle != 'monthly':
        raise HTTPException(422, 'Only monthly subscriptions are available.')
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    previous=db.scalar(select(DemoCheckout).where(DemoCheckout.user_id==user.id,DemoCheckout.request_id==data.request_id).with_for_update())
    if previous:
        if previous.plan!=data.plan or previous.billing_cycle!=data.billing_cycle: raise HTTPException(409,'Checkout request already used for another selection')
        return checkout_out(previous)
    offer=next(plan for plan in catalog()['plans'] if plan['id']==data.plan)
    row=DemoCheckout(id=str(uuid4()),user_id=user.id,plan=data.plan,billing_cycle=data.billing_cycle,
                     amount=offer['prices'][data.billing_cycle],request_id=data.request_id,expires_at=now_utc().replace(microsecond=0)+timedelta(minutes=15))
    db.add(row);db.commit()
    return checkout_out(row)


class Outcome(BaseModel):
    model_config=ConfigDict(extra='forbid')
    outcome:Literal['success','failure']


@router.post('/checkout/{key}/simulate')
def simulate(key:str,data:Outcome,user:User=Depends(current_user),db:Session=Depends(get_db)):
    demo_only()
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    row=db.scalar(select(DemoCheckout).where(DemoCheckout.id==key,DemoCheckout.user_id==user.id).with_for_update())
    if row is None: raise HTTPException(404,'Checkout session not found')
    if row.status!='pending':
        return {'checkout_status':row.status,'subscription':entitlement(db,user),'revenue_type':'SIMULATED / DEMO REVENUE'}
    if row.expires_at<=now_utc().replace(microsecond=0): raise HTTPException(409,'Demo checkout expired; create a new session')
    row.completed_at=now_utc().replace(microsecond=0);row.status='succeeded' if data.outcome=='success' else 'failed'
    if data.outcome=='success':
        sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id).with_for_update().execution_options(populate_existing=True))
        if sub is None:
            sub=Subscription(user_id=user.id,plan=row.plan,status='active');db.add(sub)
        # Same-plan renewal extends remaining time; upgrades start now.
        start=max(now_utc().replace(microsecond=0),sub.expires_at) if sub.plan==row.plan and sub.expires_at else now_utc().replace(microsecond=0)
        sub.plan=row.plan;sub.status='active';sub.source='demo';sub.billing_cycle=row.billing_cycle
        sub.period_started_at=now_utc().replace(microsecond=0);sub.expires_at=add_months(start,1 if row.billing_cycle=='monthly' else 12)
        sub.cancel_at_period_end=False;sub.pending_plan=None;sub.pending_cycle=None
    db.add(PlatformEvent(user_id=user.id,kind='demo_payment_'+row.status,target=row.id,details={'plan':row.plan,'cycle':row.billing_cycle,'revenue_type':'SIMULATED / DEMO REVENUE'}))
    db.commit()
    return {'checkout_status':row.status,'subscription':entitlement(db,user),'revenue_type':'SIMULATED / DEMO REVENUE'}


@router.post('/cancel')
def cancel(user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id).with_for_update())
    if sub is None or sub.source!='demo': raise HTTPException(409,'Only your own demo subscription can be canceled here')
    sub.cancel_at_period_end=True;sub.status='canceled'
    db.add(PlatformEvent(user_id=user.id,kind='subscription_cancel_scheduled',target=str(sub.id),details={}))
    db.commit();return entitlement(db,user)


class Change(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan:Literal['premium_individual','family_pack']
    billing_cycle:Literal['monthly','yearly']


@router.post('/schedule')
def schedule(data:Change,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if data.billing_cycle != 'monthly':
        raise HTTPException(422, 'Only monthly subscriptions are available.')
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id).with_for_update())
    if sub is None or sub.source!='demo': raise HTTPException(409,'No own demo subscription to change')
    sub.pending_plan=data.plan;sub.pending_cycle=data.billing_cycle
    db.commit()
    return {**entitlement(db,user),'message':'Selection saved for the next checkout. Existing access lasts until period end; renewal requires a new successful demo checkout.'}


@router.post('/resume')
def resume(user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id).with_for_update())
    if not sub or sub.source!='demo' or not sub.expires_at or sub.expires_at<=now_utc():
        raise HTTPException(409,'No current demo period can be resumed')
    sub.cancel_at_period_end=False;sub.status='active'
    db.commit();return entitlement(db,user)
