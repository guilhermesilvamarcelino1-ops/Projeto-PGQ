"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { saveToken } from "@/lib/token";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setError(null);
    setLoading(true);
    try {
      const token = await login(email, password);
      saveToken(token);
      router.replace("/admin");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <h2>Entrar — Painel Procede</h2>
      <div className="card">
        <label>Email</label>
        <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>Senha</label>
        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
        />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn" onClick={handleLogin} disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
          {error && <span style={{ color: "#c0392b" }}>{error}</span>}
        </div>
      </div>
    </div>
  );
}
