import axios, { type AxiosError, type AxiosResponse } from 'axios';
import type {
  AdminUserUpdate,
  BodyLoginForAccessToken,
  BodyResetPassword,
  BodyVerifyEmail,
  BrandCreate,
  BrandResponse,
  BrandUpdate,
  BugReportCreate,
  BugReportRead,
  BugReportUpdate,
  BugReportWithDetails,
  BuildListCreate,
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithGlobalPart,
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
  CarRead,
  CategoryResponse,
  FlaggedEntitySummary,
  GlobalPartCreate,
  GlobalPartRead,
  GlobalPartReadWithVotes,
  GlobalPartUpdate,
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
  timeout: 30000, // 30 seconds timeout to prevent indefinite hangs on cold starts
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
  getUser: (userId: number) => apiClient.get<UserRead>(`/users/${userId}`),
  updateUser: (userId: number, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: number) =>
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
  adminUpdateUser: (userId: number, data: AdminUserUpdate) =>
    apiClient.put<UserRead>(`/users/admin/users/${userId}`, data),
  adminDeleteUser: (userId: number) =>
    apiClient.delete<UserRead>(`/users/admin/users/${userId}`),
};

// Car API (read-only; cars are seeded from backend car_generations_data)
export const carsApi = {
  getCar: (carId: number) => apiClient.get<CarRead>(`/cars/${carId}`),
  listCars: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<CarRead[]>('/cars/', { params }),
  searchCars: (q: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>('/cars/search', { params: { q, ...params } }),
  getCarsByMake: (make: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>(`/cars/make/${encodeURIComponent(make)}`, {
      params,
    }),
  getCarsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarRead[]>(
      `/cars/make/${encodeURIComponent(make)}/model/${encodeURIComponent(model)}`,
      { params }
    ),
  getCarsByIds: (ids: number[]) =>
    apiClient.get<CarRead[]>('/cars/by-ids', { params: { ids } }),
  // Stats and count endpoints
  getCarMakeStats: () =>
    apiClient.get<Record<string, number>>('/cars/stats/makes'),
  countCars: () => apiClient.get<{ count: number }>('/cars/count'),
  countMakes: () => apiClient.get<{ count: number }>('/cars/makes/count'),
  countCarModels: () =>
    apiClient.get<{ count: number }>('/cars/car-models/count'),
};

// Car Generation API (read-only; uses /cars endpoints; Car = generation in backend)
export const carGenerationsApi = {
  getCarGeneration: (generationId: number) =>
    apiClient.get<CarGenerationRead>(`/cars/${generationId}`),
  listCarGenerations: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }) => apiClient.get<CarGenerationRead[]>('/cars/', { params }),
  getCarGenerationsByMake: (
    make: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(
      `/cars/make/${encodeURIComponent(make)}`,
      { params }
    ),
  getCarGenerationsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(
      `/cars/make/${encodeURIComponent(make)}/model/${encodeURIComponent(model)}`,
      { params }
    ),
  countCarGenerations: () => apiClient.get<{ count: number }>('/cars/count'),
};

// Build List API
export const buildListsApi = {
  createBuildList: (data: BuildListCreate) =>
    apiClient.post<BuildListRead>('/build-lists/', data),
  getBuildList: (buildListId: number) =>
    apiClient.get<BuildListRead>(`/build-lists/${buildListId}`),
  updateBuildList: (buildListId: number, data: BuildListUpdate) =>
    apiClient.put<BuildListRead>(`/build-lists/${buildListId}`, data),
  deleteBuildList: (buildListId: number) =>
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
    car_id?: number;
    car_ids?: number[];
    min_cost_cents?: number;
    max_cost_cents?: number;
    sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
  }) =>
    apiClient.get<PaginatedResponse<BuildListReadWithVotes>>(
      '/build-lists/with-votes',
      {
        params: params
          ? paramsWithArrays(params as Record<string, unknown>)
          : undefined,
      }
    ),
  getBuildListsByCar: (
    carId: number,
    params?: { skip?: number; limit?: number; search?: string }
  ) =>
    apiClient.get<PaginatedResponse<BuildListRead>>(
      `/build-lists/car/${carId}`,
      { params }
    ),
  getMyBuildLists: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<PaginatedResponse<BuildListRead>>('/build-lists/user/me', {
      params,
    }),
  getBuildListsByUser: (
    userId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<BuildListRead[]>(`/build-lists/user/${userId}`, { params }),

  // Count endpoint
  countBuildLists: () => apiClient.get<{ count: number }>('/build-lists/count'),

  // Copy build list
  copyBuildList: (buildListId: number, newName?: string) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/copy`, {
      new_name: newName || null,
    }),

  // Phases (priority groups) for a build list
  getPhases: (buildListId: number) =>
    apiClient.get<BuildListPhaseRead[]>(`/build-lists/${buildListId}/phases`),
  createPhase: (buildListId: number, data: BuildListPhaseCreate) =>
    apiClient.post<BuildListPhaseRead>(
      `/build-lists/${buildListId}/phases`,
      data
    ),
};

// Build list phases API (update/delete by phase ID)
export const buildListPhasesApi = {
  updatePhase: (phaseId: number, data: BuildListPhaseUpdate) =>
    apiClient.put<BuildListPhaseRead>(`/build-list-phases/${phaseId}`, data),
  deletePhase: (phaseId: number) =>
    apiClient.delete<BuildListPhaseRead>(`/build-list-phases/${phaseId}`),
};

// Serialize params so array values become repeated keys (category_ids=1&category_ids=2) for FastAPI
function paramsWithArrays(params: Record<string, unknown>): URLSearchParams {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => search.append(key, String(v)));
    } else if (typeof value === 'object') {
      search.append(key, JSON.stringify(value));
    } else if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean' ||
      typeof value === 'bigint'
    ) {
      search.append(key, String(value));
    } else if (typeof value === 'symbol') {
      search.append(key, value.toString());
    }
  }
  return search;
}

// Global Parts API (Global shared parts in the catalog)
export const globalPartsApi = {
  // Get all global parts with filtering
  getGlobalParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    car_id?: number;
    search?: string;
  }) => apiClient.get<GlobalPartRead[]>('/global-parts/', { params }),

  // Get global parts with vote data
  getGlobalPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    category_ids?: number[];
    car_id?: number;
    car_ids?: number[];
    brand_id?: number;
    brand_ids?: number[];
    user_id?: number;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    universal?: boolean;
  }) =>
    apiClient.get<PaginatedResponse<GlobalPartReadWithVotes>>(
      '/global-parts/with-votes',
      {
        params: params
          ? paramsWithArrays(params as Record<string, unknown>)
          : undefined,
      }
    ),

  // Get available filter options given current filters (for cascading filters)
  getFilterOptions: (params?: {
    category_ids?: number[];
    brand_ids?: number[];
    car_id?: number;
    car_ids?: number[];
    search?: string;
    user_id?: number;
    universal?: boolean;
  }) =>
    apiClient.get<{
      category_ids: number[];
      brand_ids: number[];
      car_ids?: number[];
      make_names?: string[];
    }>('/global-parts/filter-options', {
      params: params
        ? paramsWithArrays(params as Record<string, unknown>)
        : undefined,
    }),

  // Filter by category
  getGlobalPartsByCategory: (
    categoryId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<GlobalPartRead[]>(`/global-parts/category/${categoryId}`, {
      params: { filter_id: categoryId, ...params },
    }),

  // Create a new global part
  createGlobalPart: (data: GlobalPartCreate) =>
    apiClient.post<GlobalPartRead>('/global-parts/', data),

  // Get specific global part
  getGlobalPart: (partId: number) =>
    apiClient.get<GlobalPartRead>(`/global-parts/${partId}`),

  // Get retailer listings for a part (price by retailer)
  getGlobalPartListings: (partId: number) =>
    apiClient.get<PartListingReadWithRetailer[]>(
      `/global-parts/${partId}/listings`
    ),

  // Get price history for a part (optional filter by retailer)
  getGlobalPartPriceHistory: (
    partId: number,
    params?: { retailer_id?: number }
  ) =>
    apiClient.get<PartPriceHistoryReadWithRetailer[]>(
      `/global-parts/${partId}/price-history`,
      { params }
    ),

  // Update global part
  updateGlobalPart: (partId: number, data: GlobalPartUpdate) =>
    apiClient.put<GlobalPartRead>(`/global-parts/${partId}`, data),

  // Delete global part
  deleteGlobalPart: (partId: number) =>
    apiClient.delete<GlobalPartRead>(`/global-parts/${partId}`),

  // Image management (requires edit permission)
  removeGlobalPartImage: (partId: number, imageIndex: number) =>
    apiClient.delete<GlobalPartRead>(
      `/global-parts/${partId}/images/${imageIndex}`
    ),
  setGlobalPartPrimaryImage: (partId: number, index: number) =>
    apiClient.patch<GlobalPartRead>(`/global-parts/${partId}/primary-image`, {
      index,
    }),

  // Count endpoints
  countGlobalParts: () =>
    apiClient.get<{ count: number }>('/global-parts/count'),
  countGlobalPartsByUser: (userId: number) =>
    apiClient.get<{ count: number }>(`/global-parts/user/${userId}/count`),

  // Check if product URL exists
  checkProductUrl: (productUrl: string) =>
    apiClient.get<{ existing_part_id: number | null }>(
      '/global-parts/check-url',
      {
        params: { product_url: productUrl },
      }
    ),
};

// Categories API (read-only; categories are seeded from backend part_categories_data)
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories/'),
  getCategory: (categoryId: number) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  getPartsByCategory: (
    categoryId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<GlobalPartRead[]>(`/categories/${categoryId}/global-parts`, {
      params,
    }),

  // Count endpoints
  getCategoryPartsCount: (categoryId: number) =>
    apiClient.get<{ count: number }>(`/categories/${categoryId}/parts-count`),
  countCategories: () => apiClient.get<{ count: number }>('/categories/count'),
};

// Brands API
export const brandsApi = {
  getBrands: (activeOnly: boolean = true) =>
    apiClient.get<BrandResponse[]>('/brands/', {
      params: { active_only: activeOnly },
    }),
  searchBrands: (q: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<BrandResponse[]>('/brands/search', {
      params: { q, ...params },
    }),
  getBrand: (brandId: number) =>
    apiClient.get<BrandResponse>(`/brands/${brandId}`),
  createBrand: (data: BrandCreate) =>
    apiClient.post<BrandResponse>('/brands/', data),
  updateBrand: (brandId: number, data: BrandUpdate) =>
    apiClient.put<BrandResponse>(`/brands/${brandId}`, data),
  deleteBrand: (brandId: number) =>
    apiClient.delete<Record<string, string>>(`/brands/${brandId}`),
  getPartsByBrand: (
    brandId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<GlobalPartRead[]>(`/brands/${brandId}/global-parts`, {
      params,
    }),
  getBrandPartsCount: (brandId: number) =>
    apiClient.get<{ parts_count: number }>(`/brands/${brandId}/parts-count`),
  countBrands: () => apiClient.get<{ count: number }>('/brands/count'),
};

// Retailers API (part stores/sites)
export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};

// Unified Votes API
export const votesApi = {
  voteOnEntity: (
    entityType: 'car' | 'build_list' | 'global_part',
    entityId: number,
    data: VoteCreate
  ) => apiClient.post<VoteRead>(`/votes/${entityType}/${entityId}`, data),
  removeVote: (
    entityType: 'car' | 'build_list' | 'global_part',
    entityId: number
  ) =>
    apiClient.delete<Record<string, string>>(
      `/votes/${entityType}/${entityId}`
    ),
  getVoteSummary: (
    entityType: 'car' | 'build_list' | 'global_part',
    entityId: number
  ) => apiClient.get<VoteSummary>(`/votes/${entityType}/${entityId}/summary`),
  getFlaggedEntities: (
    entityType: 'car' | 'build_list' | 'global_part',
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
    entityType: 'build_list' | 'global_part',
    entityId: number,
    data: ReportCreate
  ) => apiClient.post<ReportRead>(`/reports/${entityType}/${entityId}`, data),
  getReports: (params?: {
    entity_type?: 'build_list' | 'global_part';
    status?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<ReportRead[]>('/reports/admin/list', {
      params,
    }),
  getReportsWithDetails: (params?: {
    entity_type?: 'build_list' | 'global_part';
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
  getReport: (reportId: number) =>
    apiClient.get<ReportWithDetails>(`/reports/${reportId}`),
  updateReport: (reportId: number, data: ReportUpdate) =>
    apiClient.put<ReportRead>(`/reports/${reportId}`, data),
  deleteReport: (reportId: number) =>
    apiClient.delete<Record<string, string>>(`/reports/${reportId}`),
  countReports: () => apiClient.get<{ count: number }>('/reports/count'),
};

// Legacy APIs for backward compatibility (will be removed in future versions)
export const globalPartVotesApi = {
  voteOnGlobalPart: (
    partId: number,
    data: { vote_type: 'upvote' | 'downvote' }
  ) =>
    votesApi.voteOnEntity('global_part', partId, {
      vote_type: data.vote_type,
      entity_type: 'global_part',
      entity_id: partId,
    }),
  removeVote: (partId: number) => votesApi.removeVote('global_part', partId),
  getVoteSummary: (partId: number) =>
    votesApi.getVoteSummary('global_part', partId),
  getFlaggedParts: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('global_part', params?.limit),
};

export const buildListVotesApi = {
  voteOnBuildList: (
    buildListId: number,
    data: { vote_type: 'upvote' | 'downvote' }
  ) =>
    votesApi.voteOnEntity('build_list', buildListId, {
      vote_type: data.vote_type,
      entity_type: 'build_list',
      entity_id: buildListId,
    }),
  removeVote: (buildListId: number) =>
    votesApi.removeVote('build_list', buildListId),
  getVoteSummary: (buildListId: number) =>
    votesApi.getVoteSummary('build_list', buildListId),
  getFlaggedBuildLists: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('build_list', params?.limit),
};

export const globalPartReportsApi = {
  reportGlobalPart: (
    partId: number,
    data: { reason: string; description?: string | null }
  ) =>
    reportsApi.reportEntity('global_part', partId, {
      reason: data.reason as
        | 'inappropriate_content'
        | 'spam'
        | 'inaccurate'
        | 'duplicate'
        | 'other',
      description: data.description ?? null,
    }),
  getReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    reportsApi.getReports({ ...params, entity_type: 'global_part' }),
  getReport: (reportId: number) => reportsApi.getReport(reportId),
  updateReport: (
    reportId: number,
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
  createGlobalPartAndAddToBuildList: (
    buildListId: number,
    globalPartData: GlobalPartCreate,
    buildListPartData: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartReadWithGlobalPart>(
      `/build-list-parts/${buildListId}/create-and-add-part`,
      {
        name: globalPartData.name,
        description: globalPartData.description,
        image_url: globalPartData.image_url,
        category_id: globalPartData.category_id,
        car_ids: globalPartData.car_ids ?? undefined,
        is_universal: globalPartData.is_universal ?? false,
        brand_id: globalPartData.brand_id,
        part_number: globalPartData.part_number,
        specifications: globalPartData.specifications,
        retailer_id: globalPartData.retailer_id,
        price_cents: globalPartData.price_cents,
        product_url: globalPartData.product_url,
        quantity: buildListPartData.quantity ?? 1,
        notes: buildListPartData.notes,
        build_list_phase_id: buildListPartData.build_list_phase_id ?? undefined,
      }
    ),
  // Add an existing global part to a build list as a build list part
  addGlobalPartToBuildList: (
    buildListId: number,
    globalPartId: number,
    data: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartRead>(
      `/build-list-parts/${buildListId}/global-parts/${globalPartId}`,
      {
        ...data,
        build_list_phase_id: data.build_list_phase_id ?? undefined,
      }
    ),
  // Update a build list part (notes, etc.) by build list and global part IDs
  updateBuildListPart: (
    buildListId: number,
    globalPartId: number,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListId}/global-parts/${globalPartId}`,
      data
    ),
  // Update a build list part by its own ID
  updateBuildListPartById: (
    buildListPartId: number,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListPartId}`,
      data
    ),
  // Remove a build list part from a build list (doesn't delete the global part)
  removeBuildListPart: (buildListId: number, globalPartId: number) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/${buildListId}/global-parts/${globalPartId}`
    ),
  // Delete a build list part by its own ID
  deleteBuildListPartById: (buildListPartId: number) =>
    apiClient.delete<BuildListPartRead>(`/build-list-parts/${buildListPartId}`),
  // Get all build list parts in a build list (basic info)
  getBuildListPartsBasic: (buildListId: number) =>
    apiClient.get<BuildListPartRead[]>(`/build-list-parts/${buildListId}`),
  // Get all build list parts in a build list (with global part details)
  getBuildListParts: (buildListId: number) =>
    apiClient.get<BuildListPartReadWithGlobalPart[]>(
      `/build-list-parts/${buildListId}/global-parts`
    ),
  // Count build lists containing a specific global part
  countBuildListsContainingGlobalPart: (globalPartId: number) =>
    apiClient.get<{ count: number }>(
      `/build-list-parts/global-parts/${globalPartId}/build-lists/count`
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
};

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
  global_parts: SearchCategoryResults<GlobalPartRead>;
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
    entityId?: number
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
    buildListId: number,
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
  createBuildLogPost: (buildListId: number, data: BuildLogPostCreate) =>
    apiClient.post<BuildLogPostRead>(
      `/build-logs/build-list/${buildListId}/posts`,
      data
    ),
  updateBuildLogPost: (postId: number, data: BuildLogPostUpdate) =>
    apiClient.put<BuildLogPostRead>(`/build-logs/posts/${postId}`, data),
  deleteBuildLogPost: (postId: number) =>
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
  getBugReport: (bugReportId: number) =>
    apiClient.get<BugReportWithDetails>(`/bug-reports/${bugReportId}`),
  updateBugReport: (bugReportId: number, data: BugReportUpdate) =>
    apiClient.put<BugReportRead>(`/bug-reports/${bugReportId}`, data),
  deleteBugReport: (bugReportId: number) =>
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
  id: number;
  job_type: 'crawler_run' | 'archive_rescrape';
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  triggered_by: 'manual' | 'scheduled';
  params: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  created_by_user_id: number | null;
}

export interface BackgroundJobList {
  items: BackgroundJob[];
  total: number;
  limit: number;
  offset: number;
}

/** Response when starting a crawler job (returns immediately; job runs in background). */
export interface CrawlerRunResponse {
  status: 'started';
  job_id: number;
  adapters: string[];
  triggered_by: 'manual' | 'scheduled';
  message: string;
}

export interface CrawlerServiceAccount {
  id: number;
  username: string;
  email: string;
  is_service_account: true;
  created_at: string;
}

export interface CrawlerRunRequest {
  adapters: string[];
  crawler_user_id?: number;
  crawler_default_category_id: number;
  limits?: Record<string, number>;
  global_limit?: number | null;
  parallel?: boolean;
  /** Seconds between requests per crawler (0.5–60). Default 5 for polite/heavy runs. */
  delay_sec?: number | null;
  crawl_html_save_dir?: string | null;
}

/** Admin: re-parse every archived crawled page (full ingest + inference + price history when price is present). */
export interface RescrapeArchivesRequest {
  crawler_user_id?: number;
  default_category_id: number;
}

export interface RescrapeArchivesQueuedResponse {
  status: string;
  job_id: number;
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
  global_part_cars: number;
  votes_by_entity_type: Record<string, number>;
  reports_by_entity_type: Record<string, number>;
  /** True when CRAWL_BUCKET is set and the S3 client initialized (scraped HTML may live here). */
  crawl_bucket_configured: boolean;
  crawl_bucket_total: number;
  crawl_bucket_by_prefix: Record<string, number>;
  /** Total data stored in the crawl bucket in GB (sum of all object sizes). */
  crawl_bucket_size_gb?: number;
  /** Present when listing the crawl bucket failed after configuration. */
  crawl_bucket_error?: string;
}

export interface CrawlerCronStatus {
  enabled: boolean;
  schedule_expression: string;
  preset: 'monthly' | 'weekly' | 'daily' | 'custom';
  presets: Record<string, string>;
  schedule_name: string;
  group_name: string;
}

export interface CrawlerCronUpdate {
  enabled?: boolean;
  schedule_expression?: string;
  preset?: 'monthly' | 'weekly' | 'daily';
}

export const adminApi = {
  runMigrations: () => apiClient.post<MigrationResult>('/admin/migrations/run'),
  getCurrentRevision: () =>
    apiClient.get<CurrentRevisionResult>('/admin/migrations/current'),
  initCarGenerations: () =>
    apiClient.post<InitDataResult>('/admin/init/car-generations'),
  initPartCategories: () =>
    apiClient.post<InitDataResult>('/admin/init/part-categories'),

  // Crawlers
  getCrawlers: () => apiClient.get<{ adapters: string[] }>('/admin/crawlers'),
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

  /** Delete all global parts (admin only). Cascades to listings, votes, reports, build list parts. */
  deleteAllGlobalParts: () =>
    apiClient.post<{ deleted_count: number }>('/admin/global-parts/delete-all'),

  /** Delete all cars / car generations (admin only). Also deletes car models and makes for a clean init. */
  deleteAllCars: () =>
    apiClient.post<{
      deleted_count: number;
      deleted_car_models_count: number;
      deleted_makes_count: number;
    }>('/admin/cars/delete-all'),

  /** Delete all part brands (admin only). Nullifies brand on parts first, then deletes all brands. */
  deleteAllBrands: () =>
    apiClient.post<{ deleted_count: number }>('/admin/brands/delete-all'),

  /** Supplemental table counts and polymorphic vote/report breakdown (admin only). */
  getTableCounts: () =>
    apiClient.get<AdminTableCountsResponse>('/admin/stats/table-counts'),

  // Background jobs
  listJobs: (params?: {
    status?: string;
    job_type?: string;
    limit?: number;
    offset?: number;
  }) => apiClient.get<BackgroundJobList>('/admin/jobs', { params }),
  getJob: (jobId: number) =>
    apiClient.get<BackgroundJob>(`/admin/jobs/${jobId}`),
  cancelJob: (jobId: number) =>
    apiClient.post<BackgroundJob>(`/admin/jobs/${jobId}/cancel`),

  // Cron schedule management
  getCrawlerCron: () => apiClient.get<CrawlerCronStatus>('/admin/cron/crawler'),
  updateCrawlerCron: (body: CrawlerCronUpdate) =>
    apiClient.patch<CrawlerCronStatus>('/admin/cron/crawler', body),
};

export default apiClient;
