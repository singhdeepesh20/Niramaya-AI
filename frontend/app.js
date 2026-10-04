const REQUEST_TIMEOUT_MS = 10_000;
// Keep bearer credentials in memory so they are cleared when this tab is closed or refreshed.
let accessToken = null;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function readableDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return null;

  return detail
    .map((issue) => issue?.msg)
    .filter(Boolean)
    .join(' ');
}

async function requestJson(url, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json().catch(() => null)
      : null;

    if (!response.ok) {
      const detail = readableDetail(payload?.detail);
      throw new ApiError(detail || `The request failed (${response.status}).`, response.status);
    }

    if (payload === null) {
      throw new ApiError('The server returned an unreadable response.', response.status);
    }
    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === 'AbortError') {
      throw new Error('The request took too long. Check the connection and try again.');
    }
    throw new Error('Could not reach the API. Check that the backend is running.');
  } finally {
    window.clearTimeout(timeout);
  }
}

function showMessage(element, message, kind = 'error') {
  element.textContent = message;
  element.dataset.kind = kind;
  element.hidden = false;
}

function clearMessage(element) {
  element.textContent = '';
  element.hidden = true;
  delete element.dataset.kind;
}

function setButtonLoading(button, loading, loadingLabel) {
  const label = button.querySelector('.button-text');
  if (label) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = label.textContent;
    label.textContent = loading ? loadingLabel : button.dataset.idleLabel;
  }
  button.disabled = loading;
  button.classList.toggle('is-loading', loading);
  button.setAttribute('aria-busy', String(loading));
}

function setFormBusy(form, busy) {
  form.setAttribute('aria-busy', String(busy));
  form.querySelectorAll('input').forEach((input) => {
    input.disabled = busy;
  });
}

const footerYear = document.querySelector('#footer-year');
if (footerYear) footerYear.textContent = new Date().getFullYear();

const THEME_STORAGE_KEY = 'niramaya-theme';
const themeToggle = document.querySelector('#theme-toggle');
const themeColorMeta = document.querySelector('meta[name="theme-color"]');
const systemThemePreference = window.matchMedia('(prefers-color-scheme: dark)');

function readThemePreference() {
  try {
    const preference = window.localStorage.getItem(THEME_STORAGE_KEY);
    return preference === 'light' || preference === 'dark' ? preference : null;
  } catch {
    return null;
  }
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute('aria-pressed', String(isDark));
  themeToggle.setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme');
  themeToggle.title = isDark ? 'Switch to light theme' : 'Switch to dark theme';
  themeColorMeta.content = isDark ? '#111b18' : '#f3f7f4';
}

applyTheme(readThemePreference() || (systemThemePreference.matches ? 'dark' : 'light'));

themeToggle.addEventListener('click', () => {
  const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch {
    // Theme switching still works for this page when storage is unavailable.
  }
});

systemThemePreference.addEventListener('change', (event) => {
  if (!readThemePreference()) applyTheme(event.matches ? 'dark' : 'light');
});

window.addEventListener('storage', (event) => {
  if (event.key !== THEME_STORAGE_KEY) return;
  const theme = event.newValue === 'dark' || event.newValue === 'light'
    ? event.newValue
    : systemThemePreference.matches ? 'dark' : 'light';
  applyTheme(theme);
});

const healthResult = document.querySelector('#health-result');
const healthText = document.querySelector('#health-text');
const healthDetail = document.querySelector('#health-detail');
const healthLatency = document.querySelector('#health-latency');
const healthStateLabel = document.querySelector('#health-state-label');
const lastChecked = document.querySelector('#last-checked');
const healthButton = document.querySelector('#health-button');
const autoCheckInput = document.querySelector('#auto-check');
let healthCheckInFlight = false;
let healthPollingTimer = null;

function renderHealth(state, title, detail, label) {
  healthResult.dataset.state = state;
  healthResult.setAttribute('aria-busy', String(state === 'checking'));
  healthText.textContent = title;
  healthDetail.textContent = detail;
  healthStateLabel.textContent = label;
}

function setHealthButtonLoading(loading) {
  const label = healthButton.querySelector('span');
  if (!healthButton.dataset.idleLabel) healthButton.dataset.idleLabel = label.textContent;
  label.textContent = loading ? 'Checking…' : healthButton.dataset.idleLabel;
  healthButton.disabled = loading;
  healthButton.classList.toggle('is-loading', loading);
  healthButton.setAttribute('aria-busy', String(loading));
}

async function checkHealth() {
  if (healthCheckInFlight) return;
  healthCheckInFlight = true;
  const startedAt = performance.now();
  renderHealth('checking', 'Checking connection', 'Contacting the health endpoint…', 'Checking');
  setHealthButtonLoading(true);

  try {
    const payload = await requestJson('/health');
    const connected = payload.status === 'ok' && payload.database === 'connected';
    if (!connected) throw new Error('The API responded, but the database is not connected.');

    renderHealth('connected', 'Database connected', 'PostgreSQL responded successfully.', 'Connected');
  } catch (error) {
    renderHealth('unavailable', 'Connection unavailable', error.message, 'Unavailable');
  } finally {
    healthLatency.textContent = `${Math.round(performance.now() - startedAt)} ms`;
    healthLatency.hidden = false;
    lastChecked.textContent = `Last checked at ${new Intl.DateTimeFormat(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date())}`;
    setHealthButtonLoading(false);
    healthCheckInFlight = false;
  }
}

function syncHealthPolling() {
  window.clearInterval(healthPollingTimer);
  healthPollingTimer = null;
  if (autoCheckInput.checked && document.visibilityState === 'visible') {
    healthPollingTimer = window.setInterval(checkHealth, 30_000);
  }
}

autoCheckInput.addEventListener('change', syncHealthPolling);
healthButton.addEventListener('click', checkHealth);
syncHealthPolling();
checkHealth();

document.addEventListener('visibilitychange', () => {
  syncHealthPolling();
  if (document.visibilityState === 'visible' && autoCheckInput.checked) checkHealth();
});

window.addEventListener('offline', () => {
  renderHealth('unavailable', 'Browser is offline', 'Reconnect to the internet to reach the API.', 'Offline');
});

window.addEventListener('online', () => {
  checkHealth();
});

const createForm = document.querySelector('#create-form');
const createMessage = document.querySelector('#create-message');
const createButton = createForm.querySelector('button[type="submit"]');
const lookupIdInput = document.querySelector('#user-id');
const authModeToggle = document.querySelector('#auth-mode-toggle');
const logoutButton = document.querySelector('#logout-button');
const nameField = document.querySelector('#name-field');
const emailField = document.querySelector('#email-field');
const emailInput = document.querySelector('#email');
const usernameInput = document.querySelector('#username');
const passwordInput = document.querySelector('#password');
let registering = true;

authModeToggle.addEventListener('click', () => {
  registering = !registering;
  nameField.hidden = !registering;
  emailField.hidden = !registering;
  emailInput.required = registering;
  emailInput.disabled = !registering;
  document.querySelector('#name').required = registering;
  passwordInput.autocomplete = registering ? 'new-password' : 'current-password';
  passwordInput.minLength = registering ? 12 : 1;
  createForm.querySelector('.button-text').textContent = registering ? 'Create account' : 'Sign in';
  authModeToggle.textContent = registering ? 'Already registered? Sign in' : 'New here? Create an account';
  clearMessage(createMessage);
});

logoutButton.addEventListener('click', () => {
  accessToken = null;
  logoutButton.hidden = true;
  lookupIdInput.value = '';
  userResult.hidden = true;
  currentUser = null;
  showMessage(createMessage, 'Signed out. Sign in again to access your profile.', 'success');
});

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage(createMessage);
  const formData = new FormData(createForm);
  setFormBusy(createForm, true);
  setButtonLoading(createButton, true, registering ? 'Creating account…' : 'Signing in…');

  const email = String(formData.get('email') || '').trim();
  const username = String(formData.get('username') || '').trim();
  const password = String(formData.get('password') || '');

  try {
    if (registering) {
      await requestJson('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: String(formData.get('name') || '').trim(),
          username,
          email,
          password,
        }),
      });
    }
    const token = await requestJson('/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }).toString(),
    });
    accessToken = token.access_token;
    const user = await requestJson('/auth/me');
    showMessage(createMessage, `Signed in successfully. Profile ID: ${user.id}.`, 'success');
    logoutButton.hidden = false;
    createForm.reset();
    lookupIdInput.value = user.id;
    renderUser(user);
  } catch (error) {
    showMessage(createMessage, error.message);
  } finally {
    setFormBusy(createForm, false);
    setButtonLoading(createButton, false);
  }
});

const lookupForm = document.querySelector('#lookup-form');
const lookupMessage = document.querySelector('#lookup-message');
const lookupButton = lookupForm.querySelector('button[type="submit"]');
const userResult = document.querySelector('#user-result');
let currentUser = null;

function createResultField(label, value) {
  const field = document.createElement('div');
  field.className = 'result-field';
  const fieldLabel = document.createElement('span');
  fieldLabel.textContent = label;
  const fieldValue = document.createElement('strong');
  fieldValue.textContent = value;
  field.append(fieldLabel, fieldValue);
  return field;
}

function formatCreatedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Timestamp unavailable';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function renderUser(user) {
  currentUser = user;
  const heading = document.createElement('div');
  heading.className = 'user-result-heading';

  const initials = user.name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  const avatar = document.createElement('span');
  avatar.className = 'user-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = initials || 'U';

  const title = document.createElement('div');
  title.className = 'user-result-title';
  const name = document.createElement('strong');
  name.textContent = user.name;
  const id = document.createElement('small');
  id.textContent = `Profile ID ${user.id}`;
  title.append(name, id);

  const copyButton = document.createElement('button');
  copyButton.className = 'copy-id-button';
  copyButton.type = 'button';
  copyButton.dataset.copyId = user.id;
  copyButton.setAttribute('aria-label', `Copy profile ID ${user.id}`);
  copyButton.textContent = 'Copy ID';

  const shareButton = document.createElement('button');
  shareButton.className = 'copy-id-button';
  shareButton.type = 'button';
  shareButton.dataset.shareUser = user.id;
  shareButton.setAttribute('aria-label', `Copy a link to profile ${user.id}`);
  shareButton.textContent = 'Copy link';
  heading.append(avatar, title, copyButton, shareButton);

  const fields = document.createElement('div');
  fields.className = 'result-fields';
  fields.append(createResultField('Email', user.email));
  fields.append(createResultField('Username', user.username));
  fields.append(createResultField('Created', formatCreatedAt(user.created_at)));

  const actions = document.createElement('div');
  actions.className = 'user-result-actions';
  const exportButton = document.createElement('button');
  exportButton.className = 'result-action-button';
  exportButton.type = 'button';
  exportButton.dataset.exportUser = user.id;
  exportButton.textContent = 'Download JSON';
  const clearButton = document.createElement('button');
  clearButton.className = 'result-action-button result-action-secondary';
  clearButton.type = 'button';
  clearButton.dataset.clearResult = '';
  clearButton.textContent = 'Clear result';
  actions.append(exportButton, clearButton);

  userResult.replaceChildren(heading, fields, actions);
  userResult.hidden = false;
}

lookupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage(lookupMessage);
  userResult.hidden = true;
  currentUser = null;
  setFormBusy(lookupForm, true);
  setButtonLoading(lookupButton, true, 'Searching…');

  const id = lookupIdInput.value.trim();
  try {
    const user = await requestJson(`/users/${encodeURIComponent(id)}`);
    renderUser(user);
  } catch (error) {
    showMessage(lookupMessage, error.message);
  } finally {
    setFormBusy(lookupForm, false);
    setButtonLoading(lookupButton, false);
  }
});

createForm.addEventListener('input', () => clearMessage(createMessage));

lookupIdInput.addEventListener('input', () => {
  clearMessage(lookupMessage);
  userResult.hidden = true;
  currentUser = null;
});

userResult.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-id], [data-share-user], [data-export-user], [data-clear-result]');
  if (!button) return;

  if (button.hasAttribute('data-clear-result')) {
    currentUser = null;
    userResult.replaceChildren();
    userResult.hidden = true;
    lookupIdInput.value = '';
    clearMessage(lookupMessage);
    lookupIdInput.focus();
    return;
  }

  if (button.dataset.exportUser && currentUser) {
    const download = document.createElement('a');
    const file = new Blob([JSON.stringify(currentUser, null, 2)], { type: 'application/json' });
    const fileUrl = URL.createObjectURL(file);
    download.href = fileUrl;
    download.download = `niramaya-user-${currentUser.id}.json`;
    document.body.append(download);
    download.click();
    download.remove();
    window.setTimeout(() => URL.revokeObjectURL(fileUrl), 0);
    showMessage(lookupMessage, 'Profile exported as a JSON file.', 'success');
    return;
  }

  try {
    if (button.dataset.copyId) {
      await navigator.clipboard.writeText(button.dataset.copyId);
      showMessage(lookupMessage, 'Profile ID copied to clipboard.', 'success');
    } else {
      const profileUrl = new URL(window.location.href);
      profileUrl.search = '';
      profileUrl.searchParams.set('user_id', button.dataset.shareUser);
      await navigator.clipboard.writeText(profileUrl.toString());
      showMessage(lookupMessage, 'Profile link copied to clipboard.', 'success');
    }
  } catch {
    showMessage(lookupMessage, 'Clipboard access is unavailable in this browser.');
  }
});

const sharedUserId = new URLSearchParams(window.location.search).get('user_id');
if (sharedUserId && /^[1-9]\d*$/.test(sharedUserId) && Number.isSafeInteger(Number(sharedUserId))) {
  lookupIdInput.value = sharedUserId;
  lookupForm.requestSubmit();
}
