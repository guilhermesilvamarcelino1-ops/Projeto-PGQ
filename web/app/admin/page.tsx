"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getToken, clearToken } from "@/lib/token";

export default function AdminHome() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
    } else {
      setReady(true);
    }
  }, [router]);

  if (!ready) return null;

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Painel administrativo</h2>
        <button
          className="btn"
          onClick={() => {
            clearToken();
            router.replace("/admin/login");
          }}
        >
          Sair
        </button>
      </div>
      <div className="card">
        <p>
          <Link href="/admin/documents">→ Documentos (upload, versões)</Link>
        </p>
        <p>
          <Link href="/admin/questions">→ Perguntas recentes / sem resposta boa</Link>
        </p>
        <p>
          <Link href="/admin/conexoes">→ Conexões (onde os documentos são guardados)</Link>
        </p>
      </div>
    </div>
  );
}
