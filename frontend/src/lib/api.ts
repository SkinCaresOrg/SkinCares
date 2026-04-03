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

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

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
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "Request failed";
    try {
      const payload = await res.json();
      detail = payload?.detail || detail;
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

export async function getProducts(params?: {
  category?: Category;
  sort?: SortValue;
  search?: string;
  min_price?: number;
  max_price?: number;
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
