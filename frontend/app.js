const healthText = document.querySelector('#health-text');
const healthIndicator = document.querySelector('#health-indicator');
const healthButton = document.querySelector('#health-button');

function showMessage(element, message, kind) {
  element.textContent = message;
  element.className = `message ${kind}`;
  element.hidden = false;
}

async function checkHealth() {
  healthButton.disabled = true;
  healthText.textContent = 'Checking connection…';
  healthIndicator.className = 'health-indicator';
  try {
    const response = await fetch('/health');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Database is unavailable.');
    healthText.textContent = `API online · Database ${data.database}`;
    healthIndicator.className = 'health-indicator ok';
  } catch (error) {
    healthText.textContent = error.message || 'Could not reach the API.';
    healthIndicator.className = 'health-indicator error';
  } finally {
    healthButton.disabled = false;
  }
}

healthButton.addEventListener('click', checkHealth);
checkHealth();

document.querySelector('#create-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const message = document.querySelector('#create-message');
  button.disabled = true;
  message.hidden = true;
  try {
    const response = await fetch('/users/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.elements.namedItem('name').value.trim(),
        email: form.elements.namedItem('email').value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not create user.');
    showMessage(message, `User created successfully · ID ${data.id}`, 'success');
    form.reset();
    document.querySelector('#user-id').value = data.id;
  } catch (error) {
    showMessage(message, error.message || 'Could not reach the API.', 'error');
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#lookup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const message = document.querySelector('#lookup-message');
  const result = document.querySelector('#user-result');
  const id = form.elements.namedItem('user_id').value;
  button.disabled = true;
  message.hidden = true;
  result.hidden = true;
  try {
    const response = await fetch(`/users/${encodeURIComponent(id)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not find user.');
    const fields = [
      ['ID', data.id],
      ['Name', data.name],
      ['Email', data.email],
      ['Created', new Date(data.created_at).toLocaleString()],
    ];
    result.replaceChildren(...fields.map(([label, value]) => {
      const item = document.createElement('div');
      item.className = 'result-item';
      const title = document.createElement('span');
      title.textContent = label;
      const content = document.createElement('strong');
      content.textContent = value;
      item.append(title, content);
      return item;
    }));
    result.hidden = false;
  } catch (error) {
    showMessage(message, error.message || 'Could not reach the API.', 'error');
  } finally {
    button.disabled = false;
  }
});
