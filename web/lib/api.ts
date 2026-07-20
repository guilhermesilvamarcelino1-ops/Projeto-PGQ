export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface SourceRef {
  document_title: string;
  section_ref?: string | null;
  page_ref?: number | null;
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  had_fallback: boolean;
  sources: SourceRef[];
  document_file_path?: string | null;
}

export async function sendChatMessage(form: FormData, token: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Erro ao enviar mensagem");
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Email ou senha inválidos");
  const data = await res.json();
  return data.access_token as string;
}

export async function fieldLogin(phoneNumber: string, pin: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/field-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: phoneNumber, pin }),
  });
  if (!res.ok) throw new Error("Telefone ou PIN inválidos");
  const data = await res.json();
  return data.access_token as string;
}

export async function authFetch(path: string, token: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Erro na requisição");
  }
  return res;
}
