/**
 * Options page script
 */

const apiUrlInput = document.getElementById('apiUrl') as HTMLInputElement;
const saveBtn = document.getElementById('saveBtn') as HTMLButtonElement;
const statusElement = document.getElementById('status') as HTMLElement;

// Load saved settings
chrome.storage.sync.get(['apiUrl'], (result) => {
  if (result.apiUrl && typeof result.apiUrl === 'string') {
    apiUrlInput.value = result.apiUrl;
  } else {
    apiUrlInput.value = 'https://carmodpicker.com/api';
  }
});

// Save settings
saveBtn.addEventListener('click', async () => {
  const apiUrl = apiUrlInput.value.trim();

  if (!apiUrl) {
    showStatus('API URL cannot be empty', 'error');
    return;
  }

  // Validate URL format
  try {
    new URL(apiUrl);
  } catch (e) {
    showStatus('Invalid URL format', 'error');
    return;
  }

  // Ensure URL ends with /api
  const normalizedUrl = apiUrl.endsWith('/api')
    ? apiUrl
    : apiUrl.endsWith('/')
    ? apiUrl + 'api'
    : apiUrl + '/api';

  await chrome.storage.sync.set({ apiUrl: normalizedUrl });
  showStatus('Settings saved successfully!', 'success');

  setTimeout(() => {
    statusElement.style.display = 'none';
  }, 3000);
});

function showStatus(message: string, type: 'success' | 'error'): void {
  statusElement.textContent = message;
  statusElement.className = `status ${type}`;
  statusElement.style.display = 'block';
}
