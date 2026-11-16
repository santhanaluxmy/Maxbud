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
    assert.equal(url, '/api/auth/register');
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
    assert.equal(url, '/api/auth/me');
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

test('remember me selects exactly one storage location', async () => {
  const { saveAuthSession, getAuthSession } = await import('../src/services/authApi.js');
  saveAuthSession(result, true);
  assert.ok(localStorage.getItem('maxbud_auth'));
  assert.equal(sessionStorage.getItem('maxbud_auth'), null);
  assert.equal(getAuthSession().token, result.access_token);
  saveAuthSession(result, false);
  assert.ok(sessionStorage.getItem('maxbud_auth'));
  assert.equal(localStorage.getItem('maxbud_auth'), null);
});

test('expired sessions are removed before protected navigation', async () => {
  const { saveAuthSession, getAuthSession } = await import('../src/services/authApi.js');
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) - 60 })).toString('base64url');
  saveAuthSession({ ...result, access_token: `header.${payload}.signature` }, true);
  assert.equal(getAuthSession(), null);
  assert.equal(localStorage.getItem('maxbud_auth'), null);
  assert.equal(sessionStorage.getItem('maxbud_auth'), null);
});

test('wrong password returns the backend error and leaves no previous session', async () => {
  const { saveAuthSession } = await import('../src/services/authApi.js');
  saveAuthSession(result, true);
  globalThis.fetch = async () => Response.json({ detail: 'Invalid email or password' }, { status: 401 });
  await assert.rejects(login('test@example.com', 'wrong'), /Invalid email or password/);
  assert.equal(localStorage.getItem('maxbud_auth'), null);
  assert.equal(sessionStorage.getItem('maxbud_auth'), null);
});
