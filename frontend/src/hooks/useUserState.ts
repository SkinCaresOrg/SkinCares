import { useEffect, useState, useCallback } from "react";
import { getAuthToken, getAuthUserId, clearAuthSession } from "@/lib/session";
import { fetchApi } from "@/lib/api";
import { OnboardingProfile, Product } from "@/lib/types";

// Namespaced keys
const onboardingKey = (userId: string) => `skincares_onboarding_${userId}`;
const wishlistKey = (userId: string) => `skincares_wishlist_${userId}`;

export function useUserState() {
  const [userId, setUserId] = useState<string | null>(getAuthUserId());
  const [onboarding, setOnboarding] = useState<OnboardingProfile | null>(null);
  const [wishlist, setWishlist] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);

  // Clear all user state
  const clearUserState = useCallback(() => {
    // Remove all user-specific keys
    Object.keys(localStorage).forEach((key) => {
      if (key.startsWith("skincares_onboarding_") || key.startsWith("skincares_wishlist_")) {
        localStorage.removeItem(key);
      }
    });
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
      // Always fetch onboarding from backend after login
      const onboardingResp = await fetchApi<{ user_id: string; profile: OnboardingProfile }>("/onboarding/profile");
      setOnboarding(onboardingResp.profile);
      localStorage.setItem(onboardingKey(uid), JSON.stringify(onboardingResp.profile));
    } catch {
      setOnboarding(null);
      localStorage.removeItem(onboardingKey(uid));
    }
    try {
      // Always fetch wishlist from backend after login
      const wishlistResp = await fetchApi<{ products: Product[] }>("/wishlist");
      setWishlist(wishlistResp.products);
      localStorage.setItem(wishlistKey(uid), JSON.stringify(wishlistResp.products));
    } catch {
      setWishlist([]);
      localStorage.removeItem(wishlistKey(uid));
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
      // On login, always rehydrate from backend
      hydrateUserState();
    };
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, [hydrateUserState]);

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
