"""Stripe test-mode adapter. Never accepts live keys, prices, or objects."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import time
import requests
from fastapi import HTTPException
from app.core.config import get_settings
from app.services.subscriptions import catalog

API_VERSION = '2024-06-20'


def enabled():
    s = get_settings()
    return s.ENVIRONMENT in {'development', 'test', 'beta'} and s.STRIPE_SECRET_KEY.startswith(('sk_test_', 'rk_test_')) and bool(s.STRIPE_WEBHOOK_SECRET)


def call(method, path, data=None, key=None):
    if not enabled():
        raise HTTPException(503, 'Stripe sandbox is not configured. Live keys and production billing are not accepted.')
    s = get_settings()
    headers = {'Authorization': 'Bearer ' + s.STRIPE_SECRET_KEY, 'Stripe-Version': API_VERSION}
    if key:
        headers['Idempotency-Key'] = key
    try:
        response = requests.request(method, 'https://api.stripe.com/v1/' + path,
                                    headers=headers, data=data if method != 'GET' else None,
                                    params=data if method == 'GET' else None, timeout=20)
        if not response.ok:
            raise ValueError('Provider rejected request')
        result = response.json()
        sandbox = result.get('livemode') is False
        if method == 'GET' and path in {'billing_portal/configurations', 'events', 'webhook_endpoints'} and result.get('object') == 'list':
            sandbox = all(item.get('livemode') is False for item in result.get('data', []))
        if not sandbox:
            raise ValueError('Not a sandbox object')
        return result
    except (requests.RequestException, ValueError):
        raise HTTPException(502, 'Stripe sandbox could not complete the request. Check test-mode configuration; no access was granted.') from None


def price_id(plan, cycle):
    field = 'STRIPE_PRICE_' + ('PREMIUM' if plan == 'premium_individual' else 'FAMILY') + '_' + ('MONTHLY' if cycle == 'monthly' else 'YEARLY')
    value = getattr(get_settings(), field)
    if not value.startswith('price_'):
        raise HTTPException(503, 'The selected Stripe sandbox Price ID is not configured.')
    return value


def subscription_id(obj):
    """Invoice webhooks use parent.subscription_details on Basil and later."""
    value = obj.get('subscription') or (obj.get('parent') or {}).get('subscription_details', {}).get('subscription')
    return value.get('id') if isinstance(value, dict) else value


def validate_price(price, plan, cycle):
    offer = next(row for row in catalog()['plans'] if row['id'] == plan)
    expected = offer['prices'].get(cycle)
    recurring = price.get('recurring') or {}
    if expected is None or price.get('livemode') is not False or price.get('active') is not True or price.get('currency') != 'lkr' or price.get('unit_amount') != int(Decimal(expected) * 100) or recurring.get('interval') != ('month' if cycle == 'monthly' else 'year') or recurring.get('interval_count', 1) != 1:
        raise HTTPException(503, 'Stripe Price does not match the configured LKR amount and billing period. Replace the sandbox Price ID; no access was granted.')


def selection(price):
    for plan in ['premium_individual', 'family_pack']:
        for cycle in ['monthly', 'yearly']:
            try:
                key = price_id(plan, cycle)
            except HTTPException:
                continue
            if price.get('id') == key:
                validate_price(price, plan, cycle)
                return plan, cycle
    raise HTTPException(409, 'Subscription uses an unrecognized sandbox price; reconcile its configuration.')


def signature(raw, header):
    if not enabled():
        raise HTTPException(503, 'Stripe sandbox webhook is not configured.')
    try:
        values = [part.split('=', 1) for part in header.split(',')]
        timestamp = next(value for key, value in values if key == 't')
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
        signed = timestamp.encode() + b'.' + raw
        expected = hmac.new(get_settings().STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
        if not any(key == 'v1' and hmac.compare_digest(value, expected) for key, value in values):
            raise ValueError()
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get('livemode') is not False or not isinstance(event.get('id'), str) or not isinstance(event.get('data', {}).get('object'), dict):
            raise ValueError()
        return event
    except (ValueError, TypeError, StopIteration, KeyError, AttributeError):
        raise HTTPException(400, 'Invalid Stripe webhook signature or sandbox event.') from None


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
