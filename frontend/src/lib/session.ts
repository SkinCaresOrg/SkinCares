import { OnboardingProfile } from "./types";

const TOKEN_KEY = "token";
const AUTH_USER_ID_KEY = "skincares_auth_user_id";
const ONBOARDING_BY_AUTH_USER_KEY = "skincares_onboarding_by_auth_user";

type OnboardingCache = Record<
  string,
  {
    recommendationUserId: string;
    profile: OnboardingProfile;
    completedAt: string;
  }
>;

function decodeJwtSub(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    const parsed = JSON.parse(atob(padded));
    const sub = parsed?.sub;
    return typeof sub === "string" && sub.length > 0 ? sub : null;
  } catch {
    return null;
  }
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  const token = getAuthToken();
  if (!token) return false;

  const payload = decodeJwtPayload(token);
  const exp = payload?.exp;
  if (typeof exp === "number" && Date.now() >= exp * 1000) {
    clearAuthSession();
    return false;
  }

  return true;
}

export function setAuthSession(token: string, authUserId?: string): void {
  localStorage.removeItem(AUTH_USER_ID_KEY);
  localStorage.removeItem("skincares_user_id");
  localStorage.removeItem("skincares_user_profile");

  localStorage.setItem(TOKEN_KEY, token);
  const resolvedAuthUserId = authUserId || decodeJwtSub(token);
  if (resolvedAuthUserId) {
    localStorage.setItem(AUTH_USER_ID_KEY, resolvedAuthUserId);
  }
  window.dispatchEvent(new Event("storage"));
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_ID_KEY);
  localStorage.removeItem("skincares_user_id");
  localStorage.removeItem("skincares_user_profile");
  window.dispatchEvent(new Event("storage"));
}

export function getAuthUserId(): string | null {
  const stored = localStorage.getItem(AUTH_USER_ID_KEY);
  if (stored) return stored;

  const token = getAuthToken();
  if (!token) return null;

  const decoded = decodeJwtSub(token);
  if (decoded) {
    localStorage.setItem(AUTH_USER_ID_KEY, decoded);
  }
  return decoded;
}

function readOnboardingCache(): OnboardingCache {
  try {
    const raw = localStorage.getItem(ONBOARDING_BY_AUTH_USER_KEY);
    return raw ? (JSON.parse(raw) as OnboardingCache) : {};
  } catch {
    return {};
  }
}

function writeOnboardingCache(cache: OnboardingCache): void {
  localStorage.setItem(ONBOARDING_BY_AUTH_USER_KEY, JSON.stringify(cache));
}

export function saveOnboardingForCurrentUser(data: {
  recommendationUserId: string;
  profile: OnboardingProfile;
}): void {
  const authUserId = getAuthUserId();
  if (!authUserId) return;

  const cache = readOnboardingCache();
  cache[authUserId] = {
    recommendationUserId: data.recommendationUserId,
    profile: data.profile,
    completedAt: new Date().toISOString(),
  };
  writeOnboardingCache(cache);

  // Store onboarding/profile per user
  localStorage.setItem(`skincares_user_id_${authUserId}`, data.recommendationUserId);
  localStorage.setItem(`skincares_user_profile_${authUserId}`, JSON.stringify(data.profile));
}

export function hasCompletedOnboardingForCurrentUser(): boolean {
  const authUserId = getAuthUserId();
  if (!authUserId) return false;
  const cache = readOnboardingCache();
  return !!cache[authUserId];
}

export function hydrateOnboardingForCurrentUser(): boolean {
  const authUserId = getAuthUserId();
  if (!authUserId) return false;

  const cache = readOnboardingCache();
  const entry = cache[authUserId];
  if (!entry) return false;

  // Store onboarding/profile per user
  localStorage.setItem(`skincares_user_id_${authUserId}`, entry.recommendationUserId);
  localStorage.setItem(`skincares_user_profile_${authUserId}`, JSON.stringify(entry.profile));
  return true;
}
