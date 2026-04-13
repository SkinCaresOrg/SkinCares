import {
  Product,
  ProductDetail,
  RecommendedProduct,
  DupeProduct,
  OnboardingProfile,
  FeedbackRequest,
  Category,
  SortValue,
} from "./types";
import { getUserProfile } from "./wishlist";
import { getAuthToken } from "./session";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const RETRYABLE_STATUS = new Set([502, 503, 504]);

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  let res: Response | null = null;
  let fetchError: unknown;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const token = getAuthToken();
      const defaultHeaders: HeadersInit = {
        "Content-Type": "application/json",
      };

      if (token) {
        defaultHeaders.Authorization = `Bearer ${token}`;
      }

      res = await fetch(`${BASE_URL}${url}`, {
        headers: {
          ...defaultHeaders,
          ...(options?.headers || {}),
        },
        ...options,
      });

      if (res.ok || !RETRYABLE_STATUS.has(res.status) || attempt === 2) {
        break;
      }
    } catch (error) {
      fetchError = error;
      if (attempt === 2) {
        throw error;
      }
    }

    await sleep(250 * (attempt + 1));
  }

  if (!res) {
    throw fetchError instanceof Error ? fetchError : new Error("Network request failed");
  }

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const payload = await res.json();
      if (Array.isArray(payload?.detail)) {
        detail = payload.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
      } else {
        detail = payload?.detail || detail;
      }
    } catch {
      detail = res.statusText || detail;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function submitOnboarding(profile: OnboardingProfile): Promise<{ user_id: string; profile: OnboardingProfile }> {
  return fetchApi("/onboarding", { method: "POST", body: JSON.stringify(profile) });
}

export async function getUserDebugState(userId: string): Promise<any> {
  return fetchApi(`/debug/user-state/${userId}`);
}

export async function getProducts(params?: {
  category?: Category;
  sort?: SortValue;
  search?: string;
  min_price?: number;
  max_price?: number;
  offset?: number;
}): Promise<{ products: Product[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.search) query.set("search", params.search);
  if (params?.min_price !== undefined) {
    query.set("min_price", String(params.min_price));
  }
  if (params?.max_price !== undefined) {
    query.set("max_price", String(params.max_price));
  }
  if (params?.offset !== undefined) {
  query.set("offset", String(params.offset));
}
  const qs = query.toString();
  return fetchApi(`/products${qs ? `?${qs}` : ""}`);
}

export async function getProductDetail(productId: number): Promise<ProductDetail> {
  return fetchApi(`/products/${productId}`);
}

export async function getRecommendations(userId: string, category?: Category): Promise<{ products: RecommendedProduct[] }> {
  const qs = category ? `?category=${category}` : "";
  return fetchApi(`/recommendations/${userId}${qs}`);
}

export async function getDupes(productId: number): Promise<{ source_product_id: number; dupes: DupeProduct[] }> {
  return fetchApi(`/dupes/${productId}`);
}

export async function submitFeedback(feedback: FeedbackRequest): Promise<{ success: boolean; message: string }> {
  return fetchApi("/feedback", { method: "POST", body: JSON.stringify(feedback) });
}

export async function sendChatMessage(message: string): Promise<{ response: string }> {
  const profile = getUserProfile();
  return fetchApi("/chat", { method: "POST", body: JSON.stringify({ message, profile }) });
}
