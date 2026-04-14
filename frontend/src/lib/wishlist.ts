import { supabase } from './supabaseClient';
import { OnboardingProfile } from './types';

// Supabase-backed wishlist functions
export async function getWishlist(): Promise<number[]> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('wishlist')
    .select('product_id')
    .eq('user_id', user.id);
  if (error) return [];
  return data.map((row: { product_id: number }) => row.product_id);
}

export async function toggleWishlist(productId: number): Promise<number[]> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('wishlist')
    .select('id')
    .eq('user_id', user.id)
    .eq('product_id', productId)
    .single();
  if (data && !error) {
    await supabase.from('wishlist').delete().eq('id', data.id);
  } else {
    await supabase.from('wishlist').insert({ user_id: user.id, product_id: productId });
  }
  return getWishlist();
}

export async function isInWishlist(productId: number): Promise<boolean> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;
  const { data, error } = await supabase
    .from('wishlist')
    .select('id')
    .eq('user_id', user.id)
    .eq('product_id', productId)
    .single();
  return !!(data && !error);
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
