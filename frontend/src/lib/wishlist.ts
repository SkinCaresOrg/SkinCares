import { OnboardingProfile } from "./types";

const WISHLIST_KEY = "skincares_wishlist";
const USER_ID_KEY = "skincares_user_id";
const USER_PROFILE_KEY = "skincares_user_profile";

export function getWishlist(): number[] {
  try {
    return JSON.parse(localStorage.getItem(WISHLIST_KEY) || "[]");
  } catch {
    return [];
  }
}

export function toggleWishlist(productId: number): number[] {
  const list = getWishlist();
  const idx = list.indexOf(productId);
  if (idx > -1) list.splice(idx, 1);
  else list.push(productId);
  localStorage.setItem(WISHLIST_KEY, JSON.stringify(list));
  window.dispatchEvent(new Event("storage"));
  return [...list];
}

export function isInWishlist(productId: number): boolean {
  return getWishlist().includes(productId);
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

export function setUserId(id: string): void {
  localStorage.setItem(USER_ID_KEY, id);
}

export function clearUserId(): void {
  localStorage.removeItem(USER_ID_KEY);
}

export function getUserProfile(): OnboardingProfile | null {
  try {
    const data = localStorage.getItem(USER_PROFILE_KEY);
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

export function setUserProfile(profile: OnboardingProfile): void {
  localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));
}

export function clearUserProfile(): void {
  localStorage.removeItem(USER_PROFILE_KEY);
}
