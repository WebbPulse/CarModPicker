export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface UserRead {
  id: number;
  username: string;
  email: string;
  disabled: boolean;
  email_verified: boolean;
  image_url?: string | null;
  is_superuser: boolean;
  is_admin: boolean;
  subscription_tier: string;
  subscription_status: string;
  subscription_expires_at?: string | null;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
}

export interface UserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_url?: string | null;
  current_password: string;
}

export interface AdminUserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_url?: string | null;
  is_superuser?: boolean | null;
  is_admin?: boolean | null;
  email_verified?: boolean | null;
  subscription_tier?: string | null;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
}

export interface CarCreate {
  make: string;
  model: string;
  year: number;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
}

export interface CarRead {
  id: number;
  make: string;
  model: string;
  year: number;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
  user_id: number;
}

export interface CarUpdate {
  make?: string | null;
  model?: string | null;
  year?: number | null;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
}

export interface BuildListCreate {
  name: string;
  description?: string | null;
  car_id?: number | null;
  image_url?: string | null;
}

export interface BuildListRead {
  id: number;
  name: string;
  description?: string | null;
  car_id?: number | null;
  user_id: number;
  image_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuildListUpdate {
  name?: string | null;
  description?: string | null;
  car_id?: number | null;
  image_url?: string | null;
}

// Updated Part interfaces to match new backend schema
export interface GlobalPartCreate {
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id: number;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

export interface GlobalPartRead {
  id: number;
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id: number;
  user_id: number;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface GlobalPartReadWithVotes extends GlobalPartRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface PaginationInfo {
  current_page: number;
  total_pages: number;
  total_items: number;
  items_per_page: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationInfo;
}

export interface GlobalPartUpdate {
  name?: string | null;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id?: number | null;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

// New interfaces for categories
export interface CategoryResponse {
  id: number;
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreate {
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

export interface CategoryUpdate {
  name?: string | null;
  display_name?: string | null;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean | null;
  sort_order?: number | null;
}

// Unified voting system interfaces
export interface VoteCreate {
  vote_type: 'upvote' | 'downvote';
  entity_type: 'car' | 'build_list' | 'global_part';
  entity_id: number;
}

export interface VoteRead {
  id: number;
  user_id: number;
  vote_type: string;
  entity_type: string;
  entity_id: number;
  created_at: string;
  updated_at: string;
}

export interface VoteSummary {
  entity_id: number;
  entity_type: string;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  vote_score: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface FlaggedEntitySummary {
  entity_id: number;
  entity_type: string;
  entity_name: string;
  entity_description?: string | null;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  vote_score: number;
  downvote_ratio: number;
  recent_downvotes: number;
  has_reports: boolean;
  created_at: string;
  flagged_at: string;
}

// Unified reporting system interfaces
export interface ReportCreate {
  reason:
    | 'inappropriate_content'
    | 'spam'
    | 'inaccurate'
    | 'duplicate'
    | 'other';
  description?: string | null;
  entity_type: 'car' | 'build_list' | 'global_part';
  entity_id: number;
}

export interface ReportRead {
  id: number;
  user_id: number;
  entity_type: string;
  entity_id: number;
  reason: string;
  description?: string | null;
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportWithDetails extends ReportRead {
  reporter_username: string;
  entity_name: string;
  entity_description?: string | null;
  reviewer_username?: string | null;
}

export interface ReportUpdate {
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
}

// New interfaces for subscription system
export interface SubscriptionStatus {
  tier: 'free' | 'premium';
  status: 'active' | 'cancelled' | 'expired';
  expires_at?: string | null;
  limits: Record<string, number>;
  usage: Record<string, number>;
}

export interface SubscriptionResponse {
  tier: 'free' | 'premium';
  status: 'active' | 'cancelled' | 'expired';
  expires_at?: string | null;
  id: number;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface UpgradeRequest {
  tier: 'premium';
  payment_method?: string | null;
}

// Build list part relationship
export interface BuildListPartCreate {
  global_part_id?: number | null;
  quantity?: number;
  notes?: string | null;
}

export interface BuildListPartRead {
  id: number;
  build_list_id: number;
  global_part_id: number;
  added_by: number;
  quantity: number;
  notes?: string | null;
  added_at: string;
}

export interface BuildListPartReadWithGlobalPart extends BuildListPartRead {
  global_part: GlobalPartRead;
}

export interface BuildListPartUpdate {
  quantity?: number | null;
  notes?: string | null;
}

// Auth interfaces
export interface NewPassword {
  password: string;
}

export interface BodyLoginForAccessToken {
  grant_type?: 'password' | null;
  username: string;
  password: string;
  scope?: string;
  client_id?: string | null;
  client_secret?: string | null;
}

export interface BodyVerifyEmail {
  email: string;
}

export interface BodyResetPassword {
  email: string;
}
