"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/api";
import { getToken } from "@/lib/token";

interface StatusConexao {
  conectado: boolean;
  provedor?: string;
  conta?: string;
  pasta_raiz?: string;
  conectado_em?: string;
  ultimo_erro?: string | null;
}

export default function ConexoesPage() {
  const router = useRouter();
  const [status, setStatus] = useState<StatusConexao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [conectando, setConectando] = useState(false);

  const carregar = useCallback(async () => {
    const token = getToken();
    if (!token) {
      router.replace("/admin/login");
      return;
    }
    try {
      const res = await authFetch("/drive/status", token);
      setStatus(await res.json());
    } catch (e) {
      setErro((e as Error).message);
    }
  }, [router]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function conectar() {
    const token = getToken();
    if (!token) return;
    setErro(null);
    setConectando(true);
    try {
      const res = await authFetch("/drive/connect", token);
      const { authorize_url } = await res.json();
      // A autorização acontece na tela da própria Microsoft — nunca pedimos a senha.
      window.open(authorize_url, "_blank", "noopener");
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setConectando(false);
    }
  }

  return (
    <div className="container">
      <h2>Conexões</h2>
      <p className="muted">
        Onde os documentos arquivados são guardados. Conectando o OneDrive, o acervo fica no drive da
        própria empresa, com a estrutura de pastas que ela já usa.
      </p>

      <div className="card">
        <h3>OneDrive / SharePoint</h3>

        {status === null && <p className="muted">Verificando...</p>}

        {status?.conectado ? (
          <>
            <p>
              <span className="tag tag-ok">conectado</span>
            </p>
            <div className="kv-list">
              <p>
                <b>Conta:</b> {status.conta}
              </p>
              <p>
                <b>Pasta raiz:</b> {status.pasta_raiz}
              </p>
            </div>
            {status.ultimo_erro && (
              <p style={{ color: "#c0392b" }}>Último erro: {status.ultimo_erro}</p>
            )}
            <button className="btn" onClick={conectar} disabled={conectando}>
              Reconectar
            </button>
          </>
        ) : (
          status !== null && (
            <>
              <p>
                <span className="tag tag-fallback">não conectado</span>
              </p>
              <p className="muted">
                Enquanto não houver conexão, os documentos confirmados ficam guardados no próprio
                sistema. A classificação, o nome e a pasta funcionam igual — só o destino final muda.
              </p>
              <button className="btn" onClick={conectar} disabled={conectando}>
                {conectando ? "Abrindo..." : "Conectar OneDrive"}
              </button>
            </>
          )
        )}

        {erro && <p style={{ color: "#c0392b" }}>{erro}</p>}
      </div>

      <p className="muted">
        A autorização acontece na tela da Microsoft — o sistema nunca pede a sua senha, e você pode
        revogar o acesso quando quiser.
      </p>
    </div>
  );
}
