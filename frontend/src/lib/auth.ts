import { fetchApi } from "./api";
import { clearAuthSession } from "./session";

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  return fetchApi<{ access_token: string }>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string) {
  return fetchApi("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function getCurrentUser(): Promise<{ id: string; email: string }> {
  return fetchApi("/auth/me");
}

export function logout(): void {
  clearAuthSession();
}
