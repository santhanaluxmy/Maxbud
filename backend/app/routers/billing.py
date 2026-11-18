"""Sandbox Checkout/Portal + verified, durable, idempotent subscription webhooks."""
import hashlib
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.deps import current_user
from app.database import get_db
from app.models.access import StripeAccount, StripeEvent
from app.models.family import Subscription
from app.models.platform import PlatformEvent
from app.models.user import User, now_utc
from app.routers.subscriptions import Selection
from app.services import stripe_test as stripe
from app.services.subscriptions import entitlement

router = APIRouter(prefix='/billing/stripe', tags=['Stripe sandbox'])


def ready(db):
    if not stripe.enabled():
        raise HTTPException(503, 'Stripe sandbox needs a test key, webhook signing secret and matching Price IDs. Live charges are disabled.')
    if not all(inspect(db.connection()).has_table(name) for name in ['stripe_test_accounts', 'stripe_test_events']):
        raise HTTPException(503, 'Stripe sandbox requires the additive access migration.')


@router.post('/checkout', status_code=201)
def checkout(data: Selection, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ready(db)
    if data.billing_cycle != 'monthly':
        raise HTTPException(422, 'Only monthly subscriptions are available.')
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    price = stripe.price_id(data.plan, data.billing_cycle)
    stripe.validate_price(stripe.call('GET', 'prices/' + price), data.plan, data.billing_cycle)
    account = db.get(StripeAccount, user.id)
    if account and account.checkout_id:
        pending = stripe.call('GET', 'checkout/sessions/' + account.checkout_id)
        if pending.get('status') == 'open':
            if account.checkout_selection == data.plan + ':' + data.billing_cycle:
                return {'url': pending['url'], 'mode': 'stripe_test'}
            stripe.call('POST', 'checkout/sessions/' + account.checkout_id + '/expire')
        elif pending.get('status') == 'complete' and not account.subscription_id:
            raise HTTPException(409, 'Payment confirmation is pending. Return to subscription confirmation to check again; do not pay again.')
    if account and account.subscription_id:
        existing = stripe.call('GET', 'subscriptions/' + account.subscription_id)
        if existing.get('status') not in {'canceled', 'incomplete_expired'}:
            raise HTTPException(409, 'You already have a subscription. Use Manage Subscription for payment details or cancellation. Plan switching is not available here.')
    if not account:
        key = hashlib.sha256((get_settings().JWT_SECRET + ':' + str(user.id)).encode()).hexdigest()
        customer = stripe.call('POST', 'customers', {'email': user.email, 'metadata[maxbud_user_id]': str(user.id)}, 'maxbud-customer-' + key)
        account = StripeAccount(user_id=user.id, customer_id=customer['id'])
        db.add(account)
    origin = get_settings().FRONTEND_ORIGIN.rstrip('/')
    result = stripe.call('POST', 'checkout/sessions', {
        'mode': 'subscription', 'customer': account.customer_id,
        'line_items[0][price]': price, 'line_items[0][quantity]': '1',
        'client_reference_id': str(user.id), 'subscription_data[metadata][maxbud_user_id]': str(user.id),
        'success_url': origin + '/dashboard/payment-success',
        'cancel_url': origin + '/dashboard/upgrade?checkout=canceled',
    }, f'maxbud-checkout-{account.customer_id}-{data.request_id}')
    account.checkout_id = result['id']
    account.checkout_selection = data.plan + ':' + data.billing_cycle
    db.commit()
    return {'url': result['url'], 'mode': 'stripe_test'}


@router.post('/portal')
def portal(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ready(db)
    account = db.get(StripeAccount, user.id)
    if not account or not account.subscription_id:
        raise HTTPException(409, 'No subscription is associated with this account yet.')
    data = {'customer': account.customer_id, 'return_url': get_settings().FRONTEND_ORIGIN.rstrip('/') + '/dashboard/upgrade'}
    if get_settings().STRIPE_PORTAL_CONFIGURATION:
        data['configuration'] = get_settings().STRIPE_PORTAL_CONFIGURATION
    validate_portal_configuration()
    return {'url': stripe.call('POST', 'billing_portal/sessions', data)['url']}


def validate_portal_configuration():
    configuration = get_settings().STRIPE_PORTAL_CONFIGURATION
    if configuration:
        config = stripe.call('GET', 'billing_portal/configurations/' + configuration)
    else:
        configs = stripe.call('GET', 'billing_portal/configurations', {'is_default': 'true', 'active': 'true', 'limit': 1})
        config = next(iter(configs.get('data', [])), None)
    if not config or not config.get('active'):
        raise HTTPException(503, 'Subscription management is being configured. Please try again later.')
    if config.get('features', {}).get('subscription_update', {}).get('enabled'):
        raise HTTPException(503, 'Plan switching must be disabled in the billing portal before subscription management is available.')
    return config


def sync(db, account, state):
    if state.get('livemode') is not False or state.get('customer') != account.customer_id:
        raise HTTPException(409, 'Stripe customer association did not match.')
    if state.get('metadata', {}).get('maxbud_user_id', str(account.user_id)) != str(account.user_id):
        raise HTTPException(409, 'Subscription belongs to a different MaxBud account.')
    items = state.get('items', {}).get('data', [])
    if len(items) != 1 or items[0].get('quantity', 1) != 1:
        raise HTTPException(409, 'Unsupported subscription items; reconcile the sandbox subscription.')
    plan, cycle = stripe.selection(items[0]['price'])
    status = state['status']
    invoice = state.get('latest_invoice')
    paid = isinstance(invoice, dict) and invoice.get('livemode') is False and invoice.get('status') == 'paid' and invoice.get('paid') is True and invoice.get('customer') == account.customer_id and stripe.subscription_id(invoice) == state['id']
    # Existing verified paid access remains separate from checkout redirects.
    sub = db.scalar(select(Subscription).where(Subscription.user_id == account.user_id).with_for_update().execution_options(populate_existing=True))
    account.subscription_id = state['id']
    if not sub:
        sub = Subscription(user_id=account.user_id, plan=plan, source='stripe_test', status='incomplete')
        db.add(sub)
    if status == 'active' and paid:
        sub.plan = plan
        sub.status = 'active'
        sub.source = 'stripe_test'
        sub.billing_cycle = cycle
        sub.period_started_at = stripe.utc(state.get('current_period_start') or items[0]['current_period_start'])
        sub.expires_at = stripe.utc(state.get('current_period_end') or items[0]['current_period_end'])
        sub.cancel_at_period_end = bool(state.get('cancel_at_period_end'))
        sub.pending_plan = None
        sub.pending_cycle = None
    elif sub.source == 'stripe_test':
        # An unpaid mid-period change must not erase the previous verified
        # paid period or prematurely grant the requested upgraded plan.
        if status == 'active' and sub.expires_at and sub.expires_at > now_utc():
            pass
        else:
            sub.status = status if status in {'past_due', 'unpaid', 'canceled', 'incomplete', 'incomplete_expired', 'paused'} else 'expired'
            # A terminated subscription cannot retain paid cancellation grace.
            sub.cancel_at_period_end = False


def sync_subscription(db, account, key):
    if not isinstance(key, str) or not key.startswith('sub_'):
        raise HTTPException(409, 'Subscription identifier is missing from the billing confirmation.')
    if account.subscription_id and account.subscription_id != key:
        prior = stripe.call('GET', 'subscriptions/' + account.subscription_id)
        if prior.get('status') not in {'canceled', 'incomplete_expired'}:
            raise HTTPException(409, 'A different active subscription already exists.')
    state = stripe.call('GET', 'subscriptions/' + key, {'expand[]': 'latest_invoice'})
    if state.get('id') != key:
        raise HTTPException(409, 'Subscription identifier did not match.')
    sync(db, account, state)


@router.post('/reconcile')
def reconcile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Recover missed webhooks using only this user's persisted Stripe mapping.

    No redirect parameter, user-provided session or email can select an account.
    Checkout itself never grants access; sync requires a paid provider invoice.
    """
    ready(db)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    account = db.scalar(select(StripeAccount).where(StripeAccount.user_id == user.id).with_for_update().execution_options(populate_existing=True))
    checkout_status = None
    if account:
        key = account.subscription_id
        if account.checkout_id:
            checkout = stripe.call('GET', 'checkout/sessions/' + account.checkout_id)
            if checkout.get('customer') != account.customer_id or checkout.get('livemode') is not False or checkout.get('mode') != 'subscription' or checkout.get('client_reference_id') != str(user.id):
                raise HTTPException(409, 'Checkout does not belong to this MaxBud account.')
            checkout_status = checkout.get('status')
            if checkout_status == 'complete':
                key = stripe.subscription_id(checkout) or key
        if key:
            sync_subscription(db, account, key)
        db.commit()
    result = entitlement(db, user)
    active = result['source'] == 'stripe_test' and result['plan'] in {'premium_individual', 'family_pack'} and result['status'] == 'active'
    return {'activation': 'active' if active else 'canceled' if checkout_status == 'expired' else 'pending', 'subscription': result}


@router.post('/webhook')
async def webhook(request: Request, stripe_signature: str = Header(default=''), db: Session = Depends(get_db)):
    ready(db)
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, 'Webhook body too large')
    event = stripe.signature(raw, stripe_signature)
    obj = event.get('data', {}).get('object', {})
    customer = obj.get('customer')
    account = db.scalar(select(StripeAccount).where(StripeAccount.customer_id == customer)) if isinstance(customer, str) else None
    if not account:
        return {'received': True, 'ignored': True}
    # Serialize with checkout/cancellation and other events for this user.
    db.scalar(select(User).where(User.id == account.user_id).with_for_update())
    account = db.scalar(select(StripeAccount).where(StripeAccount.user_id == account.user_id).with_for_update().execution_options(populate_existing=True))
    if db.scalar(select(StripeEvent).where(StripeEvent.id == event['id']).with_for_update()):
        return {'received': True, 'duplicate': True}
    kind = event.get('type', '')
    supported = kind.startswith('customer.subscription.') or kind in {'checkout.session.completed', 'checkout.session.async_payment_succeeded', 'checkout.session.async_payment_failed', 'invoice.paid', 'invoice.payment_failed', 'invoice.payment_action_required'}
    if supported:
        key = obj.get('id') if kind.startswith('customer.subscription.') else stripe.subscription_id(obj)
        # Unrelated one-time invoices on the same customer do not change access.
        if kind.startswith('invoice.') and not key:
            return {'received': True, 'ignored': True}
        if not isinstance(key, str) or not key.startswith('sub_'):
            raise HTTPException(409, 'Subscription identifier missing from sandbox event')
        # Fetch current authoritative state; delayed/retried events cannot
        # roll back a later cancellation, renewal or plan change.
        sync_subscription(db, account, key)
    db.add(StripeEvent(id=event['id'], kind=kind[:100]))
    db.add(PlatformEvent(user_id=account.user_id, kind='stripe_test_event', target=event['id'], details={'event': kind, 'billing_mode': 'SANDBOX / NO LIVE PAYMENT'}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Concurrent sandbox event; Stripe may retry safely') from None
    return {'received': True}
