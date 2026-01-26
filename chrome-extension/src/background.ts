/**
 * Background service worker for API communication
 */

import type {
  ApiResponse,
  GlobalPartCreate,
  ImageUploadResponse,
  LoginResponse,
  User,
  Category,
  Car,
} from './types';

// API base URL - defaults to production
const DEFAULT_API_URL = 'https://carmodpicker.com/api';

/**
 * Get API base URL from storage
 */
async function getApiUrl(): Promise<string> {
  const result = await chrome.storage.sync.get(['apiUrl']);
  const apiUrl = (result['apiUrl'] as string) || DEFAULT_API_URL;
  return apiUrl;
}

/**
 * Get stored authentication token
 */
async function getToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(['authToken']);
  return (result['authToken'] as string) || null;
}

/**
 * Store authentication token
 */
async function setToken(token: string): Promise<void> {
  await chrome.storage.local.set({ authToken: token });
}

/**
 * Remove authentication token
 */
async function removeToken(): Promise<void> {
  await chrome.storage.local.remove(['authToken']);
}

/**
 * Make authenticated API request
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const apiUrl = await getApiUrl();
  const token = await getToken();

  const url = `${apiUrl}${endpoint}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: headers as HeadersInit,
    });

    const data = (await response.json().catch(() => ({}))) as unknown;

    if (!response.ok) {
      const errorData = data as { detail?: string };
      const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
      throw new Error(errorMessage);
    }

    return { success: true, data: data as T };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Request failed';
    return {
      success: false,
      error: errorMessage,
    };
  }
}

/**
 * Login to CarModPicker
 */
async function login(
  username: string,
  password: string
): Promise<ApiResponse<User> & { requires2FA?: boolean }> {
  const apiUrl = await getApiUrl();
  const loginUrl = `${apiUrl}/auth/token`;

  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  try {
    const response = await fetch(loginUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    let data: LoginResponse | { detail?: string };
    try {
      data = (await response.json()) as LoginResponse | { detail?: string };
    } catch (_parseError) {
      const text = await response.text();

      // Check for CORS errors
      if (response.status === 0 || !response.ok && response.statusText === '') {
        return {
          success: false,
          error: 'CORS error: Server is not allowing requests from this extension. Check backend CORS configuration.',
        };
      }
      
      return {
        success: false,
        error: `Invalid response from server: ${response.status} ${response.statusText}. Response: ${text.substring(0, 200)}`,
      };
    }

    if (!response.ok) {
      const errorData = data as { detail?: string };
      const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
      return {
        success: false,
        error: errorMessage,
      };
    }

    const loginData = data as LoginResponse;

    // Check for 2FA requirement
    if (loginData.requires_2fa) {
      return {
        success: false,
        requires2FA: true,
        error: '2FA is enabled. Please use the web app to login.',
      };
    }

    if (loginData.access_token) {
      await setToken(loginData.access_token);
      return { success: true, data: loginData.user };
    }

    return { success: false, error: 'No access token received' };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Login failed';
    return {
      success: false,
      error: errorMessage,
    };
  }
}

/**
 * Get current user
 */
async function getCurrentUser(): Promise<ApiResponse<User>> {
  return apiRequest<User>('/users/me', { method: 'GET' });
}

/**
 * Get categories
 */
async function getCategories(): Promise<ApiResponse<Category[]>> {
  return apiRequest<Category[]>('/categories/', { method: 'GET' });
}

/**
 * Get cars
 */
async function getCars(limit: number = 1000): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(`/cars/?limit=${limit}`, { method: 'GET' });
}

/**
 * Search cars
 */
async function searchCars(searchTerm: string, limit: number = 100): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(`/cars/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`, { method: 'GET' });
}

/**
 * Create global part
 */
async function createGlobalPart(
  partData: GlobalPartCreate
): Promise<ApiResponse<unknown>> {
  return apiRequest('/global-parts/', {
    method: 'POST',
    body: JSON.stringify(partData),
  });
}

/**
 * Upload image and get file key
 */
async function uploadImage(
  imageUrl: string
): Promise<ApiResponse<{ fileKey: string }>> {
  try {
    // First, fetch the image
    const imageResponse = await fetch(imageUrl);
    if (!imageResponse.ok) {
      throw new Error('Failed to fetch image');
    }

    const blob = await imageResponse.blob();
    const file = new File([blob], 'image.jpg', { type: blob.type });

    // Get presigned URL or upload directly
    const apiUrl = await getApiUrl();
    const token = await getToken();

    if (!token) {
      return { success: false, error: 'Not authenticated' };
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${apiUrl}/images/upload?entity_type=global_part`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      }
    );

    const data = (await response.json()) as
      | ImageUploadResponse
      | { detail?: string };

    if (!response.ok) {
      const errorData = data as { detail?: string };
      throw new Error(errorData.detail || 'Image upload failed');
    }

    const uploadData = data as ImageUploadResponse;
    return { success: true, data: { fileKey: uploadData.file_key } };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Image upload failed',
    };
  }
}

// Listen for messages from popup/content scripts
chrome.runtime.onMessage.addListener(
  (
    request: { action: string; username?: string; password?: string; partData?: GlobalPartCreate; imageUrl?: string; limit?: number; searchTerm?: string },
    _sender,
    sendResponse: (response: unknown) => void
  ) => {
    if (request.action === 'login') {
      if (request.username && request.password) {
        login(request.username, request.password).then(sendResponse);
        return true; // Keep channel open for async
      } else {
        sendResponse({ success: false, error: 'Username and password required' });
        return false;
      }
    }

    if (request.action === 'logout') {
      removeToken().then(() => {
        sendResponse({ success: true });
      });
      return true;
    }

    if (request.action === 'getCurrentUser') {
      getCurrentUser().then(sendResponse);
      return true;
    }

    if (request.action === 'getCategories') {
      getCategories().then(sendResponse);
      return true;
    }

    if (request.action === 'getCars') {
      const limit = request.limit || 1000;
      getCars(limit).then(sendResponse);
      return true;
    }

    if (request.action === 'searchCars') {
      if (request.searchTerm) {
        searchCars(request.searchTerm).then(sendResponse);
        return true;
      }
    }

    if (request.action === 'createGlobalPart') {
      if (request.partData) {
        createGlobalPart(request.partData).then(sendResponse);
        return true;
      }
    }

    if (request.action === 'uploadImage') {
      if (request.imageUrl) {
        uploadImage(request.imageUrl).then(sendResponse);
        return true;
      }
    }

    return false;
  }
);
