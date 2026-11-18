"""Read-only audit by default. --apply reconciles one verified existing sandbox purchase.

From backend: PYTHONPATH=. .venv/bin/python scripts/verify_stripe_subscription.py --user-id ID
Add --apply only to persist that user's provider-verified subscription. No payment,
customer, checkout, portal configuration, or Stripe subscription is created/changed.
"""
import argparse
import hashlib
import json
import hmac
import subprocess
import tempfile
import time
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.access import StripeAccount, StripeEvent
from app.models.family import Subscription
from app.models.platform import PlatformEvent
from app.models.user import User, now_utc
from app.routers.ai import usage
from app.routers.billing import reconcile, validate_portal_configuration
from app.services import stripe_test as stripe
from app.services.subscriptions import entitlement


def emit(name, value):
    print(name + ': ' + json.dumps(value, default=str), flush=True)


def other_subscriptions(db, user_id):
    rows = db.execute(select(Subscription.__table__).where(Subscription.user_id != user_id).order_by(Subscription.id)).all()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def audit(user_id, apply=False, probe_url=None, local_http_check=False):
    if not stripe.enabled():
        raise ValueError('A test-mode Stripe key, signing secret, and development/test/beta environment are required.')
    with SessionLocal() as db:
        tables = inspect(db.connection())
        for name in ['subscriptions','stripe_test_accounts','stripe_test_events']:
            if not tables.has_table(name):
                raise ValueError('Required billing migration is missing: ' + name)
        emit('migration_revisions', list(db.execute(text('SELECT version_num FROM alembic_version')).scalars()))
        user = db.get(User, user_id)
        account = db.get(StripeAccount, user_id)
        if not user or not account or not account.checkout_id:
            raise ValueError('The selected user has no persisted Stripe checkout mapping; nothing was changed.')
        checkout = stripe.call('GET','checkout/sessions/'+account.checkout_id)
        customer = stripe.call('GET','customers/'+account.customer_id)
        key = stripe.subscription_id(checkout)
        if not isinstance(key,str) or not key.startswith('sub_'):
            raise ValueError('The saved checkout does not have a subscription yet; nothing was changed.')
        state = stripe.call('GET','subscriptions/'+key,{'expand[]':'latest_invoice'})
        invoice = state.get('latest_invoice') or {}
        items = state.get('items',{}).get('data',[])
        if len(items) != 1:
            raise ValueError('Unsupported subscription items; nothing was changed.')
        plan, cycle = stripe.selection(items[0]['price'])
        end = state.get('current_period_end') or items[0].get('current_period_end')
        checks = {
            'user_active': bool(user.is_active),
            'customer_test_mode':customer.get('livemode') is False,
            'customer_metadata_owner':customer.get('metadata',{}).get('maxbud_user_id') == str(user_id),
            'customer_email_matches':str(customer.get('email','')).strip().lower() == user.email.strip().lower(),
            'checkout_test_mode':checkout.get('livemode') is False,
            'checkout_id_matches':checkout.get('id') == account.checkout_id,
            'checkout_customer_matches':checkout.get('customer') == account.customer_id,
            'checkout_reference_owner':checkout.get('client_reference_id') == str(user_id),
            'checkout_completed_paid':checkout.get('status') == 'complete' and checkout.get('payment_status') == 'paid',
            'checkout_subscription_mode':checkout.get('mode') == 'subscription',
            'subscription_test_mode':state.get('livemode') is False,
            'subscription_customer_matches':state.get('customer') == account.customer_id,
            'subscription_metadata_owner':state.get('metadata',{}).get('maxbud_user_id') == str(user_id),
            'subscription_active':state.get('status') == 'active',
            'subscription_id_matches':state.get('id') == key,
            'invoice_test_mode':invoice.get('livemode') is False,
            'invoice_paid':invoice.get('status') == 'paid' and invoice.get('paid') is True,
            'invoice_customer_matches':invoice.get('customer') == account.customer_id,
            'invoice_subscription_matches':stripe.subscription_id(invoice) == key,
            'monthly_supported_price':cycle == 'monthly',
            'paid_through_future':bool(end and stripe.utc(end) > now_utc()),
        }
        emit('ownership_and_payment_checks',checks)
        emit('verified_purchase',{'user_id':user_id,'plan':plan,'cycle':cycle,'paid_through':stripe.utc(end) if end else None})
        before_usage = usage(db,user)
        before_others = other_subscriptions(db,user_id)
        before = entitlement(db,user)
        emit('before',{'plan':before['plan'],'source':before['source'],'status':before['status'],'usage':before_usage,'event_count':db.query(StripeEvent).count()})
        try:
            endpoints = stripe.call('GET','webhook_endpoints',{'limit':100})
            emit('registered_webhook_endpoints',[{'status':e.get('status'),'url':urlsplit(e.get('url',''))._replace(netloc=urlsplit(e.get('url','')).hostname or '',query='',fragment='').geturl(),'events':e.get('enabled_events'),'api_version':e.get('api_version')} for e in endpoints.get('data',[])])
        except HTTPException as exc:
            emit('webhook_endpoint_audit',{'status':'NOT VERIFIED','http_status':exc.status_code})
        events = {}
        try:
            events = stripe.call('GET','events',{'limit':100})
            matching = [e for e in events.get('data',[]) if e.get('data',{}).get('object',{}).get('customer') == account.customer_id]
            emit('matching_recent_stripe_events',[{'id':e['id'],'type':e.get('type'),'created':e.get('created'),'pending_webhooks':e.get('pending_webhooks'),'api_version':e.get('api_version')} for e in matching])
        except HTTPException as exc:
            emit('stripe_event_audit',{'status':'NOT VERIFIED','http_status':exc.status_code})
        try:
            config = validate_portal_configuration()
            emit('portal',{'available':True,'default':config.get('is_default'),'features':config.get('features')})
        except HTTPException as exc:
            emit('portal',{'available':False,'http_status':exc.status_code,'reason':exc.detail})
        listeners = []
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                args = path.read_bytes().decode(errors='ignore').split('\0')
                if args and Path(args[0]).name == 'stripe' and 'listen' in args:
                    forward = next((args[i+1] for i,a in enumerate(args[:-1]) if a=='--forward-to'),None)
                    listeners.append({'forward_to':forward})
            except (OSError,IndexError):
                continue
        emit('stripe_cli_listeners',listeners)
        if probe_url:
            parsed = urlsplit(probe_url)
            if parsed.scheme != 'http' or parsed.hostname not in {'localhost','127.0.0.1'} or parsed.path not in {'','/'} or parsed.username or parsed.password or parsed.query:
                raise ValueError('HTTP probes require a loopback HTTP origin.')
            try:
                response = requests.post(probe_url.rstrip('/')+'/billing/stripe/webhook',data=b'{}',headers={'Stripe-Signature':'invalid'},timeout=10)
                emit('invalid_signature_http_probe',{'http_status':response.status_code,'correct_rejection':response.status_code==400})
            except requests.RequestException:
                emit('invalid_signature_http_probe',{'status':'NOT VERIFIED','reason':'No reachable server at the requested loopback origin.'})
        if not all(checks.values()):
            raise ValueError('Ownership/payment verification failed; no reconciliation was applied.')
        if apply:
            db.add(PlatformEvent(user_id=user_id,kind='stripe_subscription_reconciled',target=key,
                                 details={'method':'verified_operator_reconciliation','billing_mode':'stripe_test'}))
            result = reconcile(user=user,db=db)
            if result['activation'] != 'active':
                raise ValueError('Provider reconciliation did not activate the verified purchase.')
            emit('applied',{'user_id':user_id,'activation':result['activation']})
        else:
            emit('applied',False)
    if apply:
        with SessionLocal() as fresh:
            user = fresh.get(User,user_id)
            rights = entitlement(fresh,user)
            after_usage = usage(fresh,user)
            emit('fresh_connection_verification',{'user_id':user_id,'plan':rights['plan'],'source':rights['source'],'status':rights['status'],'limits':rights['limits'],'usage':after_usage,'usage_preserved':after_usage==before_usage,'other_subscriptions_unchanged':other_subscriptions(fresh,user_id)==before_others,'subscription_rows':fresh.query(Subscription).filter_by(user_id=user_id).count()})
            assert after_usage == before_usage, 'Monthly usage unexpectedly changed'
            assert other_subscriptions(fresh,user_id) == before_others, 'Other subscriptions unexpectedly changed'
            assert rights['plan'] == plan and rights['source'] == 'stripe_test', 'Persisted entitlement did not match Stripe'
        if local_http_check:
            matching = [e for e in events.get('data',[]) if e.get('data',{}).get('object',{}).get('customer') == account.customer_id]
            event = next((e for e in matching if e.get('type') == 'invoice.paid' and stripe.subscription_id(e['data']['object']) == key),None)
            if event is None:
                raise ValueError('No matching provider invoice.paid event was available for the HTTP replay.')
            check_local_http(event,user_id,before_usage,plan)


def check_local_http(event,user_id,expected_usage,expected_plan):
    """Check HTTP/MySQL using an API-retrieved event signed locally.

    This is an operator replay, not evidence of Stripe CLI forwarding.
    """
    base='http://127.0.0.1:8897'
    with tempfile.TemporaryFile(mode='w+') as log:
        server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8897','--log-level','warning'],
                                cwd=Path(__file__).resolve().parents[1],stdout=log,stderr=log)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise ValueError('The temporary webhook verification server could not start.')
                try:
                    if requests.get(base+'/health',timeout=1).ok:break
                except requests.RequestException:pass
                time.sleep(.2)
            else:raise ValueError('The temporary webhook verification server did not become ready.')
            routes=requests.get(base+'/openapi.json',timeout=10).json().get('paths',{})
            emit('http_route_registered','post' in routes.get('/billing/stripe/webhook',{}))
            rejected=requests.post(base+'/billing/stripe/webhook',data=b'{}',headers={'Stripe-Signature':'invalid'},timeout=20)
            emit('invalid_signature_http_response',rejected.status_code)
            assert rejected.status_code==400,'Invalid signature was not rejected'
            raw=json.dumps(event,separators=(',',':')).encode()
            timestamp=str(int(time.time()))
            signature=hmac.new(get_settings().STRIPE_WEBHOOK_SECRET.encode(),timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
            headers={'Content-Type':'application/json','Stripe-Signature':f't={timestamp},v1={signature}'}
            first=requests.post(base+'/billing/stripe/webhook',data=raw,headers=headers,timeout=90)
            second=requests.post(base+'/billing/stripe/webhook',data=raw,headers=headers,timeout=90)
            emit('api_verified_local_event_replay',{'event_id':event['id'],'kind':event['type'],'first_http':first.status_code,'duplicate_http':second.status_code,'duplicate_detected':second.json().get('duplicate') is True,'stripe_cli_forwarding_verified':False})
            assert first.status_code==200 and second.status_code==200 and second.json().get('duplicate') is True,'Webhook replay failed'
            with SessionLocal() as fresh:
                user=fresh.get(User,user_id)
                saved=fresh.get(StripeEvent,event['id'])
                rights=entitlement(fresh,user)
                emit('http_database_commit',{'event_saved':saved is not None,'plan':rights['plan'],'usage_preserved':usage(fresh,user)==expected_usage})
                assert saved is not None and rights['plan']==expected_plan and usage(fresh,user)==expected_usage,'Webhook database verification failed'
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill();server.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id',type=int,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--probe-url')
    parser.add_argument('--local-http-check',action='store_true',help='With --apply, replay a verified existing invoice.paid event through a temporary local FastAPI server.')
    args = parser.parse_args()
    try:
        if args.local_http_check and not args.apply:
            raise ValueError('--local-http-check requires --apply because a verified webhook audit event will be persisted.')
        audit(args.user_id,args.apply,args.probe_url,args.local_http_check)
    except HTTPException as exc:
        emit('error',{'http_status':exc.status_code,'reason':exc.detail})
        raise SystemExit(1) from None
    except Exception as exc:
        # Never print provider responses, credentials or database connection URLs.
        emit('error',{'type':type(exc).__name__,'reason':str(exc) if isinstance(exc,(ValueError,AssertionError)) else 'Audit could not complete; no unverified entitlement was granted.'})
        raise SystemExit(1) from None
