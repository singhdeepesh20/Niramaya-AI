const REQUEST_TIMEOUT_MS = 10_000;

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
      headers: { Accept: 'application/json', ...options.headers },
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

const healthResult = document.querySelector('#health-result');
const healthText = document.querySelector('#health-text');
const healthDetail = document.querySelector('#health-detail');
const healthStateLabel = document.querySelector('#health-state-label');
const lastChecked = document.querySelector('#last-checked');
const healthButton = document.querySelector('#health-button');

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
    lastChecked.textContent = `Last checked at ${new Intl.DateTimeFormat(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date())}`;
    setHealthButtonLoading(false);
  }
}

healthButton.addEventListener('click', checkHealth);
checkHealth();

const createForm = document.querySelector('#create-form');
const createMessage = document.querySelector('#create-message');
const createButton = createForm.querySelector('button[type="submit"]');
const lookupIdInput = document.querySelector('#user-id');

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage(createMessage);
  setFormBusy(createForm, true);
  setButtonLoading(createButton, true, 'Creating profile…');

  const formData = new FormData(createForm);
  const body = {
    name: String(formData.get('name') || '').trim(),
    email: String(formData.get('email') || '').trim(),
  };

  try {
    const user = await requestJson('/users/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    showMessage(createMessage, `User created successfully. Profile ID: ${user.id}.`, 'success');
    createForm.reset();
    lookupIdInput.value = user.id;
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

function renderUser(user) {
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
  heading.append(avatar, title);

  const fields = document.createElement('div');
  fields.className = 'result-fields';
  fields.append(createResultField('Email', user.email));

  userResult.replaceChildren(heading, fields);
  userResult.hidden = false;
}

lookupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage(lookupMessage);
  userResult.hidden = true;
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
});
