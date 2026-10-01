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
  createForm.setAttribute('aria-busy', 'true');
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
    createForm.setAttribute('aria-busy', 'false');
    setButtonLoading(createButton, false);
  }
});
