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

export interface GlobalPartCreate {
  name: string;
  description?: string | null;
  price?: number | null; // Price in cents
  image_url?: string | null;
  product_url?: string | null;
  category_id: number;
  car_id?: number | null;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, unknown> | null;
}

export interface ScrapedProductData {
  name: string | null;
  description: string | null;
  price: number | null; // Price in cents
  image_url: string | null;
  product_url: string;
  brand: string | null;
  part_number: string | null;
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

export interface ExtensionMessage {
  action: string;
  username?: string;
  password?: string;
  partData?: GlobalPartCreate;
  imageUrl?: string;
}
