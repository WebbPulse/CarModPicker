import axios, { type AxiosError } from 'axios';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  AdminUserUpdate,
  CarRead,
  CarCreate,
  CarUpdate,
  BuildListRead,
  BuildListCreate,
  BuildListUpdate,
  GlobalPartRead,
  GlobalPartReadWithVotes,
  GlobalPartCreate,
  GlobalPartUpdate,
  CategoryResponse,
  CategoryCreate,
  CategoryUpdate,
  VoteCreate,
  VoteRead,
  VoteSummary,
  FlaggedEntitySummary,
  ReportCreate,
  ReportRead,
  ReportWithDetails,
  ReportUpdate,
  SubscriptionStatus,
  SubscriptionResponse,
  UpgradeRequest,
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
  NewPassword,
  BodyLoginForAccessToken,
  BodyVerifyEmail,
  BodyResetPassword,
} from '../types/Api';

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development, use the proxy
  if (import.meta.env.DEV) {
    return '/api';
  }

  // In production, check for environment variable first
  const apiUrl: string | undefined = import.meta.env.VITE_API_URL as
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
  withCredentials: true,
});

apiClient.interceptors.request.use(
  (config) => {
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
    return response;
  },
  (error: unknown) => {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 401) {
      // Handle unauthorized access, e.g., redirect to login
      console.error('Unauthorized, please login again...');
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
  createCar: (data: CarCreate) => apiClient.post<CarRead>('/cars/', data),
  getCar: (carId: number) => apiClient.get<CarRead>(`/cars/${carId}`),
  updateCar: (carId: number, data: CarUpdate) =>
    apiClient.put<CarRead>(`/cars/${carId}`, data),
  deleteCar: (carId: number) => apiClient.delete<CarRead>(`/cars/${carId}`),
  getCarsByUser: (userId: number, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>(`/cars/user/${userId}`, { params }),
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
  getBuildListsByCar: (
    carId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<BuildListRead[]>(`/build-lists/car/${carId}`, { params }),
  getBuildListsByUser: (
    userId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<BuildListRead[]>(`/build-lists/user/${userId}`, { params }),
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
    apiClient.get<GlobalPartReadWithVotes[]>('/global-parts/with-votes', {
      params,
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

  // Get global parts by user
  getGlobalPartsByUser: (
    userId: number,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<GlobalPartRead[]>(`/global-parts/user/${userId}`, { params }),
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
};

// Unified Votes API
export const votesApi = {
  voteOnEntity: (entityType: 'car' | 'build_list' | 'global_part', entityId: number, data: VoteCreate) =>
    apiClient.post<VoteRead>(
      `/votes/${entityType}/${entityId}`,
      data
    ),
  removeVote: (entityType: 'car' | 'build_list' | 'global_part', entityId: number) =>
    apiClient.delete<Record<string, string>>(
      `/votes/${entityType}/${entityId}`
    ),
  getVoteSummary: (entityType: 'car' | 'build_list' | 'global_part', entityId: number) =>
    apiClient.get<VoteSummary>(
      `/votes/${entityType}/${entityId}/summary`
    ),
  getFlaggedEntities: (entityType: 'car' | 'build_list' | 'global_part', limit?: number) =>
    apiClient.get<FlaggedEntitySummary[]>(
      `/votes/admin/flagged/${entityType}`,
      { params: { limit } }
    ),
};

// Unified Reports API
export const reportsApi = {
  reportEntity: (entityType: 'car' | 'build_list' | 'global_part', entityId: number, data: ReportCreate) =>
    apiClient.post<ReportRead>(
      `/reports/${entityType}/${entityId}`,
      data
    ),
  getReports: (params?: { 
    entity_type?: 'car' | 'build_list' | 'global_part'; 
    status?: string; 
    skip?: number; 
    limit?: number 
  }) =>
    apiClient.get<ReportRead[]>('/reports/admin/list', {
      params,
    }),
  getReportsWithDetails: (params?: { 
    entity_type?: 'car' | 'build_list' | 'global_part'; 
    status?: string; 
    skip?: number; 
    limit?: number 
  }) =>
    apiClient.get<ReportWithDetails[]>('/reports/admin/list-with-details', {
      params,
    }),
  getReport: (reportId: number) =>
    apiClient.get<ReportWithDetails>(
      `/reports/${reportId}`
    ),
  updateReport: (reportId: number, data: ReportUpdate) =>
    apiClient.put<ReportRead>(
      `/reports/${reportId}`,
      data
    ),
};

// Legacy APIs for backward compatibility (will be removed in future versions)
export const globalPartVotesApi = {
  voteOnGlobalPart: (partId: number, data: { vote_type: 'upvote' | 'downvote' }) =>
    votesApi.voteOnEntity('global_part', partId, {
      vote_type: data.vote_type,
      entity_type: 'global_part',
      entity_id: partId,
    }),
  removeVote: (partId: number) =>
    votesApi.removeVote('global_part', partId),
  getVoteSummary: (partId: number) =>
    votesApi.getVoteSummary('global_part', partId),
  getFlaggedParts: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('global_part', params?.limit),
};

export const globalPartReportsApi = {
  reportGlobalPart: (partId: number, data: { reason: string; description?: string }) =>
    reportsApi.reportEntity('global_part', partId, {
      reason: data.reason as 'inappropriate_content' | 'spam' | 'inaccurate' | 'duplicate' | 'other',
      description: data.description,
      entity_type: 'global_part',
      entity_id: partId,
    }),
  getReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    reportsApi.getReports({ ...params, entity_type: 'global_part' }),
  getReport: (reportId: number) =>
    reportsApi.getReport(reportId),
  updateReport: (reportId: number, data: { status: string; admin_notes?: string }) =>
    reportsApi.updateReport(reportId, {
      status: data.status as 'pending' | 'reviewed' | 'resolved' | 'dismissed',
      admin_notes: data.admin_notes,
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
  // Update a build list part (notes, etc.) in a build list
  updateBuildListPart: (
    buildListId: number,
    globalPartId: number,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListId}/global-parts/${globalPartId}`,
      data
    ),
  // Remove a build list part from a build list (doesn't delete the global part)
  removeBuildListPart: (buildListId: number, globalPartId: number) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/${buildListId}/global-parts/${globalPartId}`
    ),
  // Get all build list parts in a build list (with global part details)
  getBuildListParts: (buildListId: number) =>
    apiClient.get<BuildListPartReadWithGlobalPart[]>(
      `/build-list-parts/${buildListId}/global-parts`
    ),
};

// Subscriptions API
export const subscriptionsApi = {
  getStatus: () =>
    apiClient.get<SubscriptionStatus>('/subscriptions/subscriptions/status'),
  upgrade: (data: UpgradeRequest) =>
    apiClient.post<SubscriptionResponse>(
      '/subscriptions/subscriptions/upgrade',
      data
    ),
  cancel: () =>
    apiClient.post<SubscriptionResponse>('/subscriptions/subscriptions/cancel'),
  checkCreationLimits: (resourceType: string) =>
    apiClient.get<Record<string, number>>(
      '/subscriptions/subscriptions/limits/check',
      {
        params: { resource_type: resourceType },
      }
    ),
};

// Auth API
export const authApi = {
  login: (data: BodyLoginForAccessToken) =>
    apiClient.post<UserRead>('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  verifyEmail: (data: BodyVerifyEmail) =>
    apiClient.post<Record<string, string>>('/auth/verify-email', data),
  verifyEmailConfirm: (token: string) =>
    apiClient.get<Record<string, string>>('/auth/verify-email/confirm', {
      params: { token },
    }),
  forgotPassword: (data: BodyResetPassword) =>
    apiClient.post<Record<string, string>>('/auth/forgot-password', data),
  resetPasswordConfirm: (token: string, data: NewPassword) =>
    apiClient.post<Record<string, string>>(
      '/auth/forgot-password/confirm',
      data,
      {
        params: { token },
      }
    ),
  logout: () => apiClient.post<Record<string, string>>('/auth/logout'),
};

export default apiClient;
