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
