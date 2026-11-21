import assert from 'node:assert/strict';
import { test } from 'node:test';
import { verifiedCheckoutDestination } from '../src/subscriptions/checkoutNavigation.js';

test('only verified Stripe activation selects the purchased plan destination', () => {
  for (const [plan, path] of [['premium_individual', '/dashboard'], ['family_pack', '/dashboard/family']]) {
    const result = { activation: 'active', subscription: { plan, source: 'stripe_test', status: 'active' } };
    assert.equal(verifiedCheckoutDestination(result), path);
    for (const activation of ['pending', 'failed', 'canceled']) {
      assert.equal(verifiedCheckoutDestination({ ...result, activation }), null);
    }
    for (const source of ['trial', 'demo', 'test_access']) {
      assert.equal(verifiedCheckoutDestination({ ...result, subscription: { ...result.subscription, source } }), null);
    }
    assert.equal(verifiedCheckoutDestination({ ...result, subscription: { ...result.subscription, status: 'past_due' } }), null);
  }
  assert.equal(verifiedCheckoutDestination({ paid: true, plan: 'family_pack', success: true }), null);
  assert.equal(verifiedCheckoutDestination({ activation: 'active', subscription: { plan: 'trial', source: 'stripe_test', status: 'active' } }), null);
  assert.equal(verifiedCheckoutDestination(null), null);
  assert.equal(verifiedCheckoutDestination({ activation: 'active', subscription: { plan: 'constructor', source: 'stripe_test', status: 'active' } }), null);
});
