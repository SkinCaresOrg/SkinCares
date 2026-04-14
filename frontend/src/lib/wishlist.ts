import { OnboardingProfile } from "./types";

import { getAuthUserId } from "./session";

function getWishlistKeyForUser(userId: string | null) {
  return userId ? `skincares_wishlist_${userId}` : "skincares_wishlist";
}
function getProfileKeyForUser(userId: string | null) {
  return userId ? `skincares_user_profile_${userId}` : "skincares_user_profile";
}

export function getWishlist(): number[] {
  const userId = getAuthUserId();
  try {
    return JSON.parse(localStorage.getItem(getWishlistKeyForUser(userId)) || "[]");
  } catch {
    return [];
  }
}

export function toggleWishlist(productId: number): number[] {
  const userId = getAuthUserId();
  const key = getWishlistKeyForUser(userId);
  const list = getWishlist();
  const idx = list.indexOf(productId);
  if (idx > -1) list.splice(idx, 1);
  else list.push(productId);
  localStorage.setItem(key, JSON.stringify(list));
  window.dispatchEvent(new Event("storage"));
  window.dispatchEvent(new CustomEvent("skincares-wishlist-updated"));
  return [...list];
}

export function isInWishlist(productId: number): boolean {
  return getWishlist().includes(productId);
}

// Deprecated: getUserId/setUserId/clearUserId are no longer needed, use getAuthUserId from session.ts
export function getUserId(): string | null {
  return getAuthUserId();
}
export function setUserId(id: string): void {
  // No-op, handled by session.ts
}
export function clearUserId(): void {
  // Remove all user-specific wishlist/profile keys for the current user
  const userId = getAuthUserId();
  if (userId) {
    localStorage.removeItem(getWishlistKeyForUser(userId));
    localStorage.removeItem(getProfileKeyForUser(userId));
  }
}

export function getUserProfile(): OnboardingProfile | null {
  const userId = getAuthUserId();
  try {
    const data = localStorage.getItem(getProfileKeyForUser(userId));
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

export function setUserProfile(profile: OnboardingProfile): void {
  const userId = getAuthUserId();
  if (userId) {
    localStorage.setItem(getProfileKeyForUser(userId), JSON.stringify(profile));
  }
}

export function clearUserProfile(): void {
  const userId = getAuthUserId();
  if (userId) {
    localStorage.removeItem(getProfileKeyForUser(userId));
  }
}
