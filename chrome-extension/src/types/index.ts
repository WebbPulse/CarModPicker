/**
 * Type definitions for CarModPicker API
 */

export interface User {
  id: number;
  username: string;
  email: string;
  image_url?: string | null;
  email_verified: boolean;
  disabled: boolean;
  created_at: string;
  updated_at: string;
  is_superuser: boolean;
  is_admin: boolean;
  subscription_tier: string;
  subscription_expires_at?: string | null;
  subscription_status: string;
}

export interface Category {
  id: number;
  name: string;
  display_name?: string | null;
  description?: string | null;
  icon?: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Car {
  id: number;
  make: string;
  model: string;
  generation_name: string;
  start_year: number;
  end_year?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Brand {
  id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Retailer {
  id: number;
  name: string;
  domain?: string | null;
  base_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GlobalPartCreate {
  name: string;
  description?: string | null;
  price?: number | null; // Price in cents (legacy GlobalPart field)
  image_url?: string | null;
  image_urls?: string[] | null;
  product_url?: string | null;
  category_id: number;
  car_ids?: number[] | null;
  is_universal?: boolean;
  brand_id: number; // Required - part manufacturer (e.g. HKS, Borla)
  part_number?: string | null;
  specifications?: Record<string, unknown> | null;
  retailer_id?: number | null; // Optional - store/site where part is sold
  price_cents?: number | null; // Optional - for PartListing/price history when retailer_id set
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
  car_ids: number[];
  is_universal: boolean;
  brand_id?: number | null;
  part_number?: string | null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScrapedProductData {
  name: string | null;
  description: string | null;
  price: number | null; // Price in cents
  image_url: string | null; // Primary image (first in gallery)
  image_urls: string[]; // All product images for gallery
  product_url: string;
  brand: string | null;
  part_number: string | null;
  inferred_category: string | null; // server-inferred category name slug, e.g. "exhaust"
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  requires_2fa?: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  requires2FA?: boolean;
}

export interface ImageUploadResponse {
  file_key: string;
  presigned_url: string;
  message: string;
}

export interface PartListingCreate {
  global_part_id: number;
  retailer_id: number;
  product_url?: string | null;
  price_cents?: number | null;
}

export interface ExtensionMessage {
  action: string;
  username?: string;
  password?: string;
  partData?: GlobalPartCreate;
  imageUrl?: string;
  limit?: number;
  searchTerm?: string;
  brandName?: string;
  productUrl?: string;
  partId?: number;
  domain?: string;
  listingData?: PartListingCreate;
}
