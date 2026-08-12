"use client";

import { useState } from "react";
import {
  ChatResponse,
  PropostaArquivamento,
  fieldLogin,
  proposeFiling,
  resolveFiling,
  sendChatMessage,
} from "@/lib/api";

interface DisplayMessage {
  role: "user" | "assistant";
  text: string;
  fallback?: boolean;
  sources?: ChatResponse["sources"];
  documentPath?: string | null;
}

/** A resposta já vem formatada para o celular (quebras de linha, trecho citado e link).
 *  Aqui preservamos as quebras e tornamos o link do procedimento clicável. */
function AnswerText({ text }: { text: string }) {
  return (
    <div style={{ whiteSpace: "pre-wrap" }}>
      {text.split("\n").map((line, i) => (
        <span key={i}>
          {line.startsWith("http") ? (
            <a href={line} target="_blank" rel="noopener noreferrer">
              abrir documento
            </a>
          ) : (
            line
          )}
          {"\n"}
        </span>
      ))}
    </div>
  );
}

export default function ChatPage() {
  // Identidade do time de campo: telefone + PIN emitem um token; a empresa vem do
  // token (server-side), nunca é escolhida pelo cliente. No WhatsApp esta etapa é
  // dispensada — o número verificado pela Meta identifica o usuário.
  const [token, setToken] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mediaType, setMediaType] = useState<"text" | "audio" | "image">("text");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Duas intenções na mesma conversa: tirar dúvida ou guardar um documento.
  const [modo, setModo] = useState<"perguntar" | "arquivar">("perguntar");
  const [proposta, setProposta] = useState<PropostaArquivamento | null>(null);

  async function handleLogin() {
    setAuthError(null);
    try {
      setToken(await fieldLogin(phone, pin));
    } catch (e) {
      setAuthError((e as Error).message);
    }
  }

  async function handleArquivar() {
    if (!token || !file) {
      setError("Escolha o arquivo do documento.");
      return;
    }
    setError(null);
    setLoading(true);
    setMessages((m) => [...m, { role: "user", text: `[documento] ${file.name}` }]);

    const form = new FormData();
    form.append("file", file);
    if (text) form.append("hint", text);

    try {
      const res = await proposeFiling(form, token);
      setMessages((m) => [...m, { role: "assistant", text: res.mensagem, fallback: !res.mapeado }]);
      // Só há o que confirmar quando o documento foi identificado na taxonomia.
      setProposta(res.mapeado ? res : null);
      setText("");
      setFile(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResolver(acao: "confirm" | "reject") {
    if (!token || !proposta?.pendencia_id) return;
    setLoading(true);
    try {
      const res = await resolveFiling(proposta.pendencia_id, acao, token);
      setMessages((m) => [...m, { role: "assistant", text: res.mensagem }]);
      setProposta(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    if (!token) return;
    setError(null);
    setLoading(true);

    const userLabel = mediaType === "text" ? text : `[${mediaType}] ${text || "(sem texto)"}`;
    setMessages((m) => [...m, { role: "user", text: userLabel }]);

    const form = new FormData();
    if (conversationId) form.append("conversation_id", conversationId);
    form.append("media_type", mediaType);
    if (text) form.append("text", text);
    if (file) form.append("file", file);

    try {
      const res = await sendChatMessage(form, token);
      setConversationId(res.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.answer,
          fallback: res.had_fallback,
          sources: res.sources,
          documentPath: res.document_file_path,
        },
      ]);
      setText("");
      setFile(null);
      setMediaType("text");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="container">
        <h2>Entrar — Chat do time de campo</h2>
        <div className="card">
          <label>Telefone (com DDI, ex: +5511999990000)</label>
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <label>PIN</label>
          <input
            className="input"
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
          />
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn" onClick={handleLogin}>
              Entrar
            </button>
            {authError && <span style={{ color: "#c0392b" }}>{authError}</span>}
          </div>
        </div>
        <p className="muted">
          No WhatsApp esse login não existe — o número já identifica você. Aqui na web é só pra teste
          interno com segurança.
        </p>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Chat — dúvidas de procedimento</h2>
        <button className="btn" onClick={() => setToken(null)}>
          Sair
        </button>
      </div>

      <div className="messages">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="bubble-user">
              {m.text}
            </div>
          ) : (
            <div key={i} className={`bubble-assistant ${m.fallback ? "bubble-fallback" : ""}`}>
              <AnswerText text={m.text} />
            </div>
          )
        )}
      </div>

      {proposta && (
        <div className="card" style={{ borderColor: "#1f6feb" }}>
          <p className="muted" style={{ marginTop: 0 }}>
            Nada foi guardado ainda — confirme para arquivar.
          </p>
          <div className="row">
            <button className="btn" onClick={() => handleResolver("confirm")} disabled={loading}>
              ✅ Sim, arquivar
            </button>
            <button
              className="btn"
              style={{ background: "#6b7280" }}
              onClick={() => handleResolver("reject")}
              disabled={loading}
            >
              Não é isso
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <button
            className="btn"
            style={{ background: modo === "perguntar" ? "#1f6feb" : "#9aa4ae" }}
            onClick={() => setModo("perguntar")}
          >
            Tirar dúvida
          </button>
          <button
            className="btn"
            style={{ background: modo === "arquivar" ? "#1f6feb" : "#9aa4ae" }}
            onClick={() => setModo("arquivar")}
          >
            Guardar documento
          </button>
        </div>

        {modo === "perguntar" ? (
          <>
            <div className="row">
              <select
                className="select"
                style={{ maxWidth: 140 }}
                value={mediaType}
                onChange={(e) => setMediaType(e.target.value as "text" | "audio" | "image")}
              >
                <option value="text">Texto</option>
                <option value="audio">Áudio</option>
                <option value="image">Foto</option>
              </select>
              {mediaType !== "text" && (
                <input
                  type="file"
                  accept={mediaType === "audio" ? "audio/*" : "image/*"}
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              )}
            </div>
            <textarea
              className="textarea"
              style={{ marginTop: 8 }}
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={
                mediaType === "image" ? "Descreva sua dúvida sobre a foto" : "Digite sua pergunta"
              }
            />
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn" onClick={handleSend} disabled={loading}>
                {loading ? "Enviando..." : "Enviar"}
              </button>
              {error && <span style={{ color: "#c0392b" }}>{error}</span>}
            </div>
          </>
        ) : (
          <>
            <label>Documento (PDF ou foto)</label>
            <input
              type="file"
              accept="application/pdf,image/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <textarea
              className="textarea"
              style={{ marginTop: 8 }}
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Opcional: diga que documento é. Ex.: rastreabilidade da concretagem de hoje"
            />
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn" onClick={handleArquivar} disabled={loading}>
                {loading ? "Analisando..." : "Enviar documento"}
              </button>
              {error && <span style={{ color: "#c0392b" }}>{error}</span>}
            </div>
          </>
        )}
      </div>
      <p className="muted">
        A resposta vem sempre dos procedimentos cadastrados da sua empresa. Quando não há resposta no
        material, o assistente indica o responsável técnico — não inventa.
      </p>
    </div>
  );
}
