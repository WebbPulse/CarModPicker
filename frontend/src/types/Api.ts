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
  totp_enabled: boolean;
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
  current_password?: string | null;
  otp?: string | null; // Required if 2FA is enabled and changing password
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
  generation_name: string;
  start_year: number;
  end_year: number;
  description?: string | null;
  image_url?: string | null;
}

export interface CarRead {
  id: number;
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year: number;
  description?: string | null;
  image_url?: string | null;
}

export interface CarUpdate {
  make?: string | null;
  model?: string | null;
  generation_name?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
  image_url?: string | null;
}

// Car Generation interfaces
export interface CarGenerationCreate {
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year: number;
  description?: string | null;
}

export interface CarGenerationRead {
  id: number;
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year: number;
  description?: string | null;
}

export interface CarGenerationUpdate {
  make?: string | null;
  model?: string | null;
  generation_name?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
}

export interface BuildListCreate {
  name: string;
  description?: string | null;
  car_id: number; // Required - build lists must be associated with a car
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

export interface BuildListReadWithVotes extends BuildListRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface BuildListUpdate {
  name?: string | null;
  description?: string | null;
  car_id?: number | null;
  image_url?: string | null;
}

// Build Log interfaces
export interface BuildLogPostCreate {
  content: string;
}

export interface BuildLogPostUpdate {
  content?: string | null;
}

export interface BuildLogPostRead {
  id: number;
  build_log_id: number;
  user_id: number;
  content: string;
  created_at: string;
  updated_at: string;
  author_username?: string | null;
  author_image_url?: string | null;
}

export interface BuildLogRead {
  id: number;
  build_list_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
}

export interface BuildLogReadPaginated {
  id: number;
  build_list_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
  pagination: PaginationInfo;
}

// Updated Part interfaces to match new backend schema
export interface GlobalPartCreate {
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  image_urls?: string[] | null;
  product_url?: string | null;
  category_id: number;
  car_id?: number | null; // Optional car association
  brand_id: number; // Required brand association
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

export interface GlobalPartRead {
  id: number;
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  image_urls?: string[] | null;
  category_id: number;
  user_id: number;
  car_id?: number | null; // Optional car association
  brand_id?: number | null; // Optional brand association
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

/** Retailer (store) where parts are sold */
export interface RetailerRead {
  id: number;
  name: string;
  domain?: string | null;
  base_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Part listing at a retailer with current price */
export interface PartListingReadWithRetailer {
  id: number;
  global_part_id: number;
  retailer_id: number;
  product_url?: string | null;
  last_known_price_cents?: number | null;
  last_price_updated_at?: string | null;
  created_at: string;
  updated_at: string;
  retailer: RetailerRead;
}

/** Price history entry with retailer info */
export interface PartPriceHistoryReadWithRetailer {
  id: number;
  part_listing_id: number;
  price_cents: number;
  observed_at: string;
  retailer_id: number;
  retailer_name: string;
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
  image_urls?: string[] | null;
  category_id?: number | null;
  car_id?: number | null; // Optional car association
  brand_id: number; // Required brand association
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

// Brand interfaces
export interface BrandResponse {
  id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BrandCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface BrandUpdate {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
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

// Bug Report interfaces
export interface BugReportCreate {
  title: string;
  description: string;
  steps_to_reproduce?: string | null;
  expected_behavior?: string | null;
  actual_behavior?: string | null;
  browser_info?: string | null;
  device_info?: string | null;
  screenshot_url?: string | null;
}

export interface BugReportRead {
  id: number;
  user_id?: number | null;
  title: string;
  description: string;
  steps_to_reproduce?: string | null;
  expected_behavior?: string | null;
  actual_behavior?: string | null;
  browser_info?: string | null;
  device_info?: string | null;
  screenshot_url?: string | null;
  status: 'pending' | 'in_progress' | 'resolved' | 'dismissed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  admin_notes?: string | null;
  assigned_to?: number | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BugReportWithDetails extends BugReportRead {
  reporter_username?: string | null;
  assignee_username?: string | null;
}

export interface BugReportUpdate {
  status?: 'pending' | 'in_progress' | 'resolved' | 'dismissed' | null;
  priority?: 'low' | 'medium' | 'high' | 'critical' | null;
  admin_notes?: string | null;
  assigned_to?: number | null;
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
  purchased: boolean;
  added_at: string;
}

export interface BuildListPartReadWithGlobalPart extends BuildListPartRead {
  global_part: GlobalPartRead;
}

export interface BuildListPartUpdate {
  quantity?: number | null;
  notes?: string | null;
  purchased?: boolean | null;
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

// 2FA types
export interface TOTPSetupResponse {
  secret: string;
  qr_code_data: string;
  manual_entry_key: string;
}

export interface TOTPVerifyRequest {
  otp: string;
}

export interface TOTPVerifyResponse {
  success: boolean;
  message: string;
}

export interface TOTPLoginRequest {
  username: string;
  password: string;
  otp: string;
}

export interface TOTPDisableRequest {
  password: string;
  otp: string;
}

export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  user?: UserRead;
  requires_2fa?: boolean;
  message?: string;
}
