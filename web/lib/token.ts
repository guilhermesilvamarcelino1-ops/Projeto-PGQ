const KEY = "procede_token";

export function saveToken(token: string) {
  if (typeof window !== "undefined") localStorage.setItem(KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function clearToken() {
  if (typeof window !== "undefined") localStorage.removeItem(KEY);
}
