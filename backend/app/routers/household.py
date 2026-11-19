from datetime import date, timedelta
from decimal import Decimal
import hashlib
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.core.deps import current_user
from app.database import get_db
from app.models.family import Family, FamilyMembership, Subscription
from app.models.finance import Account, Budget, Goal, Transaction
from app.models.platform import FamilyInvitation, PlatformEvent, ExpenseShare
from app.models.reminder import Reminder, ReminderPayment
from app.models.user import User, now_utc
from app.services.family import get_family, active_users, overview
from app.services.subscriptions import entitlement, family_access, family_capacity
from app.services import household as service
from app.services import invitations as invitation_delivery
from app.routers.reminders import ReminderIn, PayIn, next_due

router=APIRouter(prefix='/family',tags=['Shared household'])


class Clean(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class Name(Clean):
    name:str=Field(min_length=2,max_length=100)


@router.post('',status_code=201)
def create(data:Name,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    rights=entitlement(db,user)
    if rights['billing_plan']!='family_pack' or rights['plan']!='family_pack': raise HTTPException(403,'Your own active Family Pack is required to create a household')
    current=db.scalar(select(FamilyMembership).join(Family,Family.id==FamilyMembership.family_id).where(FamilyMembership.user_id==user.id,FamilyMembership.status=='active',Family.is_active.is_(True)))
    if current: raise HTTPException(409,'You already belong to a household')
    family=db.scalar(select(Family).where(Family.owner_user_id==user.id).with_for_update())
    if family:
        family.is_active=True;family.name=data.name;family.sponsor_user_id=user.id
    else:
        family=Family(owner_user_id=user.id,name=data.name,sponsor_user_id=user.id);db.add(family);db.flush()
    membership=db.scalar(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id).with_for_update())
    if membership: membership.status='active';membership.can_view_shared=True;membership.can_add_shared=True
    else: db.add(FamilyMembership(family_id=family.id,user_id=user.id,status='active',can_view_shared=True,can_add_shared=True))
    db.add(PlatformEvent(user_id=user.id,kind='household_created',target=str(family.id),details={}))
    db.flush();result=overview(db,family,user);db.commit();return result


@router.patch('')
def settings(data:Name,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True);family_access(db,family,write=True)
    family.name=data.name;db.commit();return overview(db,family,user)


@router.post('/close')
def close(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True)
    if len(active_users(db,family,lock=True,include_inactive=True))>1: raise HTTPException(409,'Remove other members before closing; ownership transfer is not supported')
    if (db.scalar(select(Goal.id).where(Goal.family_id==family.id).limit(1))
            or db.scalar(select(Account.id).where(Account.family_id==family.id).limit(1))
            or db.scalar(select(Transaction.id).where(Transaction.family_id==family.id).limit(1))
            or db.scalar(select(Budget.id).where(Budget.family_id==family.id).limit(1))
            or db.scalar(select(Reminder.id).where(Reminder.family_id==family.id).limit(1))):
        raise HTTPException(409,'This household has shared records. It cannot be closed through the empty-household action.')
    family.is_active=False
    for invitation in db.scalars(select(FamilyInvitation).where(FamilyInvitation.family_id==family.id,FamilyInvitation.status=='pending').with_for_update()): invitation.status='revoked'
    for membership in db.scalars(select(FamilyMembership).where(FamilyMembership.family_id==family.id).with_for_update()): membership.status='removed'
    db.commit();return {'message':'Empty household closed. Personal records and subscription are unchanged.'}


@router.post('/leave')
def leave(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,lock=True)
    if family.owner_user_id==user.id: raise HTTPException(409,'Owners cannot leave their household. Close an empty household or manage its membership first.')
    for membership in db.scalars(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id,FamilyMembership.status=='active').with_for_update()): membership.status='removed'
    db.commit();return {'message':'Membership ended. Your personal subscription, history and recorded contributions are preserved.'}


class Permissions(Clean):
    can_view_shared:bool
    can_add_shared:bool


@router.patch('/members/{key}/permissions')
def permissions(key:int,data:Permissions,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True)
    if data.can_view_shared or data.can_add_shared: family_access(db,family,write=True)
    if key==family.owner_user_id: raise HTTPException(422,'Owner permissions are intrinsic')
    membership=db.scalar(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==key,FamilyMembership.status=='active').with_for_update())
    if membership is None: raise HTTPException(404,'Active member not found')
    if data.can_add_shared and not data.can_view_shared: raise HTTPException(422,'Shared editing requires shared viewing permission')
    membership.can_view_shared=data.can_view_shared;membership.can_add_shared=data.can_add_shared;db.commit()
    return data


class Invite(Permissions):
    email:EmailStr


def _email_invitation(db, row, token, family, user, previous_token_state=None):
    url = invitation_delivery.invitation_url(token)
    db.add(PlatformEvent(user_id=user.id, kind='family_invitation_email', target=str(row.id), details={'status': 'unconfirmed'}))
    # Keep the invitation and release household locks before the SMTP request.
    db.commit()
    failure = None
    message_id = None
    try:
        message_id = invitation_delivery.send_invitation(row.email, household_name=family.name, inviter_name=user.full_name, url=url)
        delivery_status = 'submitted'
    except Exception as error:
        delivery_status = 'failed'
        failure = error
    details = {'status': delivery_status}
    if message_id:
        details['message_id'] = message_id
    if failure:
        # Record only bounded codes, never provider responses or credentials.
        details['reason'] = type(failure).__name__[:80]
        smtp_code = getattr(failure, 'smtp_code', None)
        if isinstance(smtp_code, int):
            details['smtp_code'] = smtp_code
        if previous_token_state is not None:
            current = db.scalar(select(FamilyInvitation).where(FamilyInvitation.id == row.id).with_for_update().execution_options(populate_existing=True))
            if current.status == 'pending' and current.token_hash == hashlib.sha256(token.encode()).hexdigest():
                current.token_hash, current.expires_at = previous_token_state
    db.add(PlatformEvent(user_id=user.id, kind='family_invitation_email', target=str(row.id), details=details))
    db.commit()
    if failure:
        if isinstance(failure, HTTPException):
            raise failure
        raise HTTPException(502, invitation_delivery.submission_failure(failure))
    return {'id': row.id, 'token': token, 'expires_at': row.expires_at,
            'invitation_url': url, 'is_local_url': False,
            'delivery_status': delivery_status, 'delivery': invitation_delivery.DELIVERY_MESSAGES[delivery_status]}


@router.post('/invitations',status_code=201)
def invite(data:Invite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True);family_access(db,family,write=True)
    email=str(data.email).lower()
    if email==user.email.lower(): raise HTTPException(409,'You are already the owner')
    invitation_delivery.require_configuration()
    pending=db.scalars(select(FamilyInvitation).where(FamilyInvitation.family_id==family.id,FamilyInvitation.status=='pending',FamilyInvitation.expires_at>now_utc()).with_for_update()).all()
    if any(i.email.lower()==email for i in pending): raise HTTPException(409,'An active invitation already exists for that email. Use Resend Invitation to email it again.')
    members=active_users(db,family,lock=True,include_inactive=True)
    if any(m.email.lower()==email for m in members): raise HTTPException(409,'This person is already a member')
    if len(members)+len(pending)>=family_capacity(db,family): raise HTTPException(409,'Household capacity is full or reserved by pending invitations')
    if data.can_add_shared and not data.can_view_shared: raise HTTPException(422,'Editing requires shared viewing permission')
    token=secrets.token_urlsafe(32)
    row=FamilyInvitation(family_id=family.id,invited_by=user.id,email=email,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=now_utc()+timedelta(days=7),can_view_shared=data.can_view_shared,can_add_shared=data.can_add_shared)
    db.add(row);db.flush()
    return _email_invitation(db, row, token, family, user)


@router.post('/invitations/{key}/resend')
def resend(key:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True);family_access(db,family,write=True)
    invitation_delivery.require_configuration()
    row=db.scalar(select(FamilyInvitation).where(FamilyInvitation.id==key,FamilyInvitation.family_id==family.id).with_for_update().execution_options(populate_existing=True))
    if row is None: raise HTTPException(404,'Invitation not found')
    if row.status!='pending' or row.expires_at<=now_utc(): raise HTTPException(409,'Only an unexpired pending invitation can be resent')
    members=active_users(db,family,lock=True,include_inactive=True)
    if any(member.email.casefold()==row.email.casefold() for member in members): raise HTTPException(409,'This person is already a member')
    pending=db.scalars(select(FamilyInvitation.id).where(FamilyInvitation.family_id==family.id,FamilyInvitation.status=='pending',FamilyInvitation.expires_at>now_utc()).with_for_update()).all()
    if len(members)+len(pending)>family_capacity(db,family): raise HTTPException(409,'Household capacity is full or reserved by other invitations')
    latest=db.scalar(select(PlatformEvent).where(PlatformEvent.kind=='family_invitation_email',PlatformEvent.target==str(row.id)).order_by(PlatformEvent.id.desc()).limit(1))
    if latest and latest.details.get('status') in {'submitted','unconfirmed'} and latest.created_at>now_utc()-timedelta(seconds=60):
        raise HTTPException(429,'Please wait one minute before resending this invitation')
    # The plaintext token is never stored. An explicit resend replaces the old
    # link while retaining the same invitation, permissions and reserved seat.
    previous_token_state = (row.token_hash, row.expires_at)
    token=secrets.token_urlsafe(32)
    row.token_hash=hashlib.sha256(token.encode()).hexdigest()
    row.expires_at=now_utc()+timedelta(days=7)
    return _email_invitation(db, row, token, family, user, previous_token_state=previous_token_state)


@router.get('/invitations')
def invitations(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True)
    now=now_utc()
    active=(FamilyInvitation.status=='pending') & (FamilyInvitation.expires_at>now)
    rows=db.scalars(select(FamilyInvitation).where(FamilyInvitation.family_id==family.id).order_by(case((active,0),else_=1),FamilyInvitation.id.desc()).limit(100)).all()
    latest={}
    if rows:
        events=db.scalars(select(PlatformEvent).where(PlatformEvent.kind=='family_invitation_email',PlatformEvent.target.in_([str(r.id) for r in rows])).order_by(PlatformEvent.id.desc()))
        for event in events:
            latest.setdefault(event.target,event)
    result=[]
    for row in rows:
        event=latest.get(str(row.id))
        delivery_status=event.details.get('status','unknown') if event else 'unknown'
        result.append({'id':row.id,'email':row.email,'status':'expired' if row.status=='pending' and row.expires_at<=now else row.status,
                       'expires_at':row.expires_at,'created_at':row.created_at,'delivery_status':delivery_status,
                       'email_submitted_at':event.created_at if event and delivery_status=='submitted' else None})
    return result


@router.delete('/invitations/{key}')
def revoke(key:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=get_family(db,user,owner_only=True,lock=True)
    row=db.scalar(select(FamilyInvitation).where(FamilyInvitation.id==key,FamilyInvitation.family_id==family.id).with_for_update())
    if row is None: raise HTTPException(404,'Invitation not found')
    if row.status=='pending': row.status='revoked'
    db.commit();return {'status':row.status}


class InvitationToken(Clean):
    token:str=Field(min_length=32,max_length=100)


@router.post('/invitations/preview')
def preview(data:InvitationToken,db:Session=Depends(get_db)):
    """Only a bearer of the unguessable token can preview invitation metadata.

    Tokens stay in a POST body and URL fragment, never in access-log paths.
    Preview does not grant membership or expose financial/subscription records.
    """
    digest=hashlib.sha256(data.token.encode()).hexdigest()
    row=db.scalar(select(FamilyInvitation).where(FamilyInvitation.token_hash==digest))
    if row is None: raise HTTPException(404,'This invitation link is invalid. Ask the owner for a new invitation.')
    family=db.get(Family,row.family_id)
    if family is None or not family.is_active: raise HTTPException(410,'This household is no longer active. Ask the owner for a new invitation.')
    inviter=db.get(User,row.invited_by)
    status='expired' if row.status=='pending' and row.expires_at<=now_utc() else row.status
    return {'household_name':family.name,'inviter_name':inviter.full_name if inviter else 'The household owner',
            'invited_email':row.email,'status':status,'expires_at':row.expires_at}


class Answer(InvitationToken):
    accept:bool


@router.post('/invitations/respond')
def respond(data:Answer,user:User=Depends(current_user),db:Session=Depends(get_db)):
    digest=hashlib.sha256(data.token.encode()).hexdigest()
    initial=db.scalar(select(FamilyInvitation).where(FamilyInvitation.token_hash==digest))
    if initial is None: raise HTTPException(404,'Invitation not found')
    family=db.scalar(select(Family).where(Family.id==initial.family_id,Family.is_active.is_(True)).with_for_update())
    if family is None: raise HTTPException(409,'Household is no longer active')
    row=db.scalar(select(FamilyInvitation).where(FamilyInvitation.id==initial.id).with_for_update().execution_options(populate_existing=True))
    if row.email.casefold()!=user.email.casefold(): raise HTTPException(403,'Sign in with the exact invited email')
    if row.status=='accepted':
        existing=db.scalar(select(FamilyMembership.id).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id,FamilyMembership.status=='active').with_for_update())
        if not existing: raise HTTPException(409,'This invitation was already used. Request a new invitation to rejoin.')
        return {'status':'accepted','message':'This invitation was already accepted.'}
    if row.status!='pending' or row.expires_at<=now_utc(): raise HTTPException(409,'Invitation is expired or no longer pending')
    if not data.accept:
        row.status='rejected';db.commit();return {'status':'rejected'}
    family_access(db,family,write=True)
    # Serializes simultaneous invitations for the same recipient across households.
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    active_membership=db.scalar(select(FamilyMembership).join(Family,Family.id==FamilyMembership.family_id).where(FamilyMembership.user_id==user.id,FamilyMembership.status=='active',Family.is_active.is_(True)).with_for_update())
    owned=db.scalar(select(Family.id).where(Family.owner_user_id==user.id,Family.is_active.is_(True)))
    if active_membership or owned: raise HTTPException(409,'Leave or explicitly close your existing empty household before joining another')
    if len(active_users(db,family,lock=True,include_inactive=True))>=family_capacity(db,family): raise HTTPException(409,'Household member limit reached')
    membership=db.scalar(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id).with_for_update())
    if membership: membership.status='active';membership.can_view_shared=row.can_view_shared;membership.can_add_shared=row.can_add_shared
    else: db.add(FamilyMembership(family_id=family.id,user_id=user.id,status='active',can_view_shared=row.can_view_shared,can_add_shared=row.can_add_shared))
    row.status='accepted';db.commit()
    return {'status':'accepted','message':'Your own subscription was not canceled or changed.'}


class WalletIn(Clean):
    name:str=Field(min_length=1,max_length=120)


@router.get('/wallets')
def wallets(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user)
    return [{'id':a.id,'name':a.name,'currency':a.currency,'balance':str(service.account_balance(db,a)),'is_archived':a.is_archived} for a in db.scalars(select(Account).where(Account.family_id==family.id))]


@router.post('/wallets',status_code=201)
def create_wallet(data:WalletIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,owner=True,write=True)
    row=Account(user_id=family.owner_user_id,family_id=family.id,name=data.name,kind='wallet',currency='LKR',opening_balance=0)
    db.add(row);db.commit();return {'id':row.id,'name':row.name,'balance':'0.00'}


@router.patch('/wallets/{key}')
def edit_wallet(key:int,data:WalletIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,owner=True,write=True);row=service.wallet(db,family,key);row.name=data.name;db.commit();return {'id':row.id,'name':row.name}


class Funding(Clean):
    account_id:int=Field(gt=0)
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    request_id:str=Field(min_length=1,max_length=36)


@router.post('/wallets/{key}/contribute')
def fund(key:int,data:Funding,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True)
    result=service.fund(db,user,family,key,data.account_id,data.amount,data.request_id);db.commit();return result


class Split(Clean):
    user_id:int=Field(gt=0)
    value:Decimal | None=Field(default=None,ge=0,max_digits=14,decimal_places=4)


class SharedIncome(Clean):
    account_id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=60)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(default='', max_length=255)
    txn_date: date = Field(default_factory=date.today)
    request_id: str = Field(min_length=1, max_length=36)


@router.post('/income', status_code=201)
def income(data: SharedIncome, user: User=Depends(current_user), db: Session=Depends(get_db)):
    try:
        family = service.access(db, user, write=True)
        result = service.income(db, user, family, data)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get('/income')
def income_history(user: User=Depends(current_user), db: Session=Depends(get_db)):
    family = service.access(db, user)
    rows = db.scalars(select(Transaction).where(
        Transaction.family_id == family.id, Transaction.kind == 'income',
        Transaction.deleted_at.is_(None),
    ).order_by(Transaction.txn_date.desc(), Transaction.id.desc()).limit(100)).all()
    return [{'id': t.id, 'recorded_by_id': t.user_id,
             'recorded_by_name': db.get(User, t.user_id).full_name,
             'category': t.category, 'amount': str(t.amount),
             'description': t.description, 'date': t.txn_date} for t in rows]


class Expense(Clean):
    account_id:int=Field(gt=0)
    category:str=Field(min_length=1,max_length=60)
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    description:str=Field(default='',max_length=255)
    txn_date:date=Field(default_factory=date.today)
    split_mode:Literal['equal','custom','percentage']='equal'
    splits:list[Split]=Field(default_factory=list,max_length=50)
    request_id:str=Field(min_length=1,max_length=36)


@router.post('/expenses',status_code=201)
def expense(data:Expense,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True);result=service.expense(db,user,family,data);db.commit();return result


@router.get('/expenses')
def expenses(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user)
    rows=db.scalars(select(Transaction).where(Transaction.family_id==family.id,Transaction.kind=='expense',Transaction.deleted_at.is_(None)).order_by(Transaction.id.desc()).limit(100)).all()
    return [{'id':t.id,'payer_id':t.user_id,'payer_name':db.get(User,t.user_id).full_name,'category':t.category,'amount':str(t.amount),'description':t.description,'date':t.txn_date,
             'source':'shared_wallet' if db.get(Account,t.account_id).family_id else 'personal_payment',
             'shares':[{'user_id':r.user_id,'amount':str(r.amount)} for r in db.scalars(select(ExpenseShare).where(ExpenseShare.transaction_id==t.id))]} for t in rows]


class SharedBudget(Clean):
    category:str=Field(min_length=1,max_length=60)
    monthly_limit:Decimal=Field(ge=0,max_digits=12,decimal_places=2)


@router.post('/budgets',status_code=201)
def create_budget(data:SharedBudget,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True,owner=True)
    if db.scalar(select(Budget.id).where(Budget.family_id==family.id,func.lower(Budget.category)==data.category.lower())): raise HTTPException(409,'Shared category budget already exists')
    row=Budget(user_id=family.owner_user_id,family_id=family.id,**data.model_dump());db.add(row);db.commit();return {'id':row.id}


@router.put('/budgets/{key}')
def edit_budget(key:int,data:SharedBudget,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True,owner=True)
    row=db.scalar(select(Budget).where(Budget.id==key,Budget.family_id==family.id).with_for_update())
    if row is None: raise HTTPException(404,'Shared budget not found')
    if db.scalar(select(Budget.id).where(Budget.family_id==family.id,Budget.id!=key,func.lower(Budget.category)==data.category.lower())): raise HTTPException(409,'Shared category budget already exists')
    row.category=data.category;row.monthly_limit=data.monthly_limit;db.commit();return {'id':row.id}


@router.delete('/budgets/{key}')
def delete_budget(key:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True,owner=True)
    row=db.scalar(select(Budget).where(Budget.id==key,Budget.family_id==family.id).with_for_update())
    if row is None: raise HTTPException(404,'Shared budget not found')
    db.delete(row);db.commit();return {'message':'Shared budget removed; transaction history is preserved'}


@router.get('/reimbursements')
def debts(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user);return service.debts(db,family)


@router.post('/reimbursements/{key}/settle')
def settle(key:int,data:Funding,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True);result=service.settle(db,user,family,key,data.account_id,data.amount,data.request_id);db.commit();return result


@router.post('/bills',status_code=201)
def bill(data:ReminderIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True,owner=True);account=service.wallet(db,family,data.account_id)
    if account.is_archived: raise HTTPException(409,'Restore this wallet first')
    row=Reminder(user_id=user.id,family_id=family.id,recurrence_day=data.due_date.day,**data.model_dump());db.add(row);db.commit();return {'id':row.id}


@router.post('/bills/{key}/pay')
def pay(key:int,data:PayIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,write=True)
    row=db.scalar(select(Reminder).where(Reminder.id==key,Reminder.family_id==family.id).with_for_update().execution_options(populate_existing=True))
    if row is None: raise HTTPException(404,'Household bill not found')
    old=db.scalar(select(ReminderPayment).where(ReminderPayment.reminder_id==row.id,ReminderPayment.due_date==data.due_date).with_for_update())
    if old: return {'transaction_id':old.transaction_id,'already_paid':True}
    if not row.is_active or row.due_date!=data.due_date: raise HTTPException(409,'Bill occurrence changed; refresh first')
    result=service.expense(db,user,family,Expense(account_id=row.account_id,category=row.category,amount=row.amount,description=row.name,request_id=f'bill:{row.id}:{row.due_date}'))
    db.add(ReminderPayment(reminder_id=row.id,due_date=row.due_date,transaction_id=result['id']))
    if row.recurrence=='none': row.is_active=False
    else: row.due_date=next_due(row.due_date,row.recurrence,row.recurrence_day)
    db.commit();return {'transaction_id':result['id'],'already_paid':False}


@router.get('/participants')
def participants(user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user)
    return [{'id':m.id,'full_name':m.full_name} for m in active_users(db,family)]


@router.get('/activity')
def activity(user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Read existing explicit shared ledgers only; never expose private sources."""
    from app.models.finance import GoalContribution
    from app.models.platform import ExpenseShare, Settlement
    family=service.access(db,user)
    entries=[]
    for row in db.scalars(select(Transaction).where(Transaction.family_id==family.id,Transaction.deleted_at.is_(None)).order_by(Transaction.id.desc()).limit(100)):
        if row.kind not in {'income','expense','transfer_in'}: continue
        entries.append({'key':f'transaction:{row.id}','date':row.txn_date.isoformat(),'user_id':row.user_id,'kind':'Wallet contribution (transfer)' if row.kind=='transfer_in' else 'Shared '+row.kind,'description':row.description or row.category,'amount':str(row.amount)})
    for row,goal in db.execute(select(GoalContribution,Goal).join(Goal,Goal.id==GoalContribution.current_goal_id).where(Goal.family_id==family.id).order_by(GoalContribution.id.desc()).limit(100)):
        entries.append({'key':f'goal:{row.id}','date':row.recorded_on.isoformat(),'user_id':row.user_id,'kind':'Goal allocation reversed' if row.reversed_at else 'Goal allocation','description':goal.name,'amount':str(row.amount)})
    for row in db.scalars(select(Settlement).join(ExpenseShare,ExpenseShare.id==Settlement.share_id).join(Transaction,Transaction.id==ExpenseShare.transaction_id).where(Transaction.family_id==family.id).order_by(Settlement.id.desc()).limit(100)):
        entries.append({'key':f'settlement:{row.id}','date':row.created_at.isoformat(),'user_id':row.user_id,'kind':'Reimbursement (transfer)','description':'Expense share repayment','amount':str(row.amount)})
    names={row.id:row.full_name for row in db.scalars(select(User).where(User.id.in_({entry['user_id'] for entry in entries})))}
    for entry in entries:
        entry['member']=names.get(entry.pop('user_id'))
    return sorted(entries,key=lambda row:(row['date'],row['key']),reverse=True)[:100]


class Archived(Clean):
    archived:bool


@router.post('/wallets/{key}/archive')
def archive_wallet(key:int,data:Archived,user:User=Depends(current_user),db:Session=Depends(get_db)):
    family=service.access(db,user,owner=True,write=True);row=service.wallet(db,family,key)
    row.is_archived=data.archived;db.commit();return {'id':row.id,'is_archived':row.is_archived}
