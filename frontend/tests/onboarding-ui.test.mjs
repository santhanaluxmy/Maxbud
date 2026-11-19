import assert from 'node:assert/strict';
import { test } from 'node:test';
import { visibleStep, budgetComparison } from '../src/pages/onboarding/onboardingUi.js';

test('new and legacy stored onboarding steps resume at the corresponding four-step page', () => {
  assert.deepEqual([1, 2, 3, 4, 5].map(visibleStep), [1, 2, 2, 3, 4]);
  assert.equal(visibleStep(), 1);
});

test('allocation guidance uses opening balances and keeps currency precision without mutating accounts', () => {
  const accounts = [{ opening_balance: '1000.10', current_balance: '900' }, { opening_balance: '500.20' }];
  const original = structuredClone(accounts);
  assert.deepEqual(budgetComparison(accounts, [{ monthly_limit: '1000' }]), { opening: 1500.3, allocated: 1000, difference: 500.3 });
  assert.equal(budgetComparison(accounts, [{ monthly_limit: '1500.30' }]).difference, 0);
  assert.equal(budgetComparison(accounts, [{ monthly_limit: '2000' }]).difference, -499.7);
  assert.deepEqual(accounts, original);
});
