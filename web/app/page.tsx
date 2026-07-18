import Link from "next/link";

export default function Home() {
  return (
    <div className="container">
      <h1>Procede</h1>
      <p className="muted">Assistente de procedimentos de execução da obra.</p>
      <div className="card">
        <p>
          <Link href="/chat">→ Abrir chat (time de campo)</Link>
        </p>
        <p>
          <Link href="/admin">→ Painel administrativo (qualidade/planejamento)</Link>
        </p>
      </div>
    </div>
  );
}
