import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { createServer } from 'vite';

test('membership cards expose only monthly purchases, correct current plan and verified confirmation', async () => {
  const server = await createServer({ server: { middlewareMode: true, watch: null }, appType: 'custom' });
  try {
    const { default: Upgrade } = await server.ssrLoadModule('/src/pages/userdashboard/dashboard/Upgrade.jsx');
    const { default: PaymentSuccess } = await server.ssrLoadModule('/src/pages/userdashboard/dashboard/PaymentSuccess.jsx');
    const { SubscriptionContext } = await server.ssrLoadModule('/src/subscriptions/SubscriptionContext.js');
    const basic = { receipt_scans: 5, advisor_messages: 10, active_goals: 3, family_members: 0 };
    const premium = { receipt_scans: 100, advisor_messages: 200, active_goals: 20, family_members: 0 };
    const catalog = { currency: 'LKR', stripe_test_enabled: true, checkout_available: { premium_individual: true, family_pack: true }, plans: [
      { id: 'trial', name: 'Free Trial', prices: { monthly: '0.00' }, limits: basic },
      { id: 'premium_individual', name: 'Premium Individual', prices: { monthly: '650.00' }, limits: premium },
      { id: 'family_pack', name: 'Family Pack', prices: { monthly: '900.00' }, limits: { ...premium, family_members: 5 } },
    ] };
    function render(overrides = {}, Component = Upgrade, entry = '/dashboard/upgrade') {
      const subscription = { plan: 'trial', source: 'trial', status: 'trialing', billing_status: 'trialing', can_edit: true, limits: basic, catalog, ...overrides };
      return renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [entry] }, createElement(SubscriptionContext.Provider, { value: { subscription, usage: { used: { receipt_scans: 3, advisor_messages: 2 }, limits: subscription.limits }, error: '', refresh: async () => subscription } }, createElement(Component))));
    }
    const trial = render();
    assert.match(trial, /Upgrade to Premium/);
    assert.match(trial, /Choose Family Pack/);
    assert.match(trial, /LKR 650/);
    assert.match(trial, /LKR 900/);
    assert.match(trial, /Test mode/);
    assert.doesNotMatch(trial, /yearly|Demo checkout|Subscribe in Stripe|Manage sandbox/);
    for (const plan of ['premium_individual', 'family_pack']) {
      const paid = render({ plan, source: 'stripe_test', status: 'active', billing_status: 'active', stripe_subscription_exists: true, billing_portal_available: true, limits: premium, expires_at: '2027-01-01T00:00:00' });
      assert.match(paid, /disabled="">Current Plan/);
      assert.match(paid, /Manage Subscription/);
      assert.match(paid, /Renews/);
      assert.match(paid, /3 \/ 100/);
      assert.doesNotMatch(paid, />Upgrade to Premium<|>Choose Family Pack</);
    }
    const confirmation = render({}, PaymentSuccess);
    assert.match(confirmation, /Activating your subscription/);
    assert.doesNotMatch(confirmation, /Premium Active|Family Pack Active|Go to Dashboard/);
    for (const [reason, message] of [['failed', /Checkout was not successful/], ['canceled', /Checkout was canceled or expired/], ['pending', /Do not make another payment/], ['error', /We could not verify your subscription/]]) {
      assert.match(render({}, Upgrade, '/dashboard/upgrade?checkout=' + reason), message);
    }
  } finally { await server.close(); }
});
