import { Product, ProductDetail, RecommendedProduct, DupeProduct, OnboardingProfile, FeedbackRequest, Category } from "./types";
import { MOCK_PRODUCTS, MOCK_PRODUCT_DETAIL, MOCK_RECOMMENDATIONS, MOCK_DUPES } from "./mockData";

const BASE_URL = "http://localhost:8000/api";

async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function submitOnboarding(profile: OnboardingProfile): Promise<{ user_id: string; profile: OnboardingProfile }> {
  try {
    return await fetchApi("/onboarding", { method: "POST", body: JSON.stringify(profile) });
  } catch {
    return { user_id: `user_${Date.now()}`, profile };
  }
}

export async function getProducts(params?: {
  category?: Category;
  sort?: string;
  search?: string;
  min_price?: number;
  max_price?: number;
}): Promise<{ products: Product[]; total: number }> {
  try {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.sort) query.set("sort", params.sort);
    if (params?.search) query.set("search", params.search);
    if (params?.min_price) query.set("min_price", String(params.min_price));
    if (params?.max_price) query.set("max_price", String(params.max_price));
    const qs = query.toString();
    return await fetchApi(`/products${qs ? `?${qs}` : ""}`);
  } catch {
    let filtered = [...MOCK_PRODUCTS];
    if (params?.category) filtered = filtered.filter((p) => p.category === params.category);
    if (params?.search) {
      const s = params.search.toLowerCase();
      filtered = filtered.filter((p) => p.product_name.toLowerCase().includes(s) || p.brand.toLowerCase().includes(s));
    }
    if (params?.sort === "price_asc") filtered.sort((a, b) => a.price - b.price);
    if (params?.sort === "price_desc") filtered.sort((a, b) => b.price - a.price);
    return { products: filtered, total: filtered.length };
  }
}

export async function getProductDetail(productId: number): Promise<ProductDetail> {
  try {
    return await fetchApi(`/products/${productId}`);
  } catch {
    const base = MOCK_PRODUCTS.find((p) => p.product_id === productId) || MOCK_PRODUCTS[0];
    return { ...MOCK_PRODUCT_DETAIL, ...base, product_id: productId };
  }
}

export async function getRecommendations(userId: string, category?: Category): Promise<{ products: RecommendedProduct[] }> {
  try {
    const qs = category ? `?category=${category}` : "";
    return await fetchApi(`/recommendations/${userId}${qs}`);
  } catch {
    let recs = [...MOCK_RECOMMENDATIONS];
    if (category) recs = recs.filter((r) => r.category === category);
    return { products: recs };
  }
}

export async function getDupes(productId: number): Promise<{ source_product_id: number; dupes: DupeProduct[] }> {
  try {
    return await fetchApi(`/dupes/${productId}`);
  } catch {
    return { source_product_id: productId, dupes: MOCK_DUPES };
  }
}

export async function submitFeedback(feedback: FeedbackRequest): Promise<{ success: boolean; message: string }> {
  try {
    return await fetchApi("/feedback", { method: "POST", body: JSON.stringify(feedback) });
  } catch {
    return { success: true, message: "Feedback recorded" };
  }
}
