"use client";

import { useState } from "react";
import { API_BASE, ChatResponse, sendChatMessage } from "@/lib/api";

interface DisplayMessage {
  role: "user" | "assistant";
  text: string;
  fallback?: boolean;
  sources?: ChatResponse["sources"];
  documentPath?: string | null;
}

export default function ChatPage() {
  // No MVP o número/telefone identifica o usuário; aqui usamos o user_id direto para teste interno.
  const [userId, setUserId] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mediaType, setMediaType] = useState<"text" | "audio" | "image">("text");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    if (!userId) {
      setError("Informe o ID do usuário de campo.");
      return;
    }
    setError(null);
    setLoading(true);

    const userLabel = mediaType === "text" ? text : `[${mediaType}] ${text || "(sem texto)"}`;
    setMessages((m) => [...m, { role: "user", text: userLabel }]);

    const form = new FormData();
    form.append("user_id", userId);
    if (conversationId) form.append("conversation_id", conversationId);
    form.append("channel", "web");
    form.append("media_type", mediaType);
    if (text) form.append("text", text);
    if (file) form.append("file", file);

    try {
      const res = await sendChatMessage(form);
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

  return (
    <div className="container">
      <h2>Chat — dúvidas de procedimento</h2>
      <div className="card">
        <label>ID do usuário de campo</label>
        <input
          className="input"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="uuid do usuário (cadastrado na obra)"
        />
      </div>

      <div className="messages">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="bubble-user">
              {m.text}
            </div>
          ) : (
            <div key={i} className={`bubble-assistant ${m.fallback ? "bubble-fallback" : ""}`}>
              <div>{m.text}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="sources">
                  Fonte:{" "}
                  {m.sources
                    .map((s) =>
                      [s.document_title, s.section_ref && `seção ${s.section_ref}`, s.page_ref && `pág. ${s.page_ref}`]
                        .filter(Boolean)
                        .join(", ")
                    )
                    .join(" · ")}
                </div>
              )}
              {m.documentPath && (
                <div className="sources">
                  <a href={`${API_BASE}/health`} onClick={(e) => e.preventDefault()}>
                    Arquivo: {m.documentPath.split("/").pop()}
                  </a>
                </div>
              )}
            </div>
          )
        )}
      </div>

      <div className="card">
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
          placeholder={mediaType === "image" ? "Descreva sua dúvida sobre a foto" : "Digite sua pergunta"}
        />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" onClick={handleSend} disabled={loading}>
            {loading ? "Enviando..." : "Enviar"}
          </button>
          {error && <span style={{ color: "#c0392b" }}>{error}</span>}
        </div>
      </div>
      <p className="muted">
        A resposta vem sempre dos procedimentos cadastrados. Quando não há resposta no material, o
        assistente indica o responsável técnico — não inventa.
      </p>
    </div>
  );
}
