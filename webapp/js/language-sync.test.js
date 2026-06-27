const assert = require('node:assert/strict');

const ALLOWED = new Set(['ru', 'uz', 'en']);
function normalizeLanguageCode(lang) {
  const value = String(lang || '').toLowerCase();
  if (value.startsWith('ru')) return 'ru';
  if (value.startsWith('uz')) return 'uz';
  if (value.startsWith('en')) return 'en';
  return 'ru';
}
function validateLanguageCode(lang) {
  const normalized = normalizeLanguageCode(lang);
  if (!ALLOWED.has(normalized)) throw new Error('invalid language');
  return normalized;
}
function validateBackendLanguageCode(lang) {
  const value = String(lang || '').toLowerCase();
  if (!ALLOWED.has(value)) throw new Error('invalid language');
  return value;
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function createHarness(apiImpl) {
  const applied = [];
  const state = {
    token: null,
    authReady: false,
    user: null,
    pendingLanguageSave: null,
    languageSaveInFlight: false,
  };

  function applyLanguageLocally(lang, source = 'system') {
    const normalized = validateLanguageCode(lang);
    applied.push({ lang: normalized, source });
    return normalized;
  }

  function applyLanguageFromProfile(profile) {
    const profileLang = profile?.language_code;
    if (!profileLang) return;

    if (state.pendingLanguageSave) {
      const pendingLang = validateLanguageCode(state.pendingLanguageSave);
      state.user = { ...(state.user || {}), ...(profile || {}), language_code: pendingLang };
      applyLanguageLocally(pendingLang, 'pending');
      return;
    }

    const normalized = applyLanguageLocally(profileLang, 'profile');
    state.user = { ...(state.user || {}), ...(profile || {}), language_code: normalized };
  }

  async function saveSelectedLanguage(lang) {
    const normalized = validateLanguageCode(lang);
    state.pendingLanguageSave = normalized;

    if (!state.token || !state.authReady || state.languageSaveInFlight) return;

    state.languageSaveInFlight = true;
    try {
      while (state.pendingLanguageSave && state.token && state.authReady) {
        const langToSave = state.pendingLanguageSave;
        state.pendingLanguageSave = null;
        const profile = await apiImpl('PATCH', '/users/language', { language_code: langToSave });

        if (!state.pendingLanguageSave) {
          state.user = { ...(state.user || {}), ...(profile || {}), language_code: langToSave };
          applyLanguageLocally(langToSave, 'saved');
        }
      }
    } finally {
      state.languageSaveInFlight = false;
    }
  }

  async function flushPendingLanguageSave() {
    if (!state.pendingLanguageSave || !state.token || !state.authReady) return;
    await saveSelectedLanguage(state.pendingLanguageSave);
  }

  return { state, applied, applyLanguageFromProfile, saveSelectedLanguage, flushPendingLanguageSave };
}

async function run() {
  {
    const calls = [];
    const harness = createHarness(async (...args) => { calls.push(args); return { language_code: args[2].language_code }; });
    harness.state.token = 'token';
    harness.state.authReady = true;
    harness.applyLanguageFromProfile({ id: 1, language_code: 'uz' });
    assert.equal(calls.length, 0, 'profile language must not PATCH');
    assert.equal(harness.state.user.language_code, 'uz');
    assert.deepEqual(harness.applied.at(-1), { lang: 'uz', source: 'profile' });
  }

  {
    const calls = [];
    const harness = createHarness(async (...args) => { calls.push(args); return { id: 1, language_code: args[2].language_code }; });
    harness.state.token = 'token';
    harness.state.authReady = true;
    await harness.saveSelectedLanguage('en');
    assert.equal(calls.length, 1, 'manual language selection must PATCH once');
    assert.deepEqual(calls[0], ['PATCH', '/users/language', { language_code: 'en' }]);
    assert.equal(harness.state.user.language_code, 'en');
    assert.deepEqual(harness.applied.at(-1), { lang: 'en', source: 'saved' });
  }

  {
    const calls = [];
    const harness = createHarness(async (...args) => { calls.push(args); return { id: 1, language_code: args[2].language_code }; });
    await harness.saveSelectedLanguage('uz');
    harness.applyLanguageFromProfile({ id: 1, language_code: 'ru' });
    assert.equal(harness.state.user.language_code, 'uz', 'old profile language must not overwrite pending user choice');
    assert.deepEqual(harness.applied.at(-1), { lang: 'uz', source: 'pending' });
    harness.state.token = 'token';
    harness.state.authReady = true;
    await harness.flushPendingLanguageSave();
    assert.equal(calls.length, 1);
    assert.equal(calls[0][2].language_code, 'uz');
    assert.equal(harness.state.user.language_code, 'uz');
  }

  {
    const first = deferred();
    const calls = [];
    const harness = createHarness(async (...args) => {
      calls.push(args);
      if (calls.length === 1) return first.promise;
      return { id: 1, language_code: args[2].language_code };
    });
    harness.state.token = 'token';
    harness.state.authReady = true;
    const saving = harness.saveSelectedLanguage('uz');
    await Promise.resolve();
    const queued = harness.saveSelectedLanguage('en');
    assert.equal(calls.length, 1, 'second selection is queued while first PATCH is in flight');
    first.resolve({ id: 1, language_code: 'uz' });
    await Promise.all([saving, queued]);
    assert.equal(calls.length, 2, 'queued latest selection is persisted after in-flight PATCH');
    assert.equal(calls[0][2].language_code, 'uz');
    assert.equal(calls[1][2].language_code, 'en');
    assert.equal(harness.state.user.language_code, 'en');
    assert.deepEqual(harness.applied.at(-1), { lang: 'en', source: 'saved' });
  }

  assert.equal(validateBackendLanguageCode('ru'), 'ru');
  assert.equal(validateBackendLanguageCode('uz'), 'uz');
  assert.equal(validateBackendLanguageCode('en'), 'en');
  assert.throws(() => validateBackendLanguageCode('de'));
}

run().then(() => console.log('language sync tests passed'));
