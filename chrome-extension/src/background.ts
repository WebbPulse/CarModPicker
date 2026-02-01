/**
 * Background service worker for API communication
 */

import type {
  ApiResponse,
  Brand,
  Car,
  Category,
  GlobalPartCreate,
  GlobalPartRead,
  ImageUploadResponse,
  LoginResponse,
  PartListingCreate,
  Retailer,
  User,
} from "./types";
import {
  getCanonicalImageUrl,
  getHighResImageUrl,
} from "./utils/imageUrlUtils";

// API base URL - defaults to production (backend is at api subdomain + /api path)
const DEFAULT_API_URL = "https://api.carmodpicker.webbpulse.com/api";

/** Old prod URLs to migrate to DEFAULT_API_URL when seen */
const LEGACY_PROD_API_URLS = [
  "https://carmodpicker.webbpulse.com/api", // frontend origin + /api
  "https://api.carmodpicker.webbpulse.com", // api host without /api path
];

/**
 * Get API base URL from storage
 */
async function getApiUrl(): Promise<string> {
  const result = await chrome.storage.sync.get(["apiUrl"]);
  let apiUrl = (result["apiUrl"] as string) || DEFAULT_API_URL;
  if (LEGACY_PROD_API_URLS.includes(apiUrl)) {
    apiUrl = DEFAULT_API_URL;
    await chrome.storage.sync.set({ apiUrl });
  }
  return apiUrl;
}

/**
 * Get stored authentication token
 */
async function getToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(["authToken"]);
  return (result["authToken"] as string) || null;
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
  await chrome.storage.local.remove(["authToken"]);
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
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: headers as HeadersInit,
    });

    const data = (await response.json().catch(() => ({}))) as unknown;

    if (!response.ok) {
      const errorData = data as { detail?: string };
      const errorMessage =
        errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
      throw new Error(errorMessage);
    }

    return { success: true, data: data as T };
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Request failed";
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
  formData.append("username", username);
  formData.append("password", password);

  try {
    const response = await fetch(loginUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData.toString(),
    });

    let data: LoginResponse | { detail?: string };
    try {
      data = (await response.json()) as LoginResponse | { detail?: string };
    } catch (_parseError) {
      const text = await response.text();

      // Check for CORS errors
      if (
        response.status === 0 ||
        (!response.ok && response.statusText === "")
      ) {
        return {
          success: false,
          error:
            "CORS error: Server is not allowing requests from this extension. Check backend CORS configuration.",
        };
      }

      return {
        success: false,
        error: `Invalid response from server: ${response.status} ${
          response.statusText
        }. Response: ${text.substring(0, 200)}`,
      };
    }

    if (!response.ok) {
      const errorData = data as { detail?: string };
      const errorMessage =
        errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
      return {
        success: false,
        error: errorMessage,
      };
    }

    const loginData = data as LoginResponse;

    // Check for 2FA requirement - return success so extension can show OTP step
    if (loginData.requires_2fa) {
      return {
        success: false,
        requires2FA: true,
      };
    }

    if (loginData.access_token) {
      await setToken(loginData.access_token);
      return { success: true, data: loginData.user };
    }

    return { success: false, error: "No access token received" };
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Login failed";
    return {
      success: false,
      error: errorMessage,
    };
  }
}

/**
 * Complete login with 2FA OTP code.
 * User must have called /token first to verify username/password.
 */
async function loginWith2FA(
  username: string,
  password: string,
  otp: string
): Promise<ApiResponse<User> & { requires2FA?: boolean }> {
  const apiUrl = await getApiUrl();
  const loginUrl = `${apiUrl}/auth/token/2fa`;

  try {
    const response = await fetch(loginUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password, otp }),
    });

    const data = (await response.json()) as
      | LoginResponse
      | { detail?: string; message?: string };

    if (!response.ok) {
      const errorData = data as { detail?: string };
      return {
        success: false,
        error: errorData.detail || "Invalid OTP code",
      };
    }

    const loginData = data as LoginResponse;
    if (loginData.access_token) {
      await setToken(loginData.access_token);
      return { success: true, data: loginData.user };
    }

    return { success: false, error: "No access token received" };
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Login failed";
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
  return apiRequest<User>("/users/me", { method: "GET" });
}

/**
 * Get categories
 */
async function getCategories(): Promise<ApiResponse<Category[]>> {
  return apiRequest<Category[]>("/categories/", { method: "GET" });
}

/**
 * Get cars
 */
async function getCars(limit: number = 1000): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(`/cars/?limit=${limit}`, { method: "GET" });
}

/**
 * Search cars
 */
async function searchCars(
  searchTerm: string,
  limit: number = 100
): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(
    `/cars/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" }
  );
}

/**
 * Get brands (optionally filtered to active only)
 */
async function getBrands(
  activeOnly: boolean = true
): Promise<ApiResponse<Brand[]>> {
  return apiRequest<Brand[]>(`/brands/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/**
 * Search brands by name
 */
async function searchBrands(
  searchTerm: string,
  limit: number = 100
): Promise<ApiResponse<Brand[]>> {
  return apiRequest<Brand[]>(
    `/brands/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" }
  );
}

/**
 * Create a brand (get-or-create: returns existing if same name exists)
 */
async function createBrand(name: string): Promise<ApiResponse<Brand>> {
  return apiRequest<Brand>("/brands/", {
    method: "POST",
    body: JSON.stringify({ name: name.trim(), is_active: true }),
  });
}

/**
 * Get retailers (optionally filtered to active only)
 */
async function getRetailers(
  activeOnly: boolean = true
): Promise<ApiResponse<Retailer[]>> {
  return apiRequest<Retailer[]>(`/retailers/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/**
 * Get or create retailer by domain (for scrapers - creates retailer if not in catalog)
 */
async function getOrCreateRetailerByDomain(
  domain: string,
  name?: string,
  baseUrl?: string
): Promise<ApiResponse<Retailer>> {
  const body: { domain: string; name?: string; base_url?: string } = {
    domain: domain.trim().toLowerCase(),
  };
  if (name?.trim()) body.name = name.trim();
  if (baseUrl?.trim()) body.base_url = baseUrl.trim();
  return apiRequest<Retailer>("/retailers/get-or-create", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Check if product URL already exists in catalog
 */
async function checkProductUrl(
  productUrl: string
): Promise<ApiResponse<{ existing_part_id: number | null }>> {
  return apiRequest<{ existing_part_id: number | null }>(
    `/global-parts/check-url?product_url=${encodeURIComponent(productUrl)}`,
    { method: "GET" }
  );
}

/**
 * Get global part by ID (with listings for display)
 */
async function getGlobalPart(
  partId: number
): Promise<ApiResponse<GlobalPartRead>> {
  return apiRequest<GlobalPartRead>(`/global-parts/${partId}`, {
    method: "GET",
  });
}

/**
 * Find existing global part by brand ID and part number (for scraper update-mode detection).
 * Returns the part if found, or { success: false } when not found (404).
 */
async function findExistingPartByBrandAndPartNumber(
  brandId: number,
  partNumber: string
): Promise<ApiResponse<GlobalPartRead>> {
  const trimmed = partNumber?.trim();
  if (!trimmed) {
    return { success: false, error: "Part number required" };
  }
  const url = `/global-parts/find-by-brand-and-part-number?brand_id=${encodeURIComponent(
    brandId
  )}&part_number=${encodeURIComponent(trimmed)}`;
  return apiRequest<GlobalPartRead>(url, { method: "GET" });
}

/**
 * Append image file keys to a global part's gallery
 */
async function appendImagesToGlobalPart(
  partId: number,
  fileKeys: string[]
): Promise<ApiResponse<GlobalPartRead>> {
  return apiRequest<GlobalPartRead>(`/global-parts/${partId}/append-images`, {
    method: "POST",
    body: JSON.stringify({ file_keys: fileKeys }),
  });
}

/** Max images allowed per global part (must match backend MAX_IMAGES_PER_GLOBAL_PART) */
const MAX_IMAGES_PER_GLOBAL_PART = 10;

/**
 * Check which source URLs are not in our image cache.
 * Dedupes by canonical URL - returns one high-res URL per unique image.
 * Only considers up to MAX_IMAGES_PER_GLOBAL_PART URLs.
 */
async function checkUncachedImageUrls(
  sourceUrls: string[]
): Promise<ApiResponse<{ uncachedUrls: string[] }>> {
  const urls = sourceUrls.slice(0, MAX_IMAGES_PER_GLOBAL_PART);
  const byCanonical = new Map<string, string>();
  const getWidth = (u: string) => {
    try {
      return parseInt(new URL(u).searchParams.get("width") || "0", 10) || 0;
    } catch {
      return 0;
    }
  };
  for (const url of urls) {
    const c = getCanonicalImageUrl(url);
    if (!c) continue;
    const existing = byCanonical.get(c);
    if (!existing || getWidth(url) > getWidth(existing)) {
      byCanonical.set(c, url);
    }
  }
  const uncached: string[] = [];
  await Promise.all(
    Array.from(byCanonical.values()).map(async (url) => {
      const res = await getImageBySourceUrl(url);
      if (!res.success || !res.data?.fileKey) {
        uncached.push(getHighResImageUrl(url));
      }
    })
  );
  return { success: true, data: { uncachedUrls: uncached } };
}

/**
 * Add or update part listing (creates PartListing and PartPriceHistory)
 */
async function addPartListing(
  data: PartListingCreate
): Promise<ApiResponse<unknown>> {
  return apiRequest(`/global-parts/${data.global_part_id}/listings`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Create global part
 */
async function createGlobalPart(
  partData: GlobalPartCreate
): Promise<ApiResponse<unknown>> {
  return apiRequest("/global-parts/", {
    method: "POST",
    body: JSON.stringify(partData),
  });
}

/**
 * Check if we already have this image cached by source URL (deduplication)
 */
async function getImageBySourceUrl(
  sourceUrl: string
): Promise<ApiResponse<{ fileKey: string }>> {
  const res = await apiRequest<{ file_key: string }>(
    `/images/by-source-url?source_url=${encodeURIComponent(sourceUrl)}`,
    { method: "GET" }
  );
  if (res.success && res.data) {
    return { success: true, data: { fileKey: res.data.file_key } };
  }
  return { success: false, error: res.error ?? "Image not in cache" };
}

/**
 * Upload image and get file key.
 * First checks if we've already stored this image by source URL (deduplication).
 * If not cached, fetches the image and uploads, passing source_url for future dedup.
 * When entityId (global part id) is provided, backend enforces max images and rejects if part is full.
 */
async function uploadImage(
  imageUrl: string,
  entityId?: number
): Promise<ApiResponse<{ fileKey: string }>> {
  try {
    const apiUrl = await getApiUrl();
    const token = await getToken();

    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    // Check cache first (backend uses canonical URL for dedup)
    const cached = await getImageBySourceUrl(imageUrl);
    if (cached.success && cached.data?.fileKey) {
      return { success: true, data: { fileKey: cached.data.fileKey } };
    }

    // Not cached: fetch high-res and upload (canonical for storage)
    const fetchUrl = getHighResImageUrl(imageUrl);
    const imageResponse = await fetch(fetchUrl);
    if (!imageResponse.ok) {
      throw new Error("Failed to fetch image");
    }

    const blob = await imageResponse.blob();
    const file = new File([blob], "image.jpg", { type: blob.type });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_url", getCanonicalImageUrl(imageUrl));

    const uploadUrl = new URL(`${apiUrl}/images/upload`);
    uploadUrl.searchParams.set("entity_type", "global_part");
    if (entityId != null) {
      uploadUrl.searchParams.set("entity_id", String(entityId));
    }

    const response = await fetch(uploadUrl.toString(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    const data = (await response.json()) as
      | ImageUploadResponse
      | { detail?: string };

    if (!response.ok) {
      const errorData = data as { detail?: string };
      throw new Error(errorData.detail || "Image upload failed");
    }

    const uploadData = data as ImageUploadResponse;
    return { success: true, data: { fileKey: uploadData.file_key } };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Image upload failed",
    };
  }
}

// Listen for messages from popup/content scripts
chrome.runtime.onMessage.addListener(
  (
    request: {
      action: string;
      username?: string;
      password?: string;
      otp?: string;
      partData?: GlobalPartCreate;
      imageUrl?: string;
      partId?: number;
      fileKeys?: string[];
      sourceUrls?: string[];
      limit?: number;
      searchTerm?: string;
      brandName?: string;
      productUrl?: string;
      brandId?: number;
      partNumber?: string;
      domain?: string;
      listingData?: PartListingCreate;
    },
    _sender,
    sendResponse: (response: unknown) => void
  ) => {
    if (request.action === "login") {
      if (request.username && request.password) {
        login(request.username, request.password).then(sendResponse);
        return true; // Keep channel open for async
      } else {
        sendResponse({
          success: false,
          error: "Username and password required",
        });
        return false;
      }
    }

    if (request.action === "loginWith2FA") {
      if (request.username && request.password && request.otp) {
        loginWith2FA(request.username, request.password, request.otp).then(
          sendResponse
        );
        return true;
      } else {
        sendResponse({
          success: false,
          error: "Username, password, and OTP code required",
        });
        return false;
      }
    }

    if (request.action === "logout") {
      removeToken().then(() => {
        sendResponse({ success: true });
      });
      return true;
    }

    if (request.action === "getCurrentUser") {
      getCurrentUser().then(sendResponse);
      return true;
    }

    if (request.action === "getCategories") {
      getCategories().then(sendResponse);
      return true;
    }

    if (request.action === "getCars") {
      const limit = request.limit || 1000;
      getCars(limit).then(sendResponse);
      return true;
    }

    if (request.action === "searchCars") {
      if (request.searchTerm) {
        searchCars(request.searchTerm).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getBrands") {
      getBrands().then(sendResponse);
      return true;
    }

    if (request.action === "searchBrands") {
      if (request.searchTerm) {
        searchBrands(request.searchTerm).then(sendResponse);
        return true;
      }
    }

    if (request.action === "createBrand") {
      if (request.brandName) {
        createBrand(request.brandName).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getRetailers") {
      getRetailers().then(sendResponse);
      return true;
    }

    if (request.action === "getOrCreateRetailerByDomain") {
      if (request.domain) {
        getOrCreateRetailerByDomain(request.domain).then(sendResponse);
        return true;
      }
    }

    if (request.action === "checkProductUrl") {
      if (request.productUrl) {
        checkProductUrl(request.productUrl).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getGlobalPart") {
      if (request.partId != null) {
        getGlobalPart(request.partId).then(sendResponse);
        return true;
      }
    }

    if (request.action === "findExistingPartByBrandAndPartNumber") {
      if (
        request.brandId != null &&
        request.partNumber != null &&
        String(request.partNumber).trim()
      ) {
        findExistingPartByBrandAndPartNumber(
          Number(request.brandId),
          String(request.partNumber)
        ).then(sendResponse);
        return true;
      }
    }

    if (request.action === "addPartListing") {
      if (request.listingData) {
        addPartListing(request.listingData).then(sendResponse);
        return true;
      }
    }

    if (request.action === "createGlobalPart") {
      if (request.partData) {
        createGlobalPart(request.partData).then(sendResponse);
        return true;
      }
    }

    if (request.action === "uploadImage") {
      if (request.imageUrl) {
        uploadImage(request.imageUrl, request.partId).then(sendResponse);
        return true;
      }
    }

    if (request.action === "appendImagesToGlobalPart") {
      if (request.partId != null && request.fileKeys) {
        appendImagesToGlobalPart(
          request.partId,
          request.fileKeys as string[]
        ).then(sendResponse);
        return true;
      }
    }

    if (request.action === "checkUncachedImageUrls") {
      if (request.sourceUrls) {
        checkUncachedImageUrls(request.sourceUrls as string[]).then(
          sendResponse
        );
        return true;
      }
    }

    return false;
  }
);
