import { useEffect, useState, useCallback } from "react";
import { getAuthToken, getAuthUserId, clearAuthSession } from "@/lib/session";
import { fetchApi } from "@/lib/api";
import { OnboardingProfile, Product } from "@/lib/types";

// Namespaced keys
const onboardingKey = (userId: string) => `skincares_onboarding_${userId}`;
const wishlistKey = (userId: string) => `skincares_wishlist_${userId}`;
const GLOBAL_ONBOARDING_KEY = "skincares_user_profile";
const GLOBAL_USER_ID_KEY = "skincares_user_id";
const GLOBAL_WISHLIST_KEY = "skincares_wishlist";

export function useUserState() {
  const [userId, setUserId] = useState<string | null>(getAuthUserId());
  const [onboarding, setOnboarding] = useState<OnboardingProfile | null>(null);
  const [wishlist, setWishlist] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);

  // Clear all user state
  const clearUserState = useCallback(() => {
    if (userId) {
      localStorage.removeItem(onboardingKey(userId));
      localStorage.removeItem(wishlistKey(userId));
    }
    // Also clear global keys for compatibility
    localStorage.removeItem(GLOBAL_ONBOARDING_KEY);
    localStorage.removeItem(GLOBAL_USER_ID_KEY);
    localStorage.removeItem(GLOBAL_WISHLIST_KEY);
    setOnboarding(null);
    setWishlist([]);
    setUserId(null);
    clearAuthSession();
  }, [userId]);

  // Fetch onboarding and wishlist from backend
  const hydrateUserState = useCallback(async () => {
    const token = getAuthToken();
    const uid = getAuthUserId();
    if (!token || !uid) {
      clearUserState();
      return;
    }
    setLoading(true);
    setUserId(uid);
    try {
      // Fetch onboarding
      const onboardingResp = await fetchApi<{ user_id: string; profile: OnboardingProfile }>("/onboarding/profile");
      setOnboarding(onboardingResp.profile);
      localStorage.setItem(onboardingKey(uid), JSON.stringify(onboardingResp.profile));
      // Also update global keys for compatibility
      localStorage.setItem(GLOBAL_ONBOARDING_KEY, JSON.stringify(onboardingResp.profile));
      localStorage.setItem(GLOBAL_USER_ID_KEY, uid);
    } catch {
      setOnboarding(null);
      localStorage.removeItem(onboardingKey(uid));
      localStorage.removeItem(GLOBAL_ONBOARDING_KEY);
      localStorage.removeItem(GLOBAL_USER_ID_KEY);
    }
    try {
      // Fetch wishlist
      const wishlistResp = await fetchApi<{ products: Product[] }>("/wishlist");
      setWishlist(wishlistResp.products);
      localStorage.setItem(wishlistKey(uid), JSON.stringify(wishlistResp.products));
      // Also update global key for compatibility
      localStorage.setItem(GLOBAL_WISHLIST_KEY, JSON.stringify(wishlistResp.products.map(p => p.product_id)));
    } catch {
      setWishlist([]);
      localStorage.removeItem(wishlistKey(uid));
      localStorage.removeItem(GLOBAL_WISHLIST_KEY);
    }
    setLoading(false);
  }, [clearUserState]);

  // On mount or login change, hydrate state
  useEffect(() => {
    hydrateUserState();
    // eslint-disable-next-line
  }, [userId]);

  // Keep local auth state in sync with auth session changes from storage
  useEffect(() => {
    const handleStorage = () => {
      setUserId(getAuthUserId());
    };
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  // On logout, clear state
  const logout = useCallback(() => {
    clearUserState();
  }, [clearUserState]);

  return {
    userId,
    onboarding,
    wishlist,
    loading,
    hydrateUserState,
    logout,
  };
}
