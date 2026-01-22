/**
 * Popup script for CarModPicker extension
 */

import type {
  ApiResponse,
  User,
  Category,
  Car,
  GlobalPartCreate,
  ScrapedProductData,
} from './types';

// DOM elements
const loginScreen = document.getElementById('loginScreen') as HTMLElement;
const mainScreen = document.getElementById('mainScreen') as HTMLElement;
const loginForm = document.getElementById('loginForm') as HTMLFormElement;
const loginError = document.getElementById('loginError') as HTMLElement;
const logoutBtn = document.getElementById('logoutBtn') as HTMLButtonElement;
const scrapeBtn = document.getElementById('scrapeBtn') as HTMLButtonElement;
const userName = document.getElementById('userName') as HTMLElement;
const statusMessage = document.getElementById('statusMessage') as HTMLElement;
const partDialog = document.getElementById('partDialog') as HTMLElement;
const partForm = document.getElementById('partForm') as HTMLFormElement;
const closeDialog = document.getElementById('closeDialog') as HTMLButtonElement;
const cancelBtn = document.getElementById('cancelBtn') as HTMLButtonElement;
const dialogError = document.getElementById('dialogError') as HTMLElement;
const settingsLink = document.getElementById('settingsLink') as HTMLAnchorElement;

// Form fields
const partName = document.getElementById('partName') as HTMLInputElement;
const partBrand = document.getElementById('partBrand') as HTMLInputElement;
const partNumber = document.getElementById('partNumber') as HTMLInputElement;
const partDescription = document.getElementById('partDescription') as HTMLTextAreaElement;
const partPrice = document.getElementById('partPrice') as HTMLInputElement;
const partUrl = document.getElementById('partUrl') as HTMLInputElement;
const partCategory = document.getElementById('partCategory') as HTMLSelectElement;
const partCar = document.getElementById('partCar') as HTMLInputElement; // Hidden input
const partCarContainer = document.getElementById('partCarContainer') as HTMLElement;
const partCarTrigger = document.getElementById('partCarTrigger') as HTMLElement;
const partCarDisplay = document.getElementById('partCarDisplay') as HTMLElement;
const partCarDropdown = document.getElementById('partCarDropdown') as HTMLElement;
const partCarSearch = document.getElementById('partCarSearch') as HTMLInputElement;
const partCarOptions = document.getElementById('partCarOptions') as HTMLElement;
const partImage = document.getElementById('partImage') as HTMLInputElement;
const imagePreview = document.getElementById('imagePreview') as HTMLElement;
const previewImg = document.getElementById('previewImg') as HTMLImageElement;

let categories: Category[] = [];
let cars: Car[] = [];
let allCarsLoaded = false;
let searchTimeout: number | null = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuthStatus();
  setupEventListeners();
});

/**
 * Check if user is authenticated
 */
async function checkAuthStatus(): Promise<void> {
  try {
    const response = (await sendMessage({
      action: 'getCurrentUser',
    })) as ApiResponse<User>;
    if (response.success && response.data) {
      showMainScreen(response.data);
    } else {
      showLoginScreen();
    }
  } catch (error) {
    showLoginScreen();
  }
}

/**
 * Show login screen
 */
function showLoginScreen(): void {
  loginScreen.style.display = 'block';
  mainScreen.style.display = 'none';
  partDialog.style.display = 'none';
}

/**
 * Show main screen
 */
function showMainScreen(user: User): void {
  loginScreen.style.display = 'none';
  mainScreen.style.display = 'block';
  userName.textContent = user.username || user.email || 'User';
}

/**
 * Setup event listeners
 */
function setupEventListeners(): void {
  loginForm.addEventListener('submit', handleLogin);
  logoutBtn.addEventListener('click', handleLogout);
  scrapeBtn.addEventListener('click', handleScrape);
  closeDialog.addEventListener('click', closePartDialog);
  cancelBtn.addEventListener('click', closePartDialog);
  partForm.addEventListener('submit', handleCreatePart);
  partImage.addEventListener('input', handleImagePreview);
  settingsLink.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });
  
  // Searchable dropdown event listeners
  setupSearchableDropdown();
}

/**
 * Handle login
 */
async function handleLogin(e: Event): Promise<void> {
  e.preventDefault();

  const usernameInput = document.getElementById('username') as HTMLInputElement;
  const passwordInput = document.getElementById('password') as HTMLInputElement;
  const loginBtn = document.getElementById('loginBtn') as HTMLButtonElement;

  const username = usernameInput.value;
  const password = passwordInput.value;

  loginBtn.disabled = true;
  loginBtn.textContent = 'Logging in...';
  hideError(loginError);

  try {
    console.log('[Popup] Sending login request');
    const response = (await sendMessage({
      action: 'login',
      username,
      password,
    })) as ApiResponse<User> & { requires2FA?: boolean };

    console.log('[Popup] Login response:', response);

    if (response.success && response.data) {
      console.log('[Popup] Login successful');
      showMainScreen(response.data);
    } else {
      if (response.requires2FA) {
        console.log('[Popup] 2FA required');
        showError(loginError, '2FA is enabled. Please login via the web app first.');
      } else {
        const errorMsg = response.error || 'Login failed';
        console.error('[Popup] Login failed:', errorMsg);
        showError(loginError, errorMsg);
      }
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Login failed';
    console.error('[Popup] Login error:', errorMsg, error);
    showError(loginError, errorMsg);
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Login';
  }
}

/**
 * Handle logout
 */
async function handleLogout(): Promise<void> {
  await sendMessage({ action: 'logout' });
  showLoginScreen();
}

/**
 * Handle scrape button click
 */
async function handleScrape(): Promise<void> {
  scrapeBtn.disabled = true;
  scrapeBtn.textContent = 'Scraping...';
  hideStatus();

  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.id) {
      showStatus('No active tab found', 'error');
      return;
    }

    // Send message to content script to scrape the page
    chrome.tabs.sendMessage(
      tab.id,
      { action: 'scrapePage' },
      (response: { success: boolean; data: ScrapedProductData } | undefined) => {
        if (chrome.runtime.lastError) {
          showStatus(
            'Failed to scrape page data. Make sure you are on a product page and refresh if needed.',
            'error'
          );
          return;
        }
        if (response && response.success && response.data) {
          showPartDialog(response.data);
        } else {
          showStatus('Failed to scrape page data. Make sure you are on a product page.', 'error');
        }
      }
    );
  } catch (error) {
    showStatus(
      'Error scraping page: ' + (error instanceof Error ? error.message : 'Unknown error'),
      'error'
    );
  } finally {
    scrapeBtn.disabled = false;
    scrapeBtn.innerHTML = '<span class="icon">📦</span> Scrape Current Page';
  }
}

/**
 * Show part creation dialog
 */
async function showPartDialog(data: ScrapedProductData): Promise<void> {
  // Populate form with scraped data
  partName.value = data.name || '';
  partBrand.value = data.brand || '';
  partNumber.value = data.part_number || '';
  partDescription.value = data.description || '';
  partPrice.value = data.price ? (data.price / 100).toFixed(2) : '';
  partUrl.value = data.product_url || '';
  partImage.value = data.image_url || '';

  // Load categories and cars
  await loadCategories();
  await loadCars();

  // Show image preview if URL provided
  if (data.image_url) {
    previewImg.src = data.image_url;
    imagePreview.style.display = 'block';
  } else {
    imagePreview.style.display = 'none';
  }

  partDialog.style.display = 'block';
  hideError(dialogError);
}

/**
 * Close part dialog
 */
function closePartDialog(): void {
  partDialog.style.display = 'none';
  partForm.reset();
  closeCarDropdown();
  partCar.value = '';
  partCarDisplay.textContent = 'None';
}

/**
 * Load categories
 */
async function loadCategories(): Promise<void> {
  try {
    const response = (await sendMessage({
      action: 'getCategories',
    })) as ApiResponse<Category[]>;
    if (response.success && Array.isArray(response.data)) {
      categories = response.data.filter((cat) => cat.is_active);
      partCategory.innerHTML = '<option value="">Select a category...</option>';
      categories.forEach((cat) => {
        const option = document.createElement('option');
        option.value = cat.id.toString();
        option.textContent = cat.display_name || cat.name;
        partCategory.appendChild(option);
      });
    }
  } catch (error) {
    console.error('Failed to load categories:', error);
  }
}

/**
 * Load cars
 */
async function loadCars(): Promise<void> {
  try {
    const response = (await sendMessage({
      action: 'getCars',
      limit: 1000,
    })) as ApiResponse<Car[]>;
    if (response.success && Array.isArray(response.data)) {
      cars = response.data;
      allCarsLoaded = true;
      populateCarOptions();
    }
  } catch (error) {
    console.error('Failed to load cars:', error);
  }
}

/**
 * Search cars on server
 */
async function searchCarsOnServer(searchTerm: string): Promise<void> {
  try {
    const response = (await sendMessage({
      action: 'searchCars',
      searchTerm: searchTerm,
    })) as ApiResponse<Car[]>;
    if (response.success && Array.isArray(response.data)) {
      // Update the options with search results
      updateCarOptionsWithSearchResults(response.data);
    }
  } catch (error) {
    console.error('Failed to search cars:', error);
  }
}

/**
 * Populate car options in the searchable dropdown
 */
function populateCarOptions(): void {
  partCarOptions.innerHTML = '<div class="searchable-select-option" data-value="">None</div>';
  
  cars.forEach((car) => {
    const option = document.createElement('div');
    option.className = 'searchable-select-option';
    option.setAttribute('data-value', car.id.toString());
    option.textContent = `${car.make} ${car.model} ${car.generation_name} (${car.start_year}${car.end_year ? `-${car.end_year}` : ''})`;
    partCarOptions.appendChild(option);
  });
  
  // Update display if a car is already selected
  const selectedValue = partCar.value;
  if (selectedValue) {
    const selectedCar = cars.find(c => c.id.toString() === selectedValue);
    if (selectedCar) {
      partCarDisplay.textContent = `${selectedCar.make} ${selectedCar.model} ${selectedCar.generation_name} (${selectedCar.start_year}${selectedCar.end_year ? `-${selectedCar.end_year}` : ''})`;
    }
  } else {
    partCarDisplay.textContent = 'None';
  }
}

/**
 * Update car options with search results
 */
function updateCarOptionsWithSearchResults(searchResults: Car[]): void {
  partCarOptions.innerHTML = '<div class="searchable-select-option" data-value="">None</div>';
  
  if (searchResults.length === 0) {
    const noResults = document.createElement('div');
    noResults.className = 'searchable-select-option';
    noResults.style.color = '#888';
    noResults.style.cursor = 'default';
    noResults.textContent = 'No cars found';
    partCarOptions.appendChild(noResults);
    return;
  }
  
  searchResults.forEach((car) => {
    const option = document.createElement('div');
    option.className = 'searchable-select-option';
    option.setAttribute('data-value', car.id.toString());
    option.textContent = `${car.make} ${car.model} ${car.generation_name} (${car.start_year}${car.end_year ? `-${car.end_year}` : ''})`;
    partCarOptions.appendChild(option);
  });
  
  // Remove focus from any focused option
  const focused = partCarOptions.querySelector('.searchable-select-option.focused');
  if (focused) {
    focused.classList.remove('focused');
  }
}

/**
 * Setup searchable dropdown functionality
 */
function setupSearchableDropdown(): void {
  // Toggle dropdown on trigger click
  partCarTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = partCarDropdown.style.display !== 'none';
    if (isOpen) {
      closeCarDropdown();
    } else {
      openCarDropdown();
    }
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!partCarContainer.contains(e.target as Node)) {
      closeCarDropdown();
    }
  });
  
  // Handle search input with debouncing and server-side search
  partCarSearch.addEventListener('input', (e) => {
    const searchTerm = (e.target as HTMLInputElement).value.trim();
    
    // Clear existing timeout
    if (searchTimeout !== null) {
      clearTimeout(searchTimeout);
    }
    
    // If search term is empty, show all loaded cars
    if (searchTerm === '') {
      if (allCarsLoaded) {
        populateCarOptions();
      } else {
        // If we haven't loaded all cars yet, load them
        loadCars();
      }
      return;
    }
    
    // If search term is short (1-2 chars), do client-side filtering on loaded cars
    if (searchTerm.length <= 2 && allCarsLoaded) {
      filterCarOptions(searchTerm.toLowerCase());
      return;
    }
    
    // For longer search terms, use server-side search with debouncing
    searchTimeout = window.setTimeout(() => {
      searchCarsOnServer(searchTerm);
    }, 300); // 300ms debounce
  });
  
  // Handle option selection
  partCarOptions.addEventListener('click', (e) => {
    const option = (e.target as HTMLElement).closest('.searchable-select-option');
    if (option) {
      const value = option.getAttribute('data-value') || '';
      selectCar(value);
      closeCarDropdown();
    }
  });
  
  // Handle keyboard navigation
  partCarSearch.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusNextOption();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusPreviousOption();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const focused = partCarOptions.querySelector('.searchable-select-option.focused');
      if (focused) {
        const value = focused.getAttribute('data-value') || '';
        selectCar(value);
        closeCarDropdown();
      }
    } else if (e.key === 'Escape') {
      closeCarDropdown();
    }
  });
}

/**
 * Open car dropdown
 */
function openCarDropdown(): void {
  partCarDropdown.style.display = 'flex';
  partCarTrigger.classList.add('active');
  partCarSearch.value = '';
  partCarSearch.focus();
  filterCarOptions('');
}

/**
 * Close car dropdown
 */
function closeCarDropdown(): void {
  partCarDropdown.style.display = 'none';
  partCarTrigger.classList.remove('active');
  partCarSearch.value = '';
  // Remove focus from any focused option
  const focused = partCarOptions.querySelector('.searchable-select-option.focused');
  if (focused) {
    focused.classList.remove('focused');
  }
}

/**
 * Filter car options based on search term
 */
function filterCarOptions(searchTerm: string): void {
  const options = partCarOptions.querySelectorAll('.searchable-select-option');
  let visibleCount = 0;
  
  options.forEach((option) => {
    const text = option.textContent?.toLowerCase() || '';
    if (searchTerm === '' || text.includes(searchTerm)) {
      option.classList.remove('hidden');
      visibleCount++;
    } else {
      option.classList.add('hidden');
    }
  });
  
  // Remove focus from hidden options
  const focused = partCarOptions.querySelector('.searchable-select-option.focused');
  if (focused && focused.classList.contains('hidden')) {
    focused.classList.remove('focused');
  }
}

/**
 * Select a car
 */
function selectCar(value: string): void {
  partCar.value = value;
  
  if (value === '') {
    partCarDisplay.textContent = 'None';
  } else {
    const selectedCar = cars.find(c => c.id.toString() === value);
    if (selectedCar) {
      partCarDisplay.textContent = `${selectedCar.make} ${selectedCar.model} ${selectedCar.generation_name} (${selectedCar.start_year}${selectedCar.end_year ? `-${selectedCar.end_year}` : ''})`;
    }
  }
  
  // Update selected state in options
  const options = partCarOptions.querySelectorAll('.searchable-select-option');
  options.forEach((option) => {
    if (option.getAttribute('data-value') === value) {
      option.classList.add('selected');
    } else {
      option.classList.remove('selected');
    }
  });
}

/**
 * Focus next option
 */
function focusNextOption(): void {
  const options = Array.from(partCarOptions.querySelectorAll('.searchable-select-option:not(.hidden)'));
  const currentIndex = options.findIndex(opt => opt.classList.contains('focused'));
  
  options.forEach(opt => opt.classList.remove('focused'));
  
  if (currentIndex === -1 || currentIndex === options.length - 1) {
    options[0]?.classList.add('focused');
    options[0]?.scrollIntoView({ block: 'nearest' });
  } else {
    options[currentIndex + 1]?.classList.add('focused');
    options[currentIndex + 1]?.scrollIntoView({ block: 'nearest' });
  }
}

/**
 * Focus previous option
 */
function focusPreviousOption(): void {
  const options = Array.from(partCarOptions.querySelectorAll('.searchable-select-option:not(.hidden)'));
  const currentIndex = options.findIndex(opt => opt.classList.contains('focused'));
  
  options.forEach(opt => opt.classList.remove('focused'));
  
  if (currentIndex === -1 || currentIndex === 0) {
    options[options.length - 1]?.classList.add('focused');
    options[options.length - 1]?.scrollIntoView({ block: 'nearest' });
  } else {
    options[currentIndex - 1]?.classList.add('focused');
    options[currentIndex - 1]?.scrollIntoView({ block: 'nearest' });
  }
}

/**
 * Handle image preview
 */
function handleImagePreview(): void {
  const url = partImage.value.trim();
  if (url) {
    previewImg.src = url;
    imagePreview.style.display = 'block';
  } else {
    imagePreview.style.display = 'none';
  }
}

/**
 * Handle part creation
 */
async function handleCreatePart(e: Event): Promise<void> {
  e.preventDefault();
  hideError(dialogError);

  const createBtn = document.getElementById('createBtn') as HTMLButtonElement;
  createBtn.disabled = true;
  createBtn.textContent = 'Creating...';

  try {
    // Validate required fields
    if (!partName.value.trim()) {
      showError(dialogError, 'Part name is required');
      createBtn.disabled = false;
      createBtn.textContent = 'Create Part';
      return;
    }

    if (!partCategory.value) {
      showError(dialogError, 'Category is required');
      createBtn.disabled = false;
      createBtn.textContent = 'Create Part';
      return;
    }

    // Prepare part data
    const partData: GlobalPartCreate = {
      name: partName.value.trim(),
      description: partDescription.value.trim() || null,
      price: partPrice.value ? Math.round(parseFloat(partPrice.value) * 100) : null,
      product_url: partUrl.value.trim() || null,
      category_id: parseInt(partCategory.value),
      car_id: partCar.value ? parseInt(partCar.value) : null,
      brand: partBrand.value.trim() || null,
      part_number: partNumber.value.trim() || null,
      image_url: null,
    };

    // Upload image if provided
    if (partImage.value.trim()) {
      const imageResult = (await sendMessage({
        action: 'uploadImage',
        imageUrl: partImage.value.trim(),
      })) as ApiResponse<{ fileKey: string }>;

      if (imageResult.success && imageResult.data) {
        partData.image_url = imageResult.data.fileKey;
      } else {
        console.warn('Image upload failed:', imageResult.error);
        // Continue without image
      }
    }

    // Create part
    const response = (await sendMessage({
      action: 'createGlobalPart',
      partData,
    })) as ApiResponse<unknown>;

    if (response.success) {
      showStatus('Part created successfully!', 'success');
      closePartDialog();
      setTimeout(() => {
        hideStatus();
      }, 3000);
    } else {
      showError(dialogError, response.error || 'Failed to create part');
    }
  } catch (error) {
    showError(
      dialogError,
      error instanceof Error ? error.message : 'Failed to create part'
    );
  } finally {
    createBtn.disabled = false;
    createBtn.textContent = 'Create Part';
  }
}

/**
 * Send message to background script
 */
function sendMessage(message: {
  action: string;
  username?: string;
  password?: string;
  partData?: GlobalPartCreate;
  imageUrl?: string;
  limit?: number;
  searchTerm?: string;
}): Promise<unknown> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response: unknown) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

/**
 * Show error message
 */
function showError(element: HTMLElement, message: string): void {
  element.textContent = message;
  element.style.display = 'block';
}

/**
 * Hide error message
 */
function hideError(element: HTMLElement): void {
  element.style.display = 'none';
  element.textContent = '';
}

/**
 * Show status message
 */
function showStatus(message: string, type: 'info' | 'success' | 'error' = 'info'): void {
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`;
  statusMessage.style.display = message ? 'block' : 'none';
}

/**
 * Hide status message
 */
function hideStatus(): void {
  statusMessage.style.display = 'none';
}
