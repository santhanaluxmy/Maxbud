from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import current_user
from app.core.security import hash_password
from app.database import get_db
from app.models.user import AuthIdentity, User
from app.routers.auth import password_matches
from app.schemas.auth import RegisterIn, UserOut

router = APIRouter(prefix="/settings", tags=["Settings"])


class ProfileIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str = Field(min_length=2, max_length=100)


@router.put("/profile", response_model=UserOut)
def profile(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name
    db.commit()
    return user


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str


@router.put("/password")
def password(data: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    identity = db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user.id, AuthIdentity.provider == "password").with_for_update())
    if not identity or not password_matches(data.current_password, identity.password_hash):
        raise HTTPException(403, "Current password is incorrect or password login is unavailable")
    try:
        RegisterIn(full_name=user.full_name, email=user.email, password=data.new_password, confirm_password=data.confirm_password)
    except ValueError:
        raise HTTPException(422, "Passwords must match and include uppercase, lowercase, a number and a symbol")
    identity.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated"}


@router.get('/export')
def export(user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Read-only access survives expiry. Whitelist fields; never export identities."""
    from app.models.finance import Account, Transaction, Budget, Goal, IncomeSource, GoalContribution
    from app.models.reminder import Reminder
    from app.models.ai import AIScan, AdvisorMessage
    from decimal import Decimal
    def rows(model,fields,condition):
        return [{field:(str(getattr(row,field)) if isinstance(getattr(row,field),Decimal) else getattr(row,field)) for field in fields} for row in db.scalars(select(model).where(condition))]
    return {'profile':{'full_name':user.full_name,'email':user.email,'currency':user.currency},
            'accounts':rows(Account,['id','name','kind','opening_balance','currency','is_archived'],(Account.user_id==user.id)&Account.family_id.is_(None)),
            'transactions':rows(Transaction,['id','account_id','kind','category','amount','description','txn_date','deleted_at'],Transaction.user_id==user.id),
            'budgets':rows(Budget,['id','category','monthly_limit'],(Budget.user_id==user.id)&Budget.family_id.is_(None)),
            'goals':rows(Goal,['id','name','target_amount','saved_amount','target_date','status'],(Goal.user_id==user.id)&Goal.family_id.is_(None)),
            'income_sources':rows(IncomeSource,['name','amount','frequency'],IncomeSource.user_id==user.id),
            'reminders':rows(Reminder,['name','category','amount','due_date','recurrence'],(Reminder.user_id==user.id)&Reminder.family_id.is_(None)),
            'own_shared_contributions':rows(GoalContribution,['id','current_goal_id','amount','recorded_on'],GoalContribution.user_id==user.id),
            'receipts':rows(AIScan,['id','status','details','transaction_id'],AIScan.user_id==user.id),
            'advisor_history':rows(AdvisorMessage,['question','answer','created_at'],AdvisorMessage.user_id==user.id)}
