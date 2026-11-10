import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { register, login, getCurrentUser, logout } from '../src/api/auth.js';

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
  logout();
});

test('registration sends backend field names and omits confirmation password', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/auth/register');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), {
      full_name: 'Test User', email: 'test@example.com', password: 'ExamplePassword123',
    });
    return Response.json({ id: 1 }, { status: 201 });
  };
  await register({ fullName: ' Test User ', email: ' test@example.com ',
    password: 'ExamplePassword123', confirmPassword: 'never-send-this' });
});

test('login uses OAuth2 form encoding and verifies profile with bearer token', async () => {
  const profile = { id: 1, full_name: 'Test User' };
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/login')) {
      assert.equal(options.headers['Content-Type'], 'application/x-www-form-urlencoded');
      assert.equal(options.body.get('username'), 'test@example.com');
      assert.equal(options.body.get('password'), 'ExamplePassword123');
      assert.equal(options.body.get('grant_type'), 'password');
      return Response.json({ access_token: 'test-token' });
    }
    assert.equal(url, '/api/auth/me');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    return Response.json(profile);
  };
  assert.deepEqual(await login('test@example.com', 'ExamplePassword123'), profile);
});

test('duplicate email message is surfaced', async () => {
  globalThis.fetch = async () => Response.json(
    { detail: 'An account with this email already exists.' }, { status: 409 },
  );
  await assert.rejects(register({ fullName: 'Test User', email: 'test@example.com',
    password: 'ExamplePassword123' }), /already exists/);
});

test('failed login clears an earlier token', async () => {
  let rejectLogin = false;
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/login')) {
      return rejectLogin
        ? Response.json({ detail: 'Incorrect email or password.' }, { status: 401 })
        : Response.json({ access_token: 'earlier-token' });
    }
    if (rejectLogin) assert.equal(options.headers.Authorization, undefined);
    return Response.json({ id: 1 });
  };
  await login('test@example.com', 'ExamplePassword123');
  rejectLogin = true;
  await assert.rejects(login('test@example.com', 'wrong'), /Incorrect email or password/);
  await getCurrentUser();
});

test('unreachable server produces a usable error', async () => {
  globalThis.fetch = async () => { throw new TypeError('fetch failed'); };
  await assert.rejects(login('test@example.com', 'ExamplePassword123'), /Unable to reach MaxBud/);
});
