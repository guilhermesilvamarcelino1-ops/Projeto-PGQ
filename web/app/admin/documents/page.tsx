"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/api";
import { getToken } from "@/lib/token";

interface DocOut {
  id: string;
  title: string;
  category: string;
  kind: string;
  version: number;
  status: string;
  uploaded_at: string;
}

export default function DocumentsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<DocOut[]>([]);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("procedimentos de execução");
  const [kind, setKind] = useState<"procedimento" | "administrativo">("procedimento");
  const [siteId, setSiteId] = useState("");
  const [plainText, setPlainText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) {
      router.replace("/admin/login");
      return;
    }
    try {
      const res = await authFetch("/documents", token);
      setDocs(await res.json());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpload() {
    const token = getToken();
    if (!token) return;
    setMsg(null);
    setLoading(true);
    const form = new FormData();
    form.append("title", title);
    form.append("category", category);
    form.append("kind", kind);
    if (siteId) form.append("site_id", siteId);
    if (plainText) form.append("plain_text", plainText);
    if (file) form.append("file", file);
    try {
      const res = await authFetch("/documents/upload", token, { method: "POST", body: form });
      const data = await res.json();
      setMsg(`Enviado: ${data.document.title} (${data.chunks_created} trechos indexados).`);
      setTitle("");
      setPlainText("");
      setFile(null);
      await load();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <h2>Documentos</h2>

      <div className="card">
        <h3>Novo documento</h3>
        <label>Título</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />

        <label>Categoria (texto livre)</label>
        <input className="input" value={category} onChange={(e) => setCategory(e.target.value)} />

        <label>Pasta mãe</label>
        <select
          className="select"
          value={kind}
          onChange={(e) => setKind(e.target.value as "procedimento" | "administrativo")}
        >
          <option value="procedimento">Procedimento (indexado para busca)</option>
          <option value="administrativo">Administrativo (alvará, ART... retornado inteiro)</option>
        </select>

        <label>ID da obra (opcional, recomendado para administrativo)</label>
        <input className="input" value={siteId} onChange={(e) => setSiteId(e.target.value)} placeholder="uuid da obra" />

        <label>Arquivo (PDF)</label>
        <input type="file" accept=".pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <p className="muted">
          Procedimentos devem ser enviados em PDF — é o que permite abrir o documento direto na página
          citada na resposta. Se o arquivo estiver em Word, salve como PDF antes de enviar.
        </p>

        <label>...ou cole o texto do procedimento</label>
        <textarea className="textarea" rows={4} value={plainText} onChange={(e) => setPlainText(e.target.value)} />

        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn" onClick={handleUpload} disabled={loading || !title}>
            {loading ? "Enviando..." : "Enviar e indexar"}
          </button>
          {msg && <span className="muted">{msg}</span>}
        </div>
      </div>

      <div className="card">
        <h3>Documentos cadastrados</h3>
        <table>
          <thead>
            <tr>
              <th>Título</th>
              <th>Categoria</th>
              <th>Tipo</th>
              <th>Versão</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.title}</td>
                <td>{d.category}</td>
                <td>{d.kind}</td>
                <td>v{d.version}</td>
                <td>{d.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {docs.length === 0 && <p className="muted">Nenhum documento ainda.</p>}
      </div>
    </div>
  );
}
