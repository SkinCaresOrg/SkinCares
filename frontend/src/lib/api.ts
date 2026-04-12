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

export async function getUserDebugState(userId: string): Promise<Record<string, unknown>> {
  return fetchApi(`/debug/user-state/${userId}`);
}

export async function getProducts(params?: {
  category?: Category;
  sort?: SortValue;
  search?: string;
  skin_type?: string;
  concern?: string;
  brand?: string;
  ingredient?: string;
  min_price?: number;
  max_price?: number;
  page?: number;
  limit?: number;
  offset?: number;
}): Promise<{ items: Product[]; products: Product[]; total: number; hasMore: boolean; page: number }> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.search) query.set("search", params.search);
  if (params?.skin_type) query.set("skin_type", params.skin_type);
  if (params?.concern) query.set("concern", params.concern);
  if (params?.brand) query.set("brand", params.brand);
  if (params?.ingredient) query.set("ingredient", params.ingredient);
  if (params?.min_price !== undefined) {
    query.set("min_price", String(params.min_price));
  }
  if (params?.max_price !== undefined) {
    query.set("max_price", String(params.max_price));
  }
  if (params?.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  if (params?.page !== undefined) {
    query.set("page", String(params.page));
  } else if (params?.offset !== undefined) {
    const fallbackLimit = params?.limit ?? 20;
    query.set("page", String(Math.floor(params.offset / fallbackLimit) + 1));
    query.set("limit", String(fallbackLimit));
  }
  const qs = query.toString();
  return fetchApi<{ items?: Product[]; products?: Product[]; total: number; hasMore?: boolean; page?: number }>(
    `/products${qs ? `?${qs}` : ""}`
  ).then((payload) => {
    const items = payload.items ?? payload.products ?? [];
    const resolvedLimit = params?.limit ?? 20;
    const resolvedPage = payload.page ?? params?.page ?? 1;
    const hasMore = payload.hasMore ?? resolvedPage * resolvedLimit < payload.total;

    return {
      items,
      products: items,
      total: payload.total,
      hasMore,
      page: resolvedPage,
    };
  });
}

export async function getSwipeQueue(limit = 6): Promise<{ products: RecommendedProduct[]; hasMore: boolean; remaining: number }> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  return fetchApi(`/swipe/queue?${query.toString()}`);
}

export async function createSwipe(productId: number, direction: "like" | "dislike" | "irritation" | "skip"): Promise<{ swipe_event_id: number; success: boolean }> {
  return fetchApi("/swipe", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, direction }),
  });
}

export async function submitSwipeQuestionnaire(
  swipeEventId: number,
  payload: { reason_tags?: string[]; free_text?: string; skipped?: boolean }
): Promise<{ success: boolean; message: string }> {
  return fetchApi(`/swipe/${swipeEventId}/questionnaire`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getWishlistItems(): Promise<{ items: Product[] }> {
  return fetchApi("/wishlist");
}

export async function addToWishlist(productId: number): Promise<{ success: boolean; product_id: number }> {
  return fetchApi(`/wishlist/${productId}`, { method: "POST" });
}

export async function removeFromWishlist(productId: number): Promise<{ success: boolean; product_id: number }> {
  return fetchApi(`/wishlist/${productId}`, { method: "DELETE" });
}

export async function getProductDetail(productId: number): Promise<ProductDetail> {
  return fetchApi(`/products/${productId}`);
}

export async function getRecommendations(
  userId: string,
  category?: Category,
  limit?: number
): Promise<{ products: RecommendedProduct[] }> {
  const query = new URLSearchParams();
  if (category) query.set("category", category);
  if (limit !== undefined) query.set("limit", String(limit));
  const qs = query.toString();
  return fetchApi(`/recommendations/${userId}${qs ? `?${qs}` : ""}`);
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

// ML Model Metrics endpoints
export interface ModelMetric {
  accuracy: number;
  total_predictions: number;
  correct: number;
}

export interface MLMetrics {
  [modelName: string]: ModelMetric;
  available_models?: {
    [modelName: string]: boolean;
  };
}

export interface RankedModel {
  rank: number;
  name: string;
  accuracy: number;
  total_predictions: number;
  correct: number;
  model_info?: {
    threshold_interactions?: number;
    description?: string;
  };
}

export interface ModelComparison {
  all_metrics: MLMetrics;
  ranked_models: RankedModel[];
  best_model: string;
}

export async function getMLModelMetrics(): Promise<MLMetrics> {
  try {
    return fetchApi("/ml/model-metrics");
  } catch (error) {
    console.warn("Failed to fetch ML metrics:", error);
    return {};
  }
}

export async function compareMLModels(): Promise<ModelComparison> {
  try {
    return fetchApi("/ml/compare-models");
  } catch (error) {
    console.warn("Failed to compare ML models:", error);
    return { all_metrics: {}, ranked_models: [], best_model: "" };
  }
}
