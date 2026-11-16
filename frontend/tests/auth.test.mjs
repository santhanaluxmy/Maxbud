import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { register, login, getCurrentUser, logout } from '../src/api/auth.js';

function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
globalThis.localStorage = storage();
globalThis.sessionStorage = storage();
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; logout(); });
const result = { access_token: 'test-token', user: { id: 1, full_name: 'Test User' }, onboarding_completed: false };

test('registration sends validated JSON contract including password confirmation', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/auth/register');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { full_name: 'Test User', email: 'test@example.com', password: 'ExamplePassword123!', confirm_password: 'ExamplePassword123!' });
    return Response.json(result, { status: 201 });
  };
  await register({ fullName: ' Test User ', email: ' TEST@example.com ', password: 'ExamplePassword123!', confirmPassword: 'ExamplePassword123!' });
});

test('login uses backend JSON contract and profile uses bearer token', async () => {
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/login')) {
      assert.equal(options.headers['Content-Type'], 'application/json');
      assert.deepEqual(JSON.parse(options.body), { email: 'test@example.com', password: 'ExamplePassword123!' });
      return Response.json(result);
    }
    assert.equal(url, 'http://127.0.0.1:8000/auth/me');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    return Response.json(result.user);
  };
  assert.deepEqual(await login(' TEST@example.com ', 'ExamplePassword123!'), result.user);
  assert.deepEqual(await getCurrentUser(), result.user);
});

test('duplicate email message is surfaced', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Email already registered' }, { status: 409 });
  await assert.rejects(register({ fullName: 'Test User', email: 'test@example.com', password: 'ExamplePassword123!' }), /already registered/);
});

test('logout removes remembered and session credentials', async () => {
  globalThis.fetch = async () => Response.json(result);
  await login('test@example.com', 'ExamplePassword123!');
  logout();
  await assert.rejects(getCurrentUser(), /sign in first/);
});

test('unreachable server produces a usable error', async () => {
  globalThis.fetch = async () => { throw new TypeError('fetch failed'); };
  await assert.rejects(login('test@example.com', 'ExamplePassword123!'), /Cannot connect to MaxBud/);
});
