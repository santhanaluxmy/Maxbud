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

async function withLoginClock(check) {
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  let expire;
  let cleared = false;
  globalThis.setTimeout = (callback, milliseconds) => {
    assert.equal(milliseconds, 15000);
    expire = callback;
    return 123;
  };
  globalThis.clearTimeout = timer => { assert.equal(timer, 123); cleared = true; };
  try { await check({ expire: () => expire(), cleared: () => cleared }); }
  finally { globalThis.setTimeout = originalSetTimeout; globalThis.clearTimeout = originalClearTimeout; }
}

test('a stalled sign-in fails promptly, aborts the request and leaves no session', async () => {
  const { loginUser, saveAuthSession, getAuthSession } = await import('../src/services/authApi.js');
  saveAuthSession(result, true);
  let signal;
  globalThis.fetch = (_url, options) => new Promise((_resolve, reject) => {
    signal = options.signal;
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  });
  await withLoginClock(async clock => {
    const pending = loginUser({ email: 'test@example.com', password: 'ExamplePassword123!' });
    clock.expire();
    await assert.rejects(pending, /Sign-in timed out/);
    assert.equal(signal.aborted, true);
    assert.equal(clock.cleared(), true);
    assert.equal(getAuthSession(), null);
  });
});

test('the deadline also covers a stalled JSON body after successful response headers', async () => {
  const { loginUser } = await import('../src/services/authApi.js');
  let readingBody = false;
  globalThis.fetch = async () => ({ ok: true, json() { readingBody = true; return new Promise(() => {}); } });
  await withLoginClock(async clock => {
    const pending = loginUser({ email: 'test@example.com', password: 'ExamplePassword123!' });
    await Promise.resolve();
    assert.equal(readingBody, true);
    clock.expire();
    await assert.rejects(pending, /Sign-in timed out/);
    assert.equal(clock.cleared(), true);
  });
});

test('Google sign-in also times out rather than leaving the empty login form busy', async () => {
  const { googleLogin } = await import('../src/services/authApi.js');
  let signal;
  globalThis.fetch = (url, options) => {
    assert.equal(url, '/api/auth/google');
    signal = options.signal;
    return new Promise(() => {});
  };
  await withLoginClock(async clock => {
    const pending = googleLogin('synthetic-google-id-token');
    clock.expire();
    await assert.rejects(pending, /Sign-in timed out/);
    assert.equal(signal.aborted, true);
    assert.equal(clock.cleared(), true);
  });
});

test('a successful sign-in clears its deadline and permits another login after logout', async () => {
  const { loginUser, saveAuthSession, getAuthSession } = await import('../src/services/authApi.js');
  globalThis.fetch = async () => Response.json(result);
  await withLoginClock(async clock => {
    const response = await loginUser({ email: 'test@example.com', password: 'ExamplePassword123!' });
    assert.equal(clock.cleared(), true);
    saveAuthSession(response);
    assert.equal(getAuthSession().token, result.access_token);
  });
  logout();
  assert.equal(getAuthSession(), null);
  await withLoginClock(async clock => {
    assert.equal((await loginUser({ email: 'test@example.com', password: 'ExamplePassword123!' })).access_token, result.access_token);
    assert.equal(clock.cleared(), true);
  });
});
