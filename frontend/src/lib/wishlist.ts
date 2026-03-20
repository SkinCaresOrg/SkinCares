const WISHLIST_KEY = "skincares_wishlist";

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
  return [...list];
}

export function isInWishlist(productId: number): boolean {
  return getWishlist().includes(productId);
}

export function getUserId(): string | null {
  return localStorage.getItem("skincares_user_id");
}

export function setUserId(id: string): void {
  localStorage.setItem("skincares_user_id", id);
}

export function clearUserId(): void {
  localStorage.removeItem("skincares_user_id");
}
