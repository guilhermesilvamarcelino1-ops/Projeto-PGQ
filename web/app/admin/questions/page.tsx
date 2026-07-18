"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/api";
import { getToken } from "@/lib/token";

interface QuestionLog {
  id: string;
  content: string;
  had_fallback: boolean;
  created_at: string;
}

export default function QuestionsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<QuestionLog[]>([]);
  const [onlyFallback, setOnlyFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) {
      router.replace("/admin/login");
      return;
    }
    try {
      const res = await authFetch(`/admin/questions?only_fallback=${onlyFallback}`, token);
      setRows(await res.json());
    } catch (e) {
      setError((e as Error).message);
    }
  }, [router, onlyFallback]);

  useEffect(() => {
    load();
  }, [load]);

  // Perguntas repetidas apontam procedimento mal escrito — contamos ocorrências por texto.
  const counts = rows.reduce<Record<string, number>>((acc, r) => {
    const key = r.content.trim().toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="container">
      <h2>Perguntas</h2>
      <div className="card">
        <label className="row" style={{ fontWeight: 400 }}>
          <input
            type="checkbox"
            checked={onlyFallback}
            onChange={(e) => setOnlyFallback(e.target.checked)}
            style={{ width: "auto" }}
          />
          Mostrar só perguntas sem resposta boa (fallback)
        </label>
      </div>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Pergunta</th>
              <th>Repetições</th>
              <th>Resultado</th>
              <th>Quando</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.content}</td>
                <td>{counts[r.content.trim().toLowerCase()]}</td>
                <td>
                  <span className={`tag ${r.had_fallback ? "tag-fallback" : "tag-ok"}`}>
                    {r.had_fallback ? "sem resposta" : "respondida"}
                  </span>
                </td>
                <td>{new Date(r.created_at).toLocaleString("pt-BR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="muted">Nenhuma pergunta registrada.</p>}
      </div>
    </div>
  );
}
