import axios, { type AxiosError, type AxiosResponse } from 'axios';
import type {
  AdminUserUpdate,
  BodyLoginForAccessToken,
  BodyResetPassword,
  BodyVerifyEmail,
  BuildListCreate,
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
  BuildListRead,
  BuildListReadWithVotes,
  BuildListUpdate,
  CarCreate,
  CarGenerationCreate,
  CarGenerationRead,
  CarGenerationUpdate,
  CarRead,
  CarUpdate,
  CategoryCreate,
  CategoryResponse,
  CategoryUpdate,
  FlaggedEntitySummary,
  GlobalPartCreate,
  GlobalPartRead,
  GlobalPartReadWithVotes,
  GlobalPartUpdate,
  NewPassword,
  PaginatedResponse,
  ReportCreate,
  ReportRead,
  ReportUpdate,
  ReportWithDetails,
  SubscriptionResponse,
  SubscriptionStatus,
  UpgradeRequest,
  UserCreate,
  UserRead,
  UserUpdate,
  VoteCreate,
  VoteRead,
  VoteSummary,
} from '../types/Api';

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development, use the proxy
  if (import.meta.env.DEV) {
    return '/api';
  }

  // In production, check for environment variable first
  const apiUrl: string | undefined = import.meta.env['VITE_API_URL'] as
    | string
    | undefined;
  if (apiUrl && typeof apiUrl === 'string') {
    // Ensure the URL has a protocol
    const urlWithProtocol =
      apiUrl.startsWith('http://') || apiUrl.startsWith('https://')
        ? apiUrl
        : `https://${apiUrl}`;
    return `${urlWithProtocol}/api`;
  }

  // Default fallback for production
  return '/api';
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
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
  getUser: (userId: number) => apiClient.get<UserRead>(`/users/${userId}`),
  updateUser: (userId: number, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: number) =>
    apiClient.delete<UserRead>(`/users/${userId}`),

  // List and count endpoints
  listUsers: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<UserRead[]>('/users/', { params }),
  countUsers: () => apiClient.get<{ count: number }>('/users/count'),

  // Admin endpoints
  getAllUsers: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<UserRead[]>('/users/admin/users', { params }),
  adminUpdateUser: (userId: number, data: AdminUserUpdate) =>
    apiClient.put<UserRead>(`/users/admin/users/${userId}`, data),
  adminDeleteUser: (userId: number) =>
    apiClient.delete<UserRead>(`/users/admin/users/${userId}`),
};

// Car API
export const carsApi = {
  // Admin-only create/update/delete
  createCar: (data: CarCreate) =>
    apiClient.post<CarRead>('/cars/admin/cars', data),
  updateCar: (carId: number, data: CarUpdate) =>
    apiClient.put<CarRead>(`/cars/admin/cars/${carId}`, data),
  deleteCar: (carId: number) =>
    apiClient.delete<CarRead>(`/cars/admin/cars/${carId}`),
  deleteAllCars: () =>
    apiClient.delete<{ message: string; deleted_count: number }>(
      '/cars/admin/cars'
    ),

  // Public read endpoints
  getCar: (carId: number) => apiClient.get<CarRead>(`/cars/${carId}`),
  listCars: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<CarRead[]>('/cars/', { params }),
  searchCars: (q: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>('/cars/search', { params: { q, ...params } }),
  getCarsByMake: (make: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>(`/cars/make/${make}`, { params }),
  getCarsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarRead[]>(`/cars/make/${make}/model/${model}`, { params }),
  getCarsByGeneration: (
    generationId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<CarRead[]>(`/cars/generation/${generationId}`, { params }),
  getCarsByYear: (year: number, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>(`/cars/year/${year}`, { params }),
  // Stats and count endpoints
  getCarMakeStats: () =>
    apiClient.get<Record<string, number>>('/cars/stats/makes'),
  countCars: () => apiClient.get<{ count: number }>('/cars/count'),
};

// Car Generation API (Admin only) - now uses /cars endpoints
export const carGenerationsApi = {
  createCarGeneration: (data: CarGenerationCreate) =>
    apiClient.post<CarGenerationRead>('/cars/admin/cars', data),
  getCarGeneration: (generationId: number) =>
    apiClient.get<CarGenerationRead>(`/cars/${generationId}`),
  updateCarGeneration: (generationId: number, data: CarGenerationUpdate) =>
    apiClient.put<CarGenerationRead>(`/cars/admin/cars/${generationId}`, data),
  deleteCarGeneration: (generationId: number) =>
    apiClient.delete<CarGenerationRead>(`/cars/admin/cars/${generationId}`),
  listCarGenerations: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }) => apiClient.get<CarGenerationRead[]>('/cars/', { params }),
  getCarGenerationsByMake: (
    make: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(`/cars/make/${make}`, {
      params,
    }),
  getCarGenerationsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(`/cars/make/${make}/model/${model}`, {
      params,
    }),
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
  }) =>
    apiClient.get<PaginatedResponse<BuildListReadWithVotes>>(
      '/build-lists/with-votes',
      {
        params,
      }
    ),
  getBuildListsByCar: (
    carId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<BuildListRead[]>(`/build-lists/car/${carId}`, { params }),
  getMyBuildLists: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<BuildListRead[]>('/build-lists/user/me', { params }),
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
};

// Global Parts API (Global shared parts in the catalog)
export const globalPartsApi = {
  // Get all global parts with filtering
  getGlobalParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) => apiClient.get<GlobalPartRead[]>('/global-parts/', { params }),

  // Get global parts with vote data
  getGlobalPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) =>
    apiClient.get<PaginatedResponse<GlobalPartReadWithVotes>>(
      '/global-parts/with-votes',
      {
        params,
      }
    ),

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

  // Update global part
  updateGlobalPart: (partId: number, data: GlobalPartUpdate) =>
    apiClient.put<GlobalPartRead>(`/global-parts/${partId}`, data),

  // Delete global part
  deleteGlobalPart: (partId: number) =>
    apiClient.delete<GlobalPartRead>(`/global-parts/${partId}`),

  // Count endpoints
  countGlobalParts: () =>
    apiClient.get<{ count: number }>('/global-parts/count'),
  countGlobalPartsByUser: (userId: number) =>
    apiClient.get<{ count: number }>(`/global-parts/user/${userId}/count`),
};

// Categories API
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories/'),
  getCategory: (categoryId: number) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  createCategory: (data: CategoryCreate) =>
    apiClient.post<CategoryResponse>('/categories/', data),
  updateCategory: (categoryId: number, data: CategoryUpdate) =>
    apiClient.put<CategoryResponse>(`/categories/${categoryId}`, data),
  deleteCategory: (categoryId: number) =>
    apiClient.delete<Record<string, string>>(`/categories/${categoryId}`),
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
    apiClient.get<ReportWithDetails[]>('/reports/admin/list-with-details', {
      params,
    }),
  getMyReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    apiClient.get<ReportRead[]>('/reports/my-reports', { params }),
  getReport: (reportId: number) =>
    apiClient.get<ReportWithDetails>(`/reports/${reportId}`),
  updateReport: (reportId: number, data: ReportUpdate) =>
    apiClient.put<ReportRead>(`/reports/${reportId}`, data),
  deleteReport: (reportId: number) =>
    apiClient.delete<Record<string, string>>(`/reports/${reportId}`),
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
        price: globalPartData.price,
        image_url: globalPartData.image_url,
        category_id: globalPartData.category_id,
        car_id: globalPartData.car_id,
        brand: globalPartData.brand,
        part_number: globalPartData.part_number,
        specifications: globalPartData.specifications,
        notes: buildListPartData.notes,
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
      data
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
};

// Subscriptions API
export const subscriptionsApi = {
  getStatus: () => apiClient.get<SubscriptionStatus>('/subscriptions/status'),
  upgrade: (data: UpgradeRequest) =>
    apiClient.post<SubscriptionResponse>('/subscriptions/upgrade', data),
  cancel: () => apiClient.post<SubscriptionResponse>('/subscriptions/cancel'),
  checkCreationLimits: (resourceType: string) =>
    apiClient.get<Record<string, boolean>>('/subscriptions/limits/check', {
      params: { resource_type: resourceType },
    }),
  checkGlobalPartCreationLimit: () =>
    apiClient.get<Record<string, boolean>>(
      '/subscriptions/limits/check/global-part'
    ),
};

// Auth API
export const authApi = {
  login: async (
    data: BodyLoginForAccessToken
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
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
};

export default apiClient;
