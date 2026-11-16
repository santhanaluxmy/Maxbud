import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { apiUrl, resolveApiBaseUrl } from '../src/api/base.js';
import { api, logout } from '../src/api/client.js';
import { saveAuthSession } from '../src/services/authApi.js';

function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
globalThis.sessionStorage = storage();
globalThis.localStorage = storage();
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; logout(); });

function authenticate() {
  saveAuthSession({ access_token: 'test-token', user: { id: 1 }, onboarding_completed: true });
}

test('all callers can use the same normalized local or hosted API base', () => {
  assert.equal(resolveApiBaseUrl(undefined), '/api');
  assert.equal(resolveApiBaseUrl('  '), '/api');
  assert.equal(resolveApiBaseUrl(' https://api.example.test/// '), 'https://api.example.test');
  assert.equal(resolveApiBaseUrl('/api/'), '/api');
  assert.equal(apiUrl('/accounts'), '/api/accounts');
  assert.equal(apiUrl('transactions?limit=100'), '/api/transactions?limit=100');
});

test('financial writes carry authentication, exact amounts and retry key through /api', async () => {
  authenticate();
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/transactions');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    assert.equal(options.headers['Idempotency-Key'], 'submit-once');
    assert.deepEqual(JSON.parse(options.body), { amount: '25.10', account_id: 1 });
    return Response.json({ id: 2 }, { status: 201 });
  };
  assert.deepEqual(await api('/transactions', { method: 'POST', requestId: 'submit-once', data: { amount: '25.10', account_id: 1 } }), { id: 2 });
});

test('backend validation errors reach the form with the HTTP status', async () => {
  authenticate();
  globalThis.fetch = async () => Response.json({ detail: [{ msg: 'Amount must be positive' }] }, { status: 422 });
  await assert.rejects(api('/goals'), error => error.status === 422 && error.message === 'Amount must be positive');
});

test('unauthenticated requests never reach the backend', async () => {
  globalThis.fetch = async () => { assert.fail('Unexpected network request'); };
  await assert.rejects(api('/accounts'), /Please sign in/);
});
