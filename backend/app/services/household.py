"""Explicit shared ledgers. Membership never grants private account access."""
from datetime import date
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import func, select
from app.models.family import FamilyMembership
from app.models.finance import Account, AccountTransfer, Budget, Goal, Transaction
from app.models.platform import ExpenseShare, Settlement
from app.models.reminder import Reminder
from app.models.request import TransactionRequest
from app.models.user import User
from app.services.family import active_users, get_family
from app.services.subscriptions import family_access
from app.services.account import account_balance, owned_account, usable_account
from app.services.goals import shared_details

ZERO=Decimal('0.00')


def access(db,user,*,write=False,owner=False):
    family=get_family(db,user,owner_only=owner,lock=True)
    members=active_users(db,family,lock=True)
    if user.id not in {m.id for m in members}: raise HTTPException(403,'Active household membership required')
    if user.id!=family.owner_user_id:
        membership=db.scalar(select(FamilyMembership).where(FamilyMembership.family_id==family.id,FamilyMembership.user_id==user.id,FamilyMembership.status=='active').with_for_update())
        if not membership or not membership.can_view_shared or (write and not membership.can_add_shared):
            raise HTTPException(403,'The owner has not granted this shared household permission')
    if write: family_access(db,family,write=True)
    return family


def wallet(db,family,key,lock=True):
    row=db.scalar(select(Account).where(Account.id==key,Account.family_id==family.id).with_for_update().execution_options(populate_existing=True))
    if row is None: raise HTTPException(404,'Shared wallet not found')
    if row.currency!='LKR': raise HTTPException(409,'Shared wallets require LKR; conversion is unavailable')
    return row


def replay(db,user,key,payload):
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    previous=db.scalar(select(TransactionRequest).where(TransactionRequest.user_id==user.id,TransactionRequest.request_key==key).with_for_update())
    if previous and previous.payload_hash!=digest: raise HTTPException(409,'Request key was used for different financial details')
    return previous,digest


def request_record(db,user,key,digest,txn):
    db.add(TransactionRequest(user_id=user.id,request_key=key,payload_hash=digest,transaction_id=txn.id))


def move(db,user,source,destination,amount,key,description,family_id=None):
    for account in [source,destination]:
        if account.currency!='LKR' or account.is_archived: raise HTTPException(409,'Restore matching LKR accounts before transferring')
    if account_balance(db,source,lock_entries=True)<amount: raise HTTPException(422,'Insufficient tracked account balance')
    header=AccountTransfer(user_id=user.id,from_account_id=source.id,to_account_id=destination.id,amount=amount,currency='LKR',txn_date=date.today(),description=description,client_request_id=key)
    db.add(header);db.flush()
    outgoing=Transaction(user_id=source.user_id if source.family_id is None else user.id,account_id=source.id,family_id=source.family_id,kind='transfer_out',category='Transfer',amount=amount,description=description,txn_date=date.today(),transfer_id=header.id)
    incoming=Transaction(user_id=destination.user_id if destination.family_id is None else user.id,account_id=destination.id,family_id=destination.family_id,kind='transfer_in',category='Transfer',amount=amount,description=description,txn_date=date.today(),transfer_id=header.id)
    db.add_all([outgoing,incoming]);db.flush()
    return header,outgoing,incoming


def fund(db,user,family,wallet_id,account_id,amount,key):
    payload={'operation':'wallet_funding','wallet_id':wallet_id,'account_id':account_id,'amount':amount}
    previous,digest=replay(db,user,key,payload)
    if previous: return {'transaction_id':previous.transaction_id,'already_recorded':True}
    # Lock both account rows in a deterministic order.
    accounts={a.id:a for a in db.scalars(select(Account).where(Account.id.in_(sorted({wallet_id,account_id}))).order_by(Account.id).with_for_update().execution_options(populate_existing=True))}
    shared=wallet(db,family,wallet_id)
    personal=accounts.get(account_id)
    if not personal or personal.user_id!=user.id or personal.family_id is not None: raise HTTPException(404,'Personal account not found')
    header,outgoing,incoming=move(db,user,personal,shared,amount,key,'Household wallet contribution',family.id)
    request_record(db,user,key,digest,outgoing)
    return {'transaction_id':outgoing.id,'transfer_id':header.id,'already_recorded':False}


def split_amounts(amount,mode,items,allowed):
    if not items: return {}
    ids=[item.user_id for item in items]
    if len(ids)!=len(set(ids)) or not set(ids)<=allowed: raise HTTPException(422,'Split participants must be distinct active household members')
    ordered=sorted(items,key=lambda item:item.user_id)
    if mode=='custom':
        shares={item.user_id:item.value for item in ordered}
        if any(v is None or v<0 or v.quantize(Decimal('.01'))!=v for v in shares.values()) or sum(shares.values())!=amount: raise HTTPException(422,'Custom split amounts must exactly equal the expense')
        return shares
    if mode=='percentage':
        if any(item.value is None or item.value<0 for item in ordered) or sum(item.value for item in ordered)!=100: raise HTTPException(422,'Percentages must total 100')
        raw={item.user_id:amount*item.value/100 for item in ordered}
    else:
        raw={item.user_id:amount/len(ordered) for item in ordered}
    shares={uid:value.quantize(Decimal('.01'),rounding=ROUND_FLOOR) for uid,value in raw.items()}
    cents=int((amount-sum(shares.values()))*100)
    ranked=sorted(raw,key=lambda uid:(-(raw[uid]-shares[uid]),uid))
    for uid in ranked[:cents]: shares[uid]+=Decimal('.01')
    return shares


def expense(db,user,family,data):
    previous,digest=replay(db,user,data.request_id,{'operation':'shared_expense',**data.model_dump(mode='json')})
    if previous: return {'id':previous.transaction_id,'already_recorded':True}
    account=db.scalar(select(Account).where(Account.id==data.account_id).with_for_update().execution_options(populate_existing=True))
    if account is None: raise HTTPException(404,'Payment account not found')
    if account.family_id is not None:
        if account.family_id!=family.id: raise HTTPException(404,'Payment wallet not found')
        if data.splits: raise HTTPException(422,'Wallet-funded expenses cannot create personal reimbursement debts')
    elif account.user_id!=user.id: raise HTTPException(404,'Personal payment account not found')
    if account.currency!='LKR' or account.is_archived: raise HTTPException(409,'Use an active LKR payment account')
    if account_balance(db,account,lock_entries=True)<data.amount: raise HTTPException(422,'Insufficient tracked balance')
    shares=split_amounts(data.amount,data.split_mode,data.splits,{m.id for m in active_users(db,family,lock=True)})
    row=Transaction(user_id=user.id,family_id=family.id,account_id=account.id,kind='expense',category=data.category,amount=data.amount,description=data.description,txn_date=data.txn_date)
    db.add(row);db.flush()
    for uid,amount in shares.items(): db.add(ExpenseShare(transaction_id=row.id,user_id=uid,amount=amount))
    request_record(db,user,data.request_id,digest,row)
    return {'id':row.id,'already_recorded':False}


def debts(db,family):
    rows=db.execute(select(ExpenseShare,Transaction).join(Transaction,Transaction.id==ExpenseShare.transaction_id).where(Transaction.family_id==family.id,Transaction.deleted_at.is_(None)).order_by(ExpenseShare.id)).all()
    ids={uid for share,txn in rows for uid in [share.user_id,txn.user_id]}
    names={u.id:u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))}
    result=[]
    for share,txn in rows:
        if share.user_id==txn.user_id: continue
        paid=Decimal(db.scalar(select(func.coalesce(func.sum(Settlement.amount),0)).where(Settlement.share_id==share.id)) or 0)
        result.append({'share_id':share.id,'expense_id':txn.id,'debtor_id':share.user_id,'debtor':names.get(share.user_id),'creditor_id':txn.user_id,'creditor':names.get(txn.user_id),'amount':str(share.amount),'settled':str(paid),'remaining':str(share.amount-paid)})
    return result


def settle(db,user,family,share_id,account_id,amount,key):
    previous=db.scalar(select(Settlement).where(Settlement.user_id==user.id,Settlement.request_id==key).with_for_update())
    if previous:
        transfer=db.get(AccountTransfer,previous.transfer_id)
        if previous.share_id!=share_id or previous.amount!=amount or transfer.from_account_id!=account_id: raise HTTPException(409,'Settlement request has conflicting details')
        return {'id':previous.id,'already_recorded':True}
    row=db.execute(select(ExpenseShare,Transaction).join(Transaction,Transaction.id==ExpenseShare.transaction_id).where(ExpenseShare.id==share_id,Transaction.family_id==family.id,Transaction.deleted_at.is_(None)).with_for_update()).first()
    if row is None: raise HTTPException(404,'Expense share not found')
    share,txn=row
    if share.user_id!=user.id or txn.user_id==user.id: raise HTTPException(403,'You may settle only your own debt to another member')
    paid=sum(db.scalars(select(Settlement.amount).where(Settlement.share_id==share.id).with_for_update()),ZERO)
    if amount>share.amount-paid: raise HTTPException(422,'Settlement exceeds the outstanding share')
    accounts={a.id:a for a in db.scalars(select(Account).where(Account.id.in_(sorted({account_id,txn.account_id}))).order_by(Account.id).with_for_update().execution_options(populate_existing=True))}
    source=accounts.get(account_id);destination=accounts.get(txn.account_id)
    if not source or source.family_id is not None or source.user_id!=user.id: raise HTTPException(404,'Your personal account was not found')
    if not destination or destination.family_id is not None or destination.user_id!=txn.user_id: raise HTTPException(409,'Original payer account cannot receive this settlement')
    header,_,_=move(db,user,source,destination,amount,key,'Household reimbursement')
    record=Settlement(share_id=share.id,user_id=user.id,amount=amount,transfer_id=header.id,request_id=key)
    db.add(record);db.flush()
    return {'id':record.id,'already_recorded':False}


def household_report(db,user,year=None,month=None):
    family=access(db,user)
    first=date(year,month,1) if year is not None else date.today().replace(day=1)
    next_first=(first.replace(year=first.year+1,month=1) if first.month==12 else first.replace(month=first.month+1))
    wallets=db.scalars(select(Account).where(Account.family_id==family.id)).all()
    if any(w.currency!='LKR' for w in wallets): raise HTTPException(409,'Household currency conversion is unavailable')
    balance=sum((account_balance(db,w) for w in wallets),ZERO)
    txns=db.scalars(select(Transaction).where(Transaction.family_id==family.id,Transaction.deleted_at.is_(None))).all()
    month=[t for t in txns if first<=t.txn_date<next_first]
    spending=sum((t.amount for t in month if t.kind=='expense'),ZERO)
    funding=sum((t.amount for t in month if t.kind=='transfer_in'),ZERO)
    wallet_ids={w.id for w in wallets}
    wallet_spent=sum((t.amount for t in month if t.kind=='expense' and t.account_id in wallet_ids),ZERO)
    categories={}
    for txn in month:
        if txn.kind=='expense': categories[txn.category.casefold()]=categories.get(txn.category.casefold(),ZERO)+txn.amount
    budgets=[];reserves={}
    for budget in db.scalars(select(Budget).where(Budget.family_id==family.id)):
        spent=categories.get(budget.category.casefold(),ZERO);remaining=max(ZERO,budget.monthly_limit-spent)
        reserves[budget.category.casefold()]=remaining
        percent=float(spent/budget.monthly_limit*100) if budget.monthly_limit else (100 if spent else 0)
        budgets.append({'id':budget.id,'category':budget.category,'limit':str(budget.monthly_limit),'spent':str(spent),'remaining':str(budget.monthly_limit-spent),'used_percent':percent,'status':'over_limit' if percent>=100 else 'warning' if percent>=80 else 'on_track'})
    bills=db.scalars(select(Reminder).where(Reminder.family_id==family.id,Reminder.is_active.is_(True)).order_by(Reminder.due_date)).all()
    bill_reserves={}
    for bill in bills:
        if bill.due_date<next_first: bill_reserves[bill.category.casefold()]=bill_reserves.get(bill.category.casefold(),ZERO)+bill.amount
    reserve=sum((max(reserves.get(cat,ZERO),bill_reserves.get(cat,ZERO)) for cat in reserves.keys()|bill_reserves.keys()),ZERO)
    goals=[shared_details(db,g) for g in db.scalars(select(Goal).where(Goal.family_id==family.id))]
    uncertain=any(Decimal(g['saved_amount'])>0 for g in goals)
    actors={t.user_id for t in txns}|{c['user_id'] for g in goals for c in g['contributions']}|{m.id for m in active_users(db,family)}
    names={m.id:m.full_name for m in db.scalars(select(User).where(User.id.in_(actors)))}
    members=[]
    for uid in sorted(actors):
        rows=[t for t in txns if t.user_id==uid]
        members.append({'user_id':uid,'full_name':names[uid],'income':'0.00','expenses':str(sum((t.amount for t in month if t.user_id==uid and t.kind=='expense'),ZERO)),
                        'net_cash_flow':'0.00','wallet_funding':str(sum((t.amount for t in month if t.user_id==uid and t.kind=='transfer_in'),ZERO)),
                        'shared_goal_contributions':str(sum((Decimal(c['amount']) for g in goals for c in g['contributions'] if c['user_id']==uid),ZERO))})
    trends=[]
    for offset in range(-5,1):
        from app.routers.dashboard import month_start
        start=month_start(first.year,first.month,offset);end=month_start(start.year,start.month,1)
        trends.append({'month':start.strftime('%Y-%m'),'income':'0.00','wallet_funding':str(sum((t.amount for t in txns if t.kind=='transfer_in' and start<=t.txn_date<end),ZERO)),'expenses':str(sum((t.amount for t in txns if t.kind=='expense' and start<=t.txn_date<end),ZERO))})
    return {'scope':'family','shared_only':True,'currency':'LKR','onboarding_completed':user.onboarding_completed,'can_view_family':True,
        'total_balance':str(balance),'monthly_income':'0.00','monthly_expenses':str(spending),'monthly_wallet_funding':str(funding),'monthly_net_cash_flow':str(funding-wallet_spent),
        'safe_to_spend_estimate':None if uncertain else str(max(ZERO,balance-reserve)),
        'safe_to_spend_note':'Unavailable: shared goal allocations may be held outside shared wallets.' if uncertain else 'Shared wallet funds less unpaid shared commitments; personal funds and reimbursements excluded.',
        'spending_by_category':[{'category':k,'amount':str(v)} for k,v in categories.items()],'budgets':budgets,'goals':[],
        'shared_goals':goals,'member_summaries':members,'upcoming_bills':[{'id':b.id,'name':b.name,'category':b.category,'amount':str(b.amount),'due_date':b.due_date,'bill_count':1} for b in bills],
        'recent_transactions':[],'six_month_trend':trends,'total_savings_allocated':str(sum((Decimal(g['saved_amount']) for g in goals),ZERO)),
        'family_population':'Explicitly shared records only. Private salaries, accounts, transactions, budgets and bills are never pooled.',
        'reimbursements':debts(db,family),'planned_monthly_income':'0.00','remaining_budget':str(sum(reserves.values(),ZERO))}
