import axios, { type AxiosError, type AxiosResponse } from 'axios';
import type {
  AdminUserUpdate,
  BodyLoginForAccessToken,
  BodyResetPassword,
  BodyVerifyEmail,
  PartManufacturerCreate,
  PartManufacturerResponse,
  PartManufacturerUpdate,
  BugReportCreate,
  BugReportRead,
  BugReportUpdate,
  BugReportWithDetails,
  BuildListCreate,
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithPart,
  BuildListPartUpdate,
  BuildListPhaseCreate,
  BuildListPhaseRead,
  BuildListPhaseUpdate,
  BuildListRead,
  BuildListReadWithVotes,
  BuildListUpdate,
  BuildLogPostCreate,
  BuildLogPostRead,
  BuildLogPostUpdate,
  BuildLogReadPaginated,
  CarGenerationRead,
  CategoryResponse,
  FlaggedEntitySummary,
  PartCreate,
  PartRead,
  PartReadWithVotes,
  PartUpdate,
  LoginResponse,
  NewPassword,
  PaginatedResponse,
  PartListingReadWithRetailer,
  PartPriceHistoryReadWithRetailer,
  ReportCreate,
  ReportRead,
  ReportUpdate,
  ReportWithDetails,
  TOTPDisableRequest,
  TOTPLoginRequest,
  TOTPSetupResponse,
  TOTPVerifyRequest,
  TOTPVerifyResponse,
  UserCreate,
  UserRead,
  UserUpdate,
  GoogleSignInRequest,
  GoogleSignInResponse,
  GoogleLinkRequest,
  GoogleSignupRequest,
  OAuthTwoFactorRequest,
  GoogleConnectRequest,
  OAuthAccountRead,
  VoteCreate,
  VoteRead,
  VoteSummary,
} from '../types/Api';

// Normalize a base URL (ensure protocol, append /api)
const normalizeApiUrl = (url: string): string => {
  const urlWithProtocol =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `https://${url}`;
  return `${urlWithProtocol.replace(/\/+$/, '')}/api`;
};

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development: allow targeting staging or prod via VITE_BACKEND
  if (import.meta.env.DEV) {
    const backend =
      (import.meta.env['VITE_BACKEND'] as string | undefined)?.toLowerCase() ||
      'local';
    if (backend === 'staging') {
      const stagingUrl = import.meta.env['VITE_STAGING_API_URL'] as
        | string
        | undefined;
      if (stagingUrl && typeof stagingUrl === 'string' && stagingUrl.trim()) {
        return normalizeApiUrl(stagingUrl.trim());
      }
    }
    if (backend === 'production') {
      const prodUrl = import.meta.env['VITE_PROD_API_URL'] as
        | string
        | undefined;
      if (prodUrl && typeof prodUrl === 'string' && prodUrl.trim()) {
        return normalizeApiUrl(prodUrl.trim());
      }
    }
    // default (local): use proxy to localhost backend
    return '/api';
  }

  // In production, check for environment variable first
  const apiUrl: string | undefined = import.meta.env['VITE_API_URL'] as
    | string
    | undefined;
  if (apiUrl && typeof apiUrl === 'string') {
    return normalizeApiUrl(apiUrl);
  }

  // Default fallback for production
  return '/api';
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  paramsSerializer: (params) => {
    if (params instanceof URLSearchParams) {
      return params.toString();
    }
    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (Array.isArray(value)) {
        value.forEach((v: string | number | boolean) =>
          parts.push(`${key}=${encodeURIComponent(v)}`)
        );
      } else if (value !== undefined && value !== null) {
        parts.push(
          `${key}=${encodeURIComponent(value as string | number | boolean)}`
        );
      }
    }
    return parts.join('&');
  },
});

// Token storage key
const TOKEN_STORAGE_KEY = 'access_token';

// Get token from storage
export const getStoredToken = (): string | null => {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

// Store token in localStorage
export const setStoredToken = (token: string): void => {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
};

// Remove token from storage
export const removeStoredToken = (): void => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
};

// Request interceptor to add Bearer token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
  }
);

apiClient.interceptors.response.use(
  (response) => {
    // Check for new access token in response header (e.g., after username change)
    const newToken = response.headers['x-new-access-token'] as
      | string
      | undefined;
    if (newToken && typeof newToken === 'string') {
      setStoredToken(newToken);
    }
    return response;
  },
  (error: unknown) => {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 401) {
      // Handle unauthorized access, e.g., redirect to login
      //window.location.href = '/login';
    }
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
  }
);

// User API
export const usersApi = {
  getMe: () => apiClient.get<UserRead>('/users/me'),
  createUser: (data: UserCreate) => apiClient.post<UserRead>('/users/', data),
  getUser: (userId: string) => apiClient.get<UserRead>(`/users/${userId}`),
  updateUser: (userId: string, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: string) =>
    apiClient.delete<UserRead>(`/users/${userId}`),

  // Profile picture endpoints
  uploadProfilePicture: (file: File): Promise<{ data: UserRead }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<UserRead>('/users/me/profile-picture', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  deleteProfilePicture: () =>
    apiClient.delete<UserRead>('/users/me/profile-picture'),

  // List and count endpoints
  listUsers: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<UserRead[]>('/users/', { params }),
  countUsers: () => apiClient.get<{ count: number }>('/users/count'),

  // Admin endpoints
  getAllUsers: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<PaginatedResponse<UserRead>>('/users/admin/users', {
      params,
    }),
  adminUpdateUser: (userId: string, data: AdminUserUpdate) =>
    apiClient.put<UserRead>(`/users/admin/users/${userId}`, data),
  adminDeleteUser: (userId: string) =>
    apiClient.delete<UserRead>(`/users/admin/users/${userId}`),
};

// Car API (read-only; cars are seeded from backend car_generations_data)
export const carGenerationsApi = {
  getCar: (carId: string) =>
    apiClient.get<CarGenerationRead>(`/car-generations/${carId}`),
  listCars: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/', { params }),
  searchCars: (q: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/search', {
      params: { q, ...params },
    }),
  getCarsByMake: (make: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarGenerationRead[]>(
      `/car-generations/car-makes/${encodeURIComponent(make)}`,
      {
        params,
      }
    ),
  getCarsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(
      `/car-generations/car-makes/${encodeURIComponent(make)}/car-models/${encodeURIComponent(model)}`,
      { params }
    ),
  getCarsByIds: (ids: string[]) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/by-ids', {
      params: { ids },
    }),
  // Stats and count endpoints
  getCarMakeStats: () =>
    apiClient.get<Record<string, number>>('/car-generations/stats/car-makes'),
  countCars: () => apiClient.get<{ count: number }>('/car-generations/count'),
  countMakes: () =>
    apiClient.get<{ count: number }>('/car-generations/car-makes/count'),
  countCarModels: () =>
    apiClient.get<{ count: number }>('/car-generations/car-models/count'),
};

// Build List API
export const buildListsApi = {
  createBuildList: (data: BuildListCreate) =>
    apiClient.post<BuildListRead>('/build-lists/', data),
  getBuildList: (buildListId: string) =>
    apiClient.get<BuildListRead>(`/build-lists/${buildListId}`),
  updateBuildList: (buildListId: string, data: BuildListUpdate) =>
    apiClient.put<BuildListRead>(`/build-lists/${buildListId}`, data),
  deleteBuildList: (buildListId: string) =>
    apiClient.delete<BuildListRead>(`/build-lists/${buildListId}`),

  // List and filter endpoints
  listBuildLists: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }) => apiClient.get<BuildListRead[]>('/build-lists/', { params }),
  getBuildListsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    car_id?: string;
    car_ids?: string[];
    owner_id?: string;
    min_cost_cents?: number;
    max_cost_cents?: number;
    sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
  }) =>
    apiClient.get<PaginatedResponse<BuildListReadWithVotes>>(
      '/build-lists/with-votes',
      {
        params,
      }
    ),
  getBuildListsByCar: (
    carId: string,
    params?: { skip?: number; limit?: number; search?: string }
  ) =>
    apiClient.get<PaginatedResponse<BuildListRead>>(
      `/build-lists/car/${carId}`,
      { params }
    ),
  getBuildListsByUser: (
    userId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<BuildListRead[]>(`/build-lists/user/${userId}`, { params }),

  // Count endpoint
  countBuildLists: () => apiClient.get<{ count: number }>('/build-lists/count'),

  // Copy build list
  copyBuildList: (buildListId: string, newName?: string) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/copy`, {
      new_name: newName || null,
    }),

  // Phases (priority groups) for a build list
  getPhases: (buildListId: string) =>
    apiClient.get<BuildListPhaseRead[]>(`/build-lists/${buildListId}/phases`),
  createPhase: (buildListId: string, data: BuildListPhaseCreate) =>
    apiClient.post<BuildListPhaseRead>(
      `/build-lists/${buildListId}/phases`,
      data
    ),
};

// Build list phases API (update/delete by phase ID)
export const buildListPhasesApi = {
  updatePhase: (phaseId: string, data: BuildListPhaseUpdate) =>
    apiClient.put<BuildListPhaseRead>(`/build-list-phases/${phaseId}`, data),
  deletePhase: (phaseId: string) =>
    apiClient.delete<BuildListPhaseRead>(`/build-list-phases/${phaseId}`),
};

// Global Parts API (Global shared parts in the catalog)
export const partsApi = {
  // Get all global parts with filtering
  getParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    car_id?: string;
    search?: string;
  }) => apiClient.get<PartRead[]>('/parts/', { params }),

  // Get global parts with vote data
  getPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    category_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    part_manufacturer_id?: string;
    part_manufacturer_ids?: string[];
    user_id?: string;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    universal?: boolean;
    // Set false to hide community-contributed (user_created) parts.
    include_ugc?: boolean;
  }) =>
    apiClient.get<PaginatedResponse<PartReadWithVotes>>('/parts/with-votes', {
      params,
    }),

  // Get available filter options given current filters (for cascading filters)
  getFilterOptions: (params?: {
    category_ids?: string[];
    part_manufacturer_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    search?: string;
    user_id?: string;
    universal?: boolean;
    include_ugc?: boolean;
  }) =>
    apiClient.get<{
      category_ids: string[];
      part_manufacturer_ids: string[];
      car_ids?: string[];
      make_names?: string[];
    }>('/parts/filter-options', { params }),

  // Filter by category
  getPartsByCategory: (
    categoryId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(`/parts/category/${categoryId}`, {
      params: { filter_id: categoryId, ...params },
    }),

  // Create a new global part
  createPart: (data: PartCreate) => apiClient.post<PartRead>('/parts/', data),

  // Get specific global part
  getPart: (partId: string) => apiClient.get<PartRead>(`/parts/${partId}`),

  // Get retailer listings for a part (price by retailer)
  getPartListings: (partId: string) =>
    apiClient.get<PartListingReadWithRetailer[]>(`/parts/${partId}/listings`),

  // Get price history for a part (optional filter by retailer)
  getPartPriceHistory: (partId: string, params?: { retailer_id?: string }) =>
    apiClient.get<PartPriceHistoryReadWithRetailer[]>(
      `/parts/${partId}/price-history`,
      { params }
    ),

  // Update global part
  updatePart: (partId: string, data: PartUpdate) =>
    apiClient.put<PartRead>(`/parts/${partId}`, data),

  // Delete global part
  deletePart: (partId: string) =>
    apiClient.delete<PartRead>(`/parts/${partId}`),

  // Image management (requires edit permission)
  appendPartImages: (partId: string, fileKeys: string[]) =>
    apiClient.post<PartRead>(`/parts/${partId}/append-images`, {
      file_keys: fileKeys,
    }),
  removePartImage: (partId: string, imageIndex: number) =>
    apiClient.delete<PartRead>(`/parts/${partId}/images/${imageIndex}`),
  setPartPrimaryImage: (partId: string, index: number) =>
    apiClient.patch<PartRead>(`/parts/${partId}/primary-image`, {
      index,
    }),

  // Count endpoints
  countParts: () => apiClient.get<{ count: number }>('/parts/count'),
  countPartsByUser: (userId: string) =>
    apiClient.get<{ count: number }>(`/parts/user/${userId}/count`),

  // Check if product URL exists
  checkProductUrl: (productUrl: string) =>
    apiClient.get<{ existing_part_id: string | null }>('/parts/check-url', {
      params: { product_url: productUrl },
    }),
};

// Categories API (read-only; categories are seeded from backend part_categories_data)
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories/'),
  getCategory: (categoryId: string) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  getPartsByCategory: (
    categoryId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(`/categories/${categoryId}/parts`, {
      params,
    }),

  // Count endpoints
  getCategoryPartsCount: (categoryId: string) =>
    apiClient.get<{ count: number }>(`/categories/${categoryId}/parts-count`),
  countCategories: () => apiClient.get<{ count: number }>('/categories/count'),
};

// PartManufacturers API
export const partManufacturersApi = {
  getPartManufacturers: (activeOnly: boolean = true) =>
    apiClient.get<PartManufacturerResponse[]>('/part-manufacturers/', {
      params: { active_only: activeOnly },
    }),
  searchPartManufacturers: (
    q: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartManufacturerResponse[]>('/part-manufacturers/search', {
      params: { q, ...params },
    }),
  getPartManufacturer: (part_manufacturerId: string) =>
    apiClient.get<PartManufacturerResponse>(
      `/part-manufacturers/${part_manufacturerId}`
    ),
  createPartManufacturer: (data: PartManufacturerCreate) =>
    apiClient.post<PartManufacturerResponse>('/part-manufacturers/', data),
  updatePartManufacturer: (
    part_manufacturerId: string,
    data: PartManufacturerUpdate
  ) =>
    apiClient.put<PartManufacturerResponse>(
      `/part-manufacturers/${part_manufacturerId}`,
      data
    ),
  deletePartManufacturer: (part_manufacturerId: string) =>
    apiClient.delete<Record<string, string>>(
      `/part-manufacturers/${part_manufacturerId}`
    ),
  getPartsByPartManufacturer: (
    part_manufacturerId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(
      `/part-manufacturers/${part_manufacturerId}/parts`,
      {
        params,
      }
    ),
  getPartManufacturerPartsCount: (part_manufacturerId: string) =>
    apiClient.get<{ parts_count: number }>(
      `/part-manufacturers/${part_manufacturerId}/parts-count`
    ),
  countPartManufacturers: () =>
    apiClient.get<{ count: number }>('/part-manufacturers/count'),
};

// Retailers API (part stores/sites)
export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};

// Unified Votes API
export const votesApi = {
  voteOnEntity: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string,
    data: VoteCreate
  ) => apiClient.post<VoteRead>(`/votes/${entityType}/${entityId}`, data),
  removeVote: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string
  ) =>
    apiClient.delete<Record<string, string>>(
      `/votes/${entityType}/${entityId}`
    ),
  getVoteSummary: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string
  ) => apiClient.get<VoteSummary>(`/votes/${entityType}/${entityId}/summary`),
  getFlaggedEntities: (
    entityType: 'car_generation' | 'build_list' | 'part',
    limit?: number
  ) =>
    apiClient.get<FlaggedEntitySummary[]>(
      `/votes/admin/flagged/${entityType}`,
      { params: { limit } }
    ),
  countVotes: () => apiClient.get<{ count: number }>('/votes/count'),
};

// Unified Reports API
export const reportsApi = {
  reportEntity: (
    entityType: 'build_list' | 'part',
    entityId: string,
    data: ReportCreate
  ) => apiClient.post<ReportRead>(`/reports/${entityType}/${entityId}`, data),
  getReports: (params?: {
    entity_type?: 'build_list' | 'part';
    status?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<ReportRead[]>('/reports/admin/list', {
      params,
    }),
  getReportsWithDetails: (params?: {
    entity_type?: 'build_list' | 'part';
    status?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<PaginatedResponse<ReportWithDetails>>(
      '/reports/admin/list-with-details',
      {
        params,
      }
    ),
  getMyReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    apiClient.get<ReportRead[]>('/reports/my-reports', { params }),
  getReport: (reportId: string) =>
    apiClient.get<ReportWithDetails>(`/reports/${reportId}`),
  updateReport: (reportId: string, data: ReportUpdate) =>
    apiClient.put<ReportRead>(`/reports/${reportId}`, data),
  deleteReport: (reportId: string) =>
    apiClient.delete<Record<string, string>>(`/reports/${reportId}`),
  countReports: () => apiClient.get<{ count: number }>('/reports/count'),
};

// Legacy APIs for backward compatibility (will be removed in future versions)
export const partVotesApi = {
  voteOnPart: (partId: string, data: { vote_type: 'upvote' | 'downvote' }) =>
    votesApi.voteOnEntity('part', partId, {
      vote_type: data.vote_type,
      entity_type: 'part',
      entity_id: partId,
    }),
  removeVote: (partId: string) => votesApi.removeVote('part', partId),
  getVoteSummary: (partId: string) => votesApi.getVoteSummary('part', partId),
  getFlaggedParts: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('part', params?.limit),
};

export const buildListVotesApi = {
  voteOnBuildList: (
    buildListId: string,
    data: { vote_type: 'upvote' | 'downvote' }
  ) =>
    votesApi.voteOnEntity('build_list', buildListId, {
      vote_type: data.vote_type,
      entity_type: 'build_list',
      entity_id: buildListId,
    }),
  removeVote: (buildListId: string) =>
    votesApi.removeVote('build_list', buildListId),
  getVoteSummary: (buildListId: string) =>
    votesApi.getVoteSummary('build_list', buildListId),
  getFlaggedBuildLists: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('build_list', params?.limit),
};

export const partReportsApi = {
  reportPart: (
    partId: string,
    data: { reason: string; description?: string | null }
  ) =>
    reportsApi.reportEntity('part', partId, {
      reason: data.reason as
        | 'inappropriate_content'
        | 'spam'
        | 'inaccurate'
        | 'duplicate'
        | 'other',
      description: data.description ?? null,
    }),
  getReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    reportsApi.getReports({ ...params, entity_type: 'part' }),
  getReport: (reportId: string) => reportsApi.getReport(reportId),
  updateReport: (
    reportId: string,
    data: { status: string; admin_notes?: string | null }
  ) =>
    reportsApi.updateReport(reportId, {
      status: data.status as 'pending' | 'reviewed' | 'resolved' | 'dismissed',
      admin_notes: data.admin_notes ?? null,
    }),
};

// Build List Parts API (Relationships between global parts and build lists)
export const buildListPartsApi = {
  // Create a new global part and add it to a build list as a build list part
  createPartAndAddToBuildList: (
    buildListId: string,
    partData: PartCreate,
    buildListPartData: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartReadWithPart>(
      `/build-list-parts/${buildListId}/create-and-add-part`,
      {
        name: partData.name,
        description: partData.description,
        image_urls: partData.image_urls,
        category_id: partData.category_id,
        car_ids: partData.car_ids ?? undefined,
        is_universal: partData.is_universal ?? false,
        part_manufacturer_id: partData.part_manufacturer_id,
        part_number: partData.part_number,
        specifications: partData.specifications,
        retailer_id: partData.retailer_id,
        price_cents: partData.price_cents,
        product_url: partData.product_url,
        quantity: buildListPartData.quantity ?? 1,
        notes: buildListPartData.notes,
        build_list_phase_id: buildListPartData.build_list_phase_id ?? undefined,
      }
    ),
  // Add an existing global part to a build list as a build list part
  addPartToBuildList: (
    buildListId: string,
    partId: string,
    data: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`,
      {
        ...data,
        build_list_phase_id: data.build_list_phase_id ?? undefined,
      }
    ),
  // Update a build list part (notes, etc.) by build list and global part IDs
  updateBuildListPart: (
    buildListId: string,
    partId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`,
      data
    ),
  // Update a build list part by its own ID
  updateBuildListPartById: (
    buildListPartId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListPartId}`,
      data
    ),
  // Remove a build list part from a build list (doesn't delete the global part)
  removeBuildListPart: (buildListId: string, partId: string) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`
    ),
  // Delete a build list part by its own ID
  deleteBuildListPartById: (buildListPartId: string) =>
    apiClient.delete<BuildListPartRead>(`/build-list-parts/${buildListPartId}`),
  // Get all build list parts in a build list (basic info)
  getBuildListPartsBasic: (buildListId: string) =>
    apiClient.get<BuildListPartRead[]>(`/build-list-parts/${buildListId}`),
  // Get all build list parts in a build list (with global part details)
  getBuildListParts: (buildListId: string) =>
    apiClient.get<BuildListPartReadWithPart[]>(
      `/build-list-parts/${buildListId}/parts`
    ),
  // Count build lists containing a specific global part
  countBuildListsContainingPart: (partId: string) =>
    apiClient.get<{ count: number }>(
      `/build-list-parts/parts/${partId}/build-lists/count`
    ),
  // Count all build list parts
  countBuildListParts: () =>
    apiClient.get<{ count: number }>('/build-list-parts/count'),
};

// Auth API
export const authApi = {
  login: async (
    data: BodyLoginForAccessToken
  ): Promise<AxiosResponse<UserRead | LoginResponse>> => {
    const response = await apiClient.post<LoginResponse>('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    // If 2FA is required, return the response as-is
    if (response.data.requires_2fa) {
      return response;
    }
    // Store the token
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    // Return response with user data as the main data field
    return {
      ...response,
      data: response.data.user!,
    } as AxiosResponse<UserRead>;
  },
  loginWith2FA: async (
    data: TOTPLoginRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/token/2fa', data);
    // Store the token
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    // Return response with user data as the main data field
    return {
      ...response,
      data: response.data.user,
    } as AxiosResponse<UserRead>;
  },
  setup2FA: () => apiClient.post<TOTPSetupResponse>('/auth/2fa/setup'),
  verify2FA: (data: TOTPVerifyRequest) =>
    apiClient.post<TOTPVerifyResponse>('/auth/2fa/verify', data),
  disable2FA: (data: TOTPDisableRequest) =>
    apiClient.post<Record<string, string>>('/auth/2fa/disable', data),
  verifyEmail: (data: BodyVerifyEmail) =>
    apiClient.post<Record<string, string>>('/auth/verify-email', data),
  verifyEmailConfirm: (token: string) =>
    apiClient.get<Record<string, string>>('/auth/verify-email/confirm', {
      params: { token },
    }),
  resetPassword: (data: BodyResetPassword) =>
    apiClient.post<Record<string, string>>('/auth/reset-password', data),
  resetPasswordConfirm: (token: string, data: NewPassword) =>
    apiClient.post<Record<string, string>>('/auth/reset-password/confirm', {
      token,
      new_password: data,
    }),
  logout: async () => {
    const response =
      await apiClient.post<Record<string, string>>('/auth/logout');
    // Remove token from storage
    removeStoredToken();
    return response;
  },

  webauthnRegisterOptions: (nickname: string) =>
    apiClient.post<WebAuthnOptionsResponse>('/auth/webauthn/register/options', {
      nickname,
    }),
  webauthnRegisterVerify: (data: {
    challenge_token: string;
    credential: unknown;
    nickname: string;
  }) =>
    apiClient.post<WebAuthnCredentialSummary>(
      '/auth/webauthn/register/verify',
      data
    ),
  webauthnLoginOptions: (username?: string) =>
    apiClient.post<WebAuthnOptionsResponse>('/auth/webauthn/login/options', {
      username,
    }),
  webauthnLoginVerify: async (data: {
    challenge_token: string;
    credential: unknown;
  }): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/webauthn/login/verify', data);
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    return {
      ...response,
      data: response.data.user,
    } as AxiosResponse<UserRead>;
  },
  webauthnListCredentials: () =>
    apiClient.get<WebAuthnCredentialSummary[]>('/auth/webauthn/credentials'),
  webauthnRenameCredential: (id: string, nickname: string) =>
    apiClient.patch<WebAuthnCredentialSummary>(
      `/auth/webauthn/credentials/${id}`,
      { nickname }
    ),
  webauthnDeleteCredential: (id: string) =>
    apiClient.delete<Record<string, string>>(
      `/auth/webauthn/credentials/${id}`
    ),

  // Google sign-in. The first call returns one of four shapes (token / 2fa / link
  // required / signup required); the caller dispatches on the discriminator. Token
  // storage happens in the page handler so the merge / signup flows can complete first.
  googleSignIn: (data: GoogleSignInRequest) =>
    apiClient.post<GoogleSignInResponse>('/auth/google', data),
  googleLink: async (
    data: GoogleLinkRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/google/link', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  googleSignup: async (
    data: GoogleSignupRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/google/signup', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  oauthTwoFactor: async (
    data: OAuthTwoFactorRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/oauth/2fa', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  googleConnect: (data: GoogleConnectRequest) =>
    apiClient.post<OAuthAccountRead>('/auth/google/connect', data),
  listOAuthAccounts: () => apiClient.get<OAuthAccountRead[]>('/auth/oauth'),
  deleteOAuthAccount: (id: string) =>
    apiClient.delete<Record<string, string>>(`/auth/oauth/${id}`),
};

export interface WebAuthnOptionsResponse {
  options: Record<string, unknown>;
  challenge_token: string;
}

export interface WebAuthnCredentialSummary {
  id: string;
  nickname: string;
  aaguid?: string | null;
  transports?: string[] | null;
  backup_eligible: boolean;
  backup_state: boolean;
  created_at: string;
  last_used_at?: string | null;
}

// Search API
export interface SearchCategoryResults<T> {
  data: T[];
  total: number;
  has_next: boolean;
  skip: number;
  limit: number;
}

export interface SearchResults {
  build_lists: SearchCategoryResults<BuildListRead>;
  users: SearchCategoryResults<UserRead>;
  parts: SearchCategoryResults<PartRead>;
  query: string;
}

export const searchApi = {
  search: (params: { q: string; skip?: number; limit?: number }) =>
    apiClient.get<SearchResults>('/search/', { params }),
};

// Utility/Health API
export const utilityApi = {
  getRoot: () => apiClient.get<Record<string, string>>('/'),
  healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
};

// Image upload API
export interface ImageUploadResponse {
  file_key: string;
  presigned_url: string;
  message: string;
}

export interface PresignedUrlResponse {
  presigned_url: string;
  file_key: string;
}

export const imageApi = {
  uploadImage: async (
    file: File,
    entityType: string,
    entityId?: string
  ): Promise<ImageUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    params.append('entity_type', entityType);
    if (entityId !== undefined) {
      params.append('entity_id', entityId.toString());
    }

    const response = await apiClient.post<ImageUploadResponse>(
      `/images/upload?${params.toString()}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  getPresignedUrl: (
    fileKey: string,
    expiration?: number
  ): Promise<PresignedUrlResponse> => {
    const params = new URLSearchParams();
    params.append('file_key', fileKey);
    if (expiration !== undefined) {
      params.append('expiration', expiration.toString());
    }
    return apiClient
      .get<PresignedUrlResponse>(`/images/presigned-url?${params.toString()}`)
      .then((response) => response.data);
  },

  deleteImage: (
    fileKey: string
  ): Promise<{ message: string; file_key: string }> => {
    const params = new URLSearchParams();
    params.append('file_key', fileKey);
    return apiClient
      .delete<{
        message: string;
        file_key: string;
      }>(`/images/delete?${params.toString()}`)
      .then((response) => response.data);
  },

  countBucketObjects: () =>
    apiClient.get<{ count: number }>('/images/admin/count'),

  /** Single S3 pass: total plus counts by standard key prefix (admin only). */
  getBucketCountByEntityType: () =>
    apiClient.get<BucketEntityTypeCountResponse>(
      '/images/admin/count-by-entity-type'
    ),

  /** Dry run: list bucket object keys not referenced by any entity (admin only). */
  getOrphanedBucketObjects: () =>
    apiClient.get<{
      orphaned_keys: string[];
      count: number;
      total_bucket: number;
      total_referenced: number;
    }>('/images/admin/orphaned'),

  /** Delete bucket objects not referenced by any entity (admin only). Non-destructive. */
  purgeOrphanedBucketObjects: () =>
    apiClient.post<{ deleted: number; deleted_keys: string[] }>(
      '/images/admin/purge-orphaned'
    ),
};

// Build Logs API
export const buildLogsApi = {
  getBuildLogByBuildList: (
    buildListId: string,
    skip?: number,
    limit?: number
  ) => {
    const params = new URLSearchParams();
    if (skip !== undefined) params.append('skip', skip.toString());
    if (limit !== undefined) params.append('limit', limit.toString());
    const queryString = params.toString();
    return apiClient.get<BuildLogReadPaginated>(
      `/build-logs/build-list/${buildListId}${queryString ? `?${queryString}` : ''}`
    );
  },
  createBuildLogPost: (buildListId: string, data: BuildLogPostCreate) =>
    apiClient.post<BuildLogPostRead>(
      `/build-logs/build-list/${buildListId}/posts`,
      data
    ),
  updateBuildLogPost: (postId: string, data: BuildLogPostUpdate) =>
    apiClient.put<BuildLogPostRead>(`/build-logs/posts/${postId}`, data),
  deleteBuildLogPost: (postId: string) =>
    apiClient.delete<{ message: string }>(`/build-logs/posts/${postId}`),
  countBuildLogPosts: () =>
    apiClient.get<{ count: number }>('/build-logs/posts/count'),
};

// Bug Reports API
export const bugReportsApi = {
  createBugReport: (data: BugReportCreate) =>
    apiClient.post<BugReportRead>('/bug-reports/', data),
  getBugReports: (params?: {
    status?: string;
    priority?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<BugReportRead[]>('/bug-reports/admin/list', {
      params,
    }),
  getBugReportsWithDetails: (params?: {
    status?: string;
    priority?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<PaginatedResponse<BugReportWithDetails>>(
      '/bug-reports/admin/list-with-details',
      {
        params,
      }
    ),
  getBugReport: (bugReportId: string) =>
    apiClient.get<BugReportWithDetails>(`/bug-reports/${bugReportId}`),
  updateBugReport: (bugReportId: string, data: BugReportUpdate) =>
    apiClient.put<BugReportRead>(`/bug-reports/${bugReportId}`, data),
  deleteBugReport: (bugReportId: string) =>
    apiClient.delete<Record<string, string>>(`/bug-reports/${bugReportId}`),
  countBugReports: () => apiClient.get<{ count: number }>('/bug-reports/count'),
};

// Admin API
export interface MigrationResult {
  success: boolean;
  output: string;
  error: string | null;
  current_revision: string | null;
}

export interface CurrentRevisionResult {
  current_revision: string;
  output: string;
}

export interface InitDataResult {
  success: boolean;
  message: string;
}

/** A persisted background job record. */
export interface BackgroundJob {
  id: string;
  job_type: 'crawler_run' | 'archive_rescrape';
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  triggered_by: 'manual' | 'scheduled';
  params: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  last_heartbeat_at: string | null;
  worker_instance_id: string | null;
  created_by_user_id: string | null;
}

export interface BackgroundJobList {
  items: BackgroundJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface CrawlerAdapterProgress {
  parsed_this_run: number;
  last_parsed_at: string | null;
}

export interface CrawlerJobProgress {
  job_id: string;
  status: string;
  started_at: string | null;
  now: string;
  adapters: Record<string, CrawlerAdapterProgress>;
}

/** Response when starting a crawler job (returns immediately; job runs in background). */
export interface CrawlerRunResponse {
  status: 'started';
  job_id: string;
  adapters: string[];
  triggered_by: 'manual' | 'scheduled';
  message: string;
}

export interface CrawlerServiceAccount {
  id: string;
  username: string;
  email: string;
  is_service_account: true;
  created_at: string;
}

export interface CrawlerRunRequest {
  adapters: string[];
  crawler_user_id?: string;
  crawler_default_category_id: string;
  limits?: Record<string, number>;
  global_limit?: number | null;
  parallel?: boolean;
  /** Seconds between requests per crawler (0.5–60). Default 5 for polite/heavy runs. */
  delay_sec?: number | null;
  crawl_html_save_dir?: string | null;
  /** Skip URLs already in crawled_pages with parse_status='parsed'. Useful for successive test runs. */
  skip_known_urls?: boolean;
}

/** Admin: re-parse every archived crawled page (full ingest + inference + price history when price is present). */
export interface RescrapeArchivesRequest {
  crawler_user_id?: string;
  default_category_id: string;
}

export interface RescrapeArchivesQueuedResponse {
  status: string;
  job_id: string;
  triggered_by: 'manual' | 'scheduled';
  message: string;
}

/** Admin-only: S3 user-images bucket totals grouped by upload key prefix (entity_type). */
export interface BucketEntityTypeCountResponse {
  total: number;
  by_entity_type: Record<string, number>;
  other: number;
  /** Total stored data in GB (sum of all object sizes). */
  size_gb?: number;
}

/** Admin-only: supplemental DB table row counts plus votes/reports by entity_type. */
export interface AdminTableCountsResponse {
  build_list_phases: number;
  crawled_pages: number;
  part_listings: number;
  part_price_histories: number;
  image_source_mappings: number;
  build_logs: number;
  part_cars: number;
  background_jobs: number;
  oauth_accounts: number;
  webauthn_credentials: number;
  crawler_adapter_configs: number;
  crawler_schedules: number;
  crawler_schedule_adapters: number;
  votes_by_entity_type: Record<string, number>;
  reports_by_entity_type: Record<string, number>;
}

/** Admin-only: full S3 listing of the crawl HTML bucket. On-demand; scans every key. */
export interface CrawlBucketSummaryResponse {
  /** True when CRAWL_BUCKET is set and the S3 client initialized (scraped HTML may live here). */
  crawl_bucket_configured: boolean;
  crawl_bucket_total: number;
  crawl_bucket_by_prefix: Record<string, number>;
  /** Total data stored in the crawl bucket in GB (sum of all object sizes). */
  crawl_bucket_size_gb?: number;
  /** Present when listing the crawl bucket failed after configuration. */
  crawl_bucket_error?: string;
}

/** One member of a canonical-part link group. */
export interface CanonicalLinkGroupMember {
  id: string;
  name: string;
  source: string;
  is_canonical: boolean;
  /** Linker election score; higher wins when picking a canonical. */
  richness_score: number;
  /** First image file key / URL for thumbnailing, if any. */
  image_url: string | null;
  /** Product URL at the member's retailer (from the first PartListing). */
  product_url: string | null;
  /** Retailer of the member's first PartListing. */
  retailer_id: string | null;
  created_at: string;
}

export interface CanonicalLinkGroupResponse {
  canonical_id: string;
  members: CanonicalLinkGroupMember[];
}

/** One Part whose first PartListing has a product_url matching a lookup query. */
export interface UrlLookupMatch {
  part_id: string;
  name: string;
  source: string;
  is_canonical: boolean;
  /** Canonical of this part's link group (self when canonical). */
  canonical_id: string;
  retailer_id: string | null;
}

export interface UrlLookupResponse {
  normalized_url: string;
  /**
   * All parts matching this URL. Non-UGC parts are unique on URL; UGC rows may
   * share a URL by design, so multiple matches are possible.
   */
  matches: UrlLookupMatch[];
}

/** One entry in the rescan diff: before/after canonical and the action that would be taken. */
export interface RescanDiffEntry {
  part_id: string;
  before_canonical_id: string | null;
  after_canonical_id: string | null;
  /** "link" | "reelect" | "unchanged". Only non-unchanged entries appear in the sample. */
  action: string;
}

/** Full-catalog rescan summary. */
export interface RescanResponse {
  dry_run: boolean;
  scanned: number;
  changes: number;
  diff_sample: RescanDiffEntry[];
  diff_truncated: boolean;
}

/** Per-adapter retailer tuning (delay, limit, skip flag, default category). */
export interface CrawlerAdapterConfig {
  id: string;
  adapter_name: string;
  delay_sec: number;
  per_run_limit: number | null;
  skip_known_urls: boolean;
  default_category_id: string;
  created_at: string;
  updated_at: string;
}

export interface CrawlerAdapterConfigList {
  items: CrawlerAdapterConfig[];
}

export interface CrawlerAdapterConfigUpdate {
  delay_sec?: number;
  per_run_limit?: number | null;
  /** Set true to clear per_run_limit (unlimited). Takes precedence over per_run_limit. */
  clear_per_run_limit?: boolean;
  skip_known_urls?: boolean;
  default_category_id?: string;
}

/** A user-defined crawler schedule with its adapter membership. */
export interface CrawlerSchedule {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  schedule_expression: string;
  last_reconciled_at: string | null;
  last_reconcile_error: string | null;
  created_at: string;
  updated_at: string;
  adapters: { adapter_name: string }[];
}

export interface CrawlerScheduleList {
  items: CrawlerSchedule[];
  presets: Record<string, string>;
}

export interface CrawlerScheduleCreate {
  name: string;
  description?: string | null;
  enabled?: boolean;
  schedule_expression?: string;
  preset?: 'monthly' | 'weekly' | 'daily';
  adapters: string[];
}

export interface CrawlerScheduleUpdate {
  description?: string | null;
  enabled?: boolean;
  schedule_expression?: string;
  preset?: 'monthly' | 'weekly' | 'daily';
  adapters?: string[];
}

export interface CrawlerReconcileResult {
  schedule_name: string;
  ok: boolean;
  error: string | null;
}

export interface CrawlerReconcileAllResponse {
  results: CrawlerReconcileResult[];
}

export interface AppSettings {
  ads_disabled_global: boolean;
  updated_at: string;
}

export interface AppSettingsUpdate {
  ads_disabled_global?: boolean;
}

export const appSettingsApi = {
  /** Public: fetch global app settings (e.g. global ads toggle). */
  get: () => apiClient.get<AppSettings>('/app-settings/'),
  /** Admin-only: update global app settings. */
  update: (body: AppSettingsUpdate) =>
    apiClient.put<AppSettings>('/app-settings/', body),
};

export const adminApi = {
  runMigrations: () => apiClient.post<MigrationResult>('/admin/migrations/run'),
  getCurrentRevision: () =>
    apiClient.get<CurrentRevisionResult>('/admin/migrations/current'),
  initCarGenerations: () =>
    apiClient.post<InitDataResult>('/admin/init/car-generations'),
  initPartCategories: () =>
    apiClient.post<InitDataResult>('/admin/init/part-categories'),

  // Crawlers
  getCrawlers: () =>
    apiClient.get<{
      adapters: string[];
      adapter_info: { name: string; tier: 'http' | 'tls' | 'browser' }[];
    }>('/admin/crawlers'),
  getCrawlerServiceAccount: () =>
    apiClient.get<CrawlerServiceAccount>('/admin/service-accounts/crawler'),
  runCrawlers: (body: CrawlerRunRequest) =>
    apiClient.post<CrawlerRunResponse>('/admin/crawlers/run', body),

  /** Re-parse all archived HTML into parts (background job; admin only). */
  rescrapeArchives: (body: RescrapeArchivesRequest) =>
    apiClient.post<RescrapeArchivesQueuedResponse>(
      '/admin/crawled-pages/rescrape-archives',
      body
    ),

  /** Admin: archived page count per source (adapter name or chrome_extension). */
  getCrawledPageCountsBySource: () =>
    apiClient.get<Record<string, number>>('/crawled-pages/counts-by-source'),

  /** Admin: per-source, per-parse_status counts — drives the parsed/total progress pill. */
  getCrawledPageCountsBySourceAndStatus: () =>
    apiClient.get<Record<string, Record<string, number>>>(
      '/crawled-pages/counts-by-source-and-status'
    ),

  /** Delete all global parts (admin only). Cascades to listings, votes, reports, build list parts. */
  deleteAllParts: () =>
    apiClient.post<{ deleted_count: number }>('/admin/parts/delete-all'),

  /** Delete all cars / car generations (admin only). Also deletes car models and makes for a clean init. */
  deleteAllCars: () =>
    apiClient.post<{
      deleted_count: number;
      deleted_car_models_count: number;
      deleted_makes_count: number;
    }>('/admin/cars/delete-all'),

  /** Delete all part_manufacturers (admin only). Nullifies part_manufacturer on parts first, then deletes all part_manufacturers. */
  deleteAllPartManufacturers: () =>
    apiClient.post<{ deleted_count: number }>(
      '/admin/part-manufacturers/delete-all'
    ),

  /** Supplemental table counts and polymorphic vote/report breakdown (admin only). */
  getTableCounts: () =>
    apiClient.get<AdminTableCountsResponse>('/admin/stats/table-counts'),

  /** On-demand S3 list of the crawl HTML bucket (admin only). Scans every key — slow on large buckets. */
  getCrawlBucketSummary: () =>
    apiClient.get<CrawlBucketSummaryResponse>('/admin/stats/crawl-bucket'),

  // Background jobs
  listJobs: (params?: {
    status?: string;
    job_type?: string;
    limit?: number;
    offset?: number;
  }) => apiClient.get<BackgroundJobList>('/admin/jobs', { params }),
  getJob: (jobId: string) =>
    apiClient.get<BackgroundJob>(`/admin/jobs/${jobId}`),
  getCrawlerJobProgress: (jobId: string) =>
    apiClient.get<CrawlerJobProgress>(`/admin/jobs/${jobId}/crawler-progress`),
  cancelJob: (jobId: string) =>
    apiClient.post<BackgroundJob>(`/admin/jobs/${jobId}/cancel`),

  // Crawler schedules (user-defined, N-to-N with adapters, reconciled to EventBridge)
  listCrawlerSchedules: () =>
    apiClient.get<CrawlerScheduleList>('/admin/crawler-schedules/'),
  createCrawlerSchedule: (body: CrawlerScheduleCreate) =>
    apiClient.post<CrawlerSchedule>('/admin/crawler-schedules/', body),
  updateCrawlerSchedule: (scheduleId: string, body: CrawlerScheduleUpdate) =>
    apiClient.patch<CrawlerSchedule>(
      `/admin/crawler-schedules/${scheduleId}`,
      body
    ),
  deleteCrawlerSchedule: (scheduleId: string) =>
    apiClient.delete<void>(`/admin/crawler-schedules/${scheduleId}`),
  reconcileCrawlerSchedules: () =>
    apiClient.post<CrawlerReconcileAllResponse>(
      '/admin/crawler-schedules/reconcile'
    ),

  // Per-adapter retailer tuning (used by every schedule the adapter is in)
  listCrawlerAdapterConfigs: () =>
    apiClient.get<CrawlerAdapterConfigList>('/admin/crawler-adapter-configs/'),
  updateCrawlerAdapterConfig: (
    adapterName: string,
    body: CrawlerAdapterConfigUpdate
  ) =>
    apiClient.patch<CrawlerAdapterConfig>(
      `/admin/crawler-adapter-configs/${adapterName}`,
      body
    ),

  // Canonical-part curation (admin-only)
  getPartLinkGroup: (partId: string) =>
    apiClient.get<CanonicalLinkGroupResponse>(
      `/admin/parts/${partId}/link-group`
    ),
  lookupPartsByProductUrl: (url: string) =>
    apiClient.get<UrlLookupResponse>('/admin/parts/lookup-by-url', {
      params: { url },
    }),
  promotePartToCanonical: (partId: string) =>
    apiClient.post<CanonicalLinkGroupResponse>(
      '/admin/parts/promote-canonical',
      { part_id: partId }
    ),
  unlinkPartFromCanonical: (partId: string) =>
    apiClient.post<CanonicalLinkGroupResponse>('/admin/parts/unlink', {
      part_id: partId,
    }),
  manuallyLinkParts: (body: { duplicate_id: string; canonical_id: string }) =>
    apiClient.post<CanonicalLinkGroupResponse>('/admin/parts/link', body),
  rescanPartsForCanonicalLinking: (body: {
    dry_run: boolean;
    batch_size?: number;
  }) => apiClient.post<RescanResponse>('/admin/parts/rescan', body),
};

export default apiClient;
