"""Platform administration exposes metadata and audit counts, never private finance."""
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.deps import current_user
from app.database import get_db
from app.models.user import User, now_utc
from app.models.family import Subscription
from app.models.ai import AIUsage, AdvisorMessage
from app.models.platform import DemoCheckout, PlatformEvent
from app.schemas.auth import UserOut
from app.services.subscriptions import entitlement, subscription_valid, catalog

router=APIRouter(prefix='/admin',tags=['Admin'])


def admin(user:User=Depends(current_user)):
    if user.role!='admin': raise HTTPException(403,'Platform administrator access required')
    return user


@router.get('/users')
def users(offset:int=Query(0,ge=0),q:str=Query('',max_length=100),status:Literal['active','suspended']|None=None,
          plan:str|None=None,billing_cycle:Literal['monthly','yearly']|None=None,user:User=Depends(admin),db:Session=Depends(get_db)):
    statement=select(User)
    if q.strip(): statement=statement.where(User.full_name.contains(q.strip(),autoescape=True)|User.email.contains(q.strip(),autoescape=True))
    if status: statement=statement.where(User.is_active.is_(status=='active'))
    if plan or billing_cycle: statement=statement.outerjoin(Subscription,Subscription.user_id==User.id)
    if plan: statement=statement.where((Subscription.plan==plan)|(Subscription.id.is_(None)) if plan=='free' else Subscription.plan==plan)
    if billing_cycle: statement=statement.where(Subscription.billing_cycle==billing_cycle)
    result=[]
    for row in db.scalars(statement.order_by(User.id).offset(offset).limit(100)):
        rights=entitlement(db,row)
        result.append({'id':row.id,'full_name':row.full_name,'email':row.email,'role':row.role,'is_active':row.is_active,'created_at':row.created_at,
                       'plan':rights['plan'],'billing_plan':rights['billing_plan'],'billing_cycle':db.scalar(select(Subscription.billing_cycle).where(Subscription.user_id==row.id)),'subscription_status':rights['status'],'source':rights['source'],'sponsored':rights['sponsored_by'] is not None})
    return result


@router.get('/overview')
def overview(user:User=Depends(admin),db:Session=Depends(get_db)):
    people=db.scalars(select(User)).all();subs=db.scalars(select(Subscription)).all();now=now_utc()
    counts={key:0 for key in ['trial','premium_individual','family_pack','free','premium','read_only']}
    for person in people: counts[entitlement(db,person)['plan']]+=1
    events=db.scalar(select(func.count(DemoCheckout.id)))
    simulated=db.scalar(select(func.coalesce(func.sum(DemoCheckout.amount),0)).where(DemoCheckout.status=='succeeded'))
    trends=db.execute(select(func.date(User.created_at),func.count(User.id)).where(User.created_at>=now-timedelta(days=30)).group_by(func.date(User.created_at)).order_by(func.date(User.created_at))).all()
    breakdown=[{'plan':plan,'billing_cycle':cycle,'subscriptions':sum(s.plan==plan and s.billing_cycle==cycle and subscription_valid(s) for s in subs)} for plan in ['trial','premium_individual','family_pack'] for cycle in ([None] if plan=='trial' else ['monthly','yearly'])]
    return {'subscription_breakdown':breakdown,'total_users':len(people),'active_users':sum(p.is_active for p in people),'trial_users':counts['trial'],
            'premium_individual_users':counts['premium_individual'],'family_pack_subscribers':sum(s.plan=='family_pack' and subscription_valid(s) for s in subs),
            'premium_users':counts['premium']+counts['premium_individual']+counts['family_pack'],'free_users':counts['free'],
            'premium_subscriptions':sum(s.plan in {'premium','premium_individual','family_pack'} and subscription_valid(s) for s in subs),
            'active_subscriptions':sum(subscription_valid(s) for s in subs),'expired_subscriptions':sum(s.status=='expired' or (s.expires_at is not None and s.expires_at<=now) for s in subs),
            'demo_subscription_events':events,'simulated_revenue_lkr':str(simulated),'revenue_type':'SIMULATED / DEMO REVENUE','verified_real_revenue_lkr':'0.00',
            'receipt_scans':db.scalar(select(func.count(AIUsage.id))),'advisor_messages':db.scalar(select(func.count(AdvisorMessage.id))),
            'failed_ai_requests':db.scalar(select(func.count(PlatformEvent.id)).where(PlatformEvent.kind=='ai_failure')),
            'registration_trends':[{'date':str(day),'users':count} for day,count in trends],
            'revenue_note':'Demo checkout events are simulated; they are not verified real revenue.'}


@router.get('/subscriptions')
def subscriptions(offset:int=Query(0,ge=0),plan:str|None=None,billing_cycle:Literal['monthly','yearly']|None=None,user:User=Depends(admin),db:Session=Depends(get_db)):
    statement=select(Subscription)
    if plan: statement=statement.where(Subscription.plan==plan)
    if billing_cycle: statement=statement.where(Subscription.billing_cycle==billing_cycle)
    return [{'id':s.id,'user_id':s.user_id,'plan':s.plan,'status':'expired' if s.expires_at and s.expires_at<=now_utc() else s.status,
             'source':s.source or 'legacy','billing_cycle':s.billing_cycle,'expires_at':s.expires_at,'cancel_at_period_end':s.cancel_at_period_end} for s in db.scalars(statement.order_by(Subscription.id.desc()).offset(offset).limit(100))]


class AccountStatus(BaseModel):
    model_config=ConfigDict(extra='forbid')
    is_active:bool


@router.patch('/users/{key}',response_model=UserOut)
def account_status(key:int,data:AccountStatus,user:User=Depends(admin),db:Session=Depends(get_db)):
    target=db.scalar(select(User).where(User.id==key).with_for_update())
    if target is None: raise HTTPException(404,'User not found')
    if target.id==user.id or target.role=='admin': raise HTTPException(409,'Administrator accounts require separate recovery review')
    target.is_active=data.is_active
    db.add(PlatformEvent(user_id=user.id,kind='admin_user_reactivated' if data.is_active else 'admin_user_suspended',target=str(key),details={}))
    db.commit();return target


class SubscriptionStatus(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status:Literal['past_due','suspended','active']


@router.patch('/subscriptions/{key}')
def subscription_status(key:int,data:SubscriptionStatus,user:User=Depends(admin),db:Session=Depends(get_db)):
    sub=db.scalar(select(Subscription).where(Subscription.id==key).with_for_update())
    if sub is None: raise HTTPException(404,'Subscription not found')
    if data.status=='active' and (sub.expires_at is None or sub.expires_at<=now_utc() or sub.source not in {'demo','trial'}):
        raise HTTPException(409,'Reactivation requires an existing unexpired demo/trial period; this action cannot grant a paid period')
    sub.status=data.status
    db.add(PlatformEvent(user_id=user.id,kind='admin_subscription_status',target=str(key),details={'status':data.status}))
    db.commit();return {'id':sub.id,'status':sub.status}


@router.get('/billing')
def billing(offset:int=Query(0,ge=0),user:User=Depends(admin),db:Session=Depends(get_db)):
    return {'revenue_type':'SIMULATED / DEMO REVENUE','events':[{'id':r.id,'user_id':r.user_id,'plan':r.plan,'billing_cycle':r.billing_cycle,'amount':str(r.amount) if r.amount is not None else None,'status':r.status,'created_at':r.created_at} for r in db.scalars(select(DemoCheckout).order_by(DemoCheckout.created_at.desc(),DemoCheckout.id).offset(offset).limit(100))]}


@router.get('/activity')
def activity(offset:int=Query(0,ge=0),user:User=Depends(admin),db:Session=Depends(get_db)):
    return [{'id':r.id,'actor_id':r.user_id,'kind':r.kind,'target':r.target,'details':r.details,'created_at':r.created_at} for r in db.scalars(select(PlatformEvent).order_by(PlatformEvent.id.desc()).offset(offset).limit(100))]


@router.get('/ai-usage')
def ai_usage(user:User=Depends(admin),db:Session=Depends(get_db)):
    scans=dict(db.execute(select(AIUsage.user_id,func.count(AIUsage.id)).group_by(AIUsage.user_id)).all())
    chats=dict(db.execute(select(AdvisorMessage.user_id,func.count(AdvisorMessage.id)).group_by(AdvisorMessage.user_id)).all())
    failures=dict(db.execute(select(PlatformEvent.user_id,func.count(PlatformEvent.id)).where(PlatformEvent.kind=='ai_failure').group_by(PlatformEvent.user_id)).all())
    return [{'user_id':uid,'scans':scans.get(uid,0),'messages':chats.get(uid,0),'failures':failures.get(uid,0)} for uid in sorted((scans.keys()|chats.keys()|failures.keys())-{None})]


@router.get('/settings')
def settings(user:User=Depends(admin)):
    s=get_settings()
    return {'plan_catalog':catalog(),'environment':s.ENVIRONMENT,'demo_payments_enabled':s.DEMO_PAYMENTS_ENABLED,'family_member_limit':s.FAMILY_PACK_MEMBER_LIMIT,
            'ai_configured':bool(s.GROQ_API_KEY and s.GROQ_CHAT_MODEL and s.GROQ_VISION_MODEL),'chat_model':s.GROQ_CHAT_MODEL,'vision_model':s.GROQ_VISION_MODEL,
            'note':'API keys, database credentials and signing secrets are never returned.'}
