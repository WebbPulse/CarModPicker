export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface UserRead {
  id: string;
  username: string;
  email: string;
  disabled: boolean;
  email_verified: boolean;
  image_urls?: string[] | null;
  is_superuser: boolean;
  is_admin: boolean;
  is_service_account: boolean;
  subscription_tier: string;
  subscription_status: string;
  subscription_expires_at?: string | null;
  totp_enabled: boolean;
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
  session_expire_minutes?: number | null;
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
  image_urls?: string[] | null;
  current_password?: string | null;
  otp?: string | null; // Required if 2FA is enabled and changing password
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
  session_expire_minutes?: number | null;
}

export interface AdminUserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_urls?: string[] | null;
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
  image_urls?: string[] | null;
}

export interface CarRead {
  id: string;
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year?: number | null; // null for current/ongoing generations
  description?: string | null;
  image_urls?: string[] | null;
}

export interface CarUpdate {
  make?: string | null;
  model?: string | null;
  generation_name?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
  image_urls?: string[] | null;
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
  id: string;
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year?: number | null; // null for current/ongoing generations
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
  car_id: string; // Required - build lists must be associated with a car
  image_urls?: string[] | null;
}

export interface BuildListRead {
  id: string;
  name: string;
  description?: string | null;
  car_id?: string | null;
  user_id: string;
  image_urls?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface BuildListReadWithVotes extends BuildListRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
  /** Sum of (part quantity * best price) for all parts in the build list (cents). */
  total_cost_cents?: number | null;
}

export interface BuildListUpdate {
  name?: string | null;
  description?: string | null;
  car_id?: string | null;
  image_urls?: string[] | null;
}

// Build Log interfaces
export interface BuildLogPostCreate {
  content: string;
}

export interface BuildLogPostUpdate {
  content?: string | null;
}

export interface BuildLogPostRead {
  id: string;
  build_log_id: string;
  user_id: string;
  content: string;
  created_at: string;
  updated_at: string;
  author_username?: string | null;
  author_image_url?: string | null;
}

export interface BuildLogRead {
  id: string;
  build_list_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
}

export interface BuildLogReadPaginated {
  id: string;
  build_list_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
  pagination: PaginationInfo;
}

// Updated Part interfaces to match new backend schema
export interface PartCreate {
  name: string;
  description?: string | null;
  image_urls?: string[] | null;
  product_url?: string | null;
  category_id: string;
  car_ids?: string[] | null; // Car IDs this part fits; ignored when is_universal
  is_universal?: boolean; // When true, part fits all cars
  part_manufacturer_id: string; // Required part_manufacturer association
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
  retailer_id?: string | null;
  price_cents?: number | null; // Price for this retailer (creates/updates listing)
}

export interface PartRead {
  id: string;
  name: string;
  description?: string | null;
  best_price_cents?: number | null; // Lowest current price from any retailer listing
  image_urls?: string[] | null;
  category_id: string;
  user_id: string;
  car_ids: string[]; // Car IDs this part is associated with
  is_universal: boolean; // When true, part fits all cars
  part_manufacturer_id?: string | null; // Optional part_manufacturer association
  part_manufacturer?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface PartReadWithVotes extends PartRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

/** Retailer (store) where parts are sold */
export interface RetailerRead {
  id: string;
  name: string;
  domain?: string | null;
  base_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Part listing at a retailer with current price */
export interface PartListingReadWithRetailer {
  id: string;
  part_id: string;
  retailer_id: string;
  product_url?: string | null;
  last_known_price_cents?: number | null;
  last_price_updated_at?: string | null;
  created_at: string;
  updated_at: string;
  retailer: RetailerRead;
}

/** Price history entry with retailer info */
export interface PartPriceHistoryReadWithRetailer {
  id: string;
  part_listing_id: string;
  price_cents: number;
  observed_at: string;
  retailer_id: string;
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

export interface PartUpdate {
  name?: string | null;
  description?: string | null;
  image_urls?: string[] | null;
  category_id?: string | null;
  car_ids?: string[] | null; // Car IDs this part fits; ignored when is_universal
  is_universal?: boolean | null;
  part_manufacturer_id: string; // Required part_manufacturer association
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

// New interfaces for categories
export interface CategoryResponse {
  id: string;
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

// PartManufacturer interfaces
export interface PartManufacturerResponse {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PartManufacturerCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface PartManufacturerUpdate {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
}

// Unified voting system interfaces
export interface VoteCreate {
  vote_type: 'upvote' | 'downvote';
  entity_type: 'car' | 'build_list' | 'part';
  entity_id: string;
}

export interface VoteRead {
  id: string;
  user_id: string;
  vote_type: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  updated_at: string;
}

export interface VoteSummary {
  entity_id: string;
  entity_type: string;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  vote_score: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface FlaggedEntitySummary {
  entity_id: string;
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
  id: string;
  user_id: string;
  entity_type: string;
  entity_id: string;
  reason: string;
  description?: string | null;
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
  reviewed_by?: string | null;
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
  id: string;
  user_id?: string | null;
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
  assigned_to?: string | null;
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
  assigned_to?: string | null;
}

// Build list phase (priority group) per build list
export interface BuildListPhaseRead {
  id: string;
  build_list_id: string;
  name: string;
  sort_order: number;
}

export interface BuildListPhaseCreate {
  name: string;
  sort_order?: number;
}

export interface BuildListPhaseUpdate {
  name?: string | null;
  sort_order?: number | null;
}

// Build list part relationship
export interface BuildListPartCreate {
  part_id?: string | null;
  quantity?: number;
  notes?: string | null;
  build_list_phase_id?: string | null;
}

export interface BuildListPartRead {
  id: string;
  build_list_id: string;
  part_id: string;
  added_by: string;
  quantity: number;
  notes?: string | null;
  purchased: boolean;
  added_at: string;
  build_list_phase_id?: string | null;
}

export interface BuildListPartReadWithPart extends BuildListPartRead {
  phase_name?: string | null;
  part: PartRead;
}

export interface BuildListPartUpdate {
  quantity?: number | null;
  notes?: string | null;
  purchased?: boolean | null;
  build_list_phase_id?: string | null;
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
