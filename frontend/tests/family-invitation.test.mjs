import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { captureInvitation, pendingInvitation, clearInvitation, authDestination } from '../src/services/familyInvitation.js';
import { saveAuthSession, getAuthSession } from '../src/services/authApi.js';
import { logout } from '../src/api/client.js';
import { publicPost } from '../src/api/public.js';

function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
globalThis.sessionStorage = storage();
globalThis.localStorage = storage();
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; clearInvitation(); logout(); });
const token = 'a'.repeat(43);

test('invitation survives registration, login and account switching in this tab', () => {
  assert.equal(captureInvitation('#invite=' + token), true);
  assert.equal(pendingInvitation(), token);
  const auth = { access_token: 'synthetic-token', user: { id: 2, role: 'user' }, onboarding_completed: false };
  assert.equal(authDestination(auth), '/invite');
  saveAuthSession(auth, false);
  assert.equal(pendingInvitation(), token);
  assert.equal(getAuthSession().user.id, 2);
  logout();
  assert.equal(pendingInvitation(), token);
  assert.equal(authDestination({ ...auth, onboarding_completed: true }), '/invite');
  clearInvitation();
  assert.equal(authDestination(auth), '/onboarding');
});

test('joined members return to shared household on subsequent login before personal onboarding', () => {
  assert.equal(authDestination({ has_household: true, onboarding_completed: false }), '/dashboard/family');
  assert.equal(authDestination({ has_household: true, onboarding_completed: true }), '/dashboard');
  assert.equal(authDestination({ user: { role: 'admin' }, has_household: true }), '/dashboard/admin');
});

test('malformed token fragments fail safely and ordinary anchors preserve invitations', () => {
  captureInvitation('#invite=' + token);
  assert.equal(captureInvitation('#pricing'), false);
  assert.equal(pendingInvitation(), token);
  for (const invalid of ['#invite=%E0%A4%A', '#invite=short', '#invite=' + '<'.repeat(40)]) {
    assert.doesNotThrow(() => captureInvitation(invalid));
    assert.equal(pendingInvitation(), null);
  }
});

test('public preview uses POST without requiring a login or putting tokens in the URL', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/family/invitations/preview');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.Authorization, undefined);
    assert.deepEqual(JSON.parse(options.body), { token });
    return Response.json({ household_name: 'Shared household', status: 'pending' });
  };
  assert.equal((await publicPost('/family/invitations/preview', { token })).status, 'pending');
});

test('public invitation errors preserve useful status and aborts do not become network errors', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'This invitation link is invalid.' }, { status: 404 });
  await assert.rejects(publicPost('/family/invitations/preview', { token }), error => error.status === 404 && /invalid/.test(error.message));
  globalThis.fetch = async () => { throw new DOMException('aborted', 'AbortError'); };
  await assert.rejects(publicPost('/family/invitations/preview', { token }), error => error.name === 'AbortError');
});
