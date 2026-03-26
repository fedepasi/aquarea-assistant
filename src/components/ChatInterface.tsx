"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageBubble } from "./MessageBubble";

interface ImageResult {
  filename: string;
  docName: string;
  page: number;
  score: number;
  contextText: string;
}

interface Message {
  id: string;
  role: "user" | "model";
  text: string;
  citations?: Array<{ content: string; source: string }>;
  images?: ImageResult[];
  timestamp: Date;
}

const SUGGESTED_QUESTIONS = [
  "Come si accende la pompa di calore?",
  "Quali sono i codici errore più comuni?",
  "Come impostare la temperatura dell'acqua calda sanitaria?",
  "What are the specifications of the outdoor unit WH-WXG12ME8?",
  "Come funziona la modalità silenziosa?",
  "Come si effettua la sterilizzazione del serbatoio?",
];

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height =
        Math.min(inputRef.current.scrollHeight, 150) + "px";
    }
  }, [input]);

  const sendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isLoading) return;

    setInput("");
    setError(null);

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: messageText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Build conversation history for context
      const history = [...messages, userMessage].map((m) => ({
        role: m.role,
        text: m.text,
      }));

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Errore nella risposta del server");
      }

      const botMessage: Message = {
        id: crypto.randomUUID(),
        role: "model",
        text: data.text,
        citations: data.citations,
        images: data.images,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err: any) {
      setError(err.message || "Errore di connessione");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: "900px",
        margin: "0 auto",
        background: "var(--bg-chat)",
        boxShadow: "0 0 40px rgba(0,0,0,0.08)",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 24px",
          background: "var(--panasonic-blue)",
          color: "white",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "22px",
            }}
          >
            🌡️
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>
              Aquarea Assistant
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: "12px",
                opacity: 0.8,
              }}
            >
              Panasonic Heat Pump — Interactive Manual
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            style={{
              background: "rgba(255,255,255,0.15)",
              color: "white",
              border: "none",
              padding: "8px 16px",
              borderRadius: "8px",
              cursor: "pointer",
              fontSize: "13px",
              transition: "background 0.2s",
            }}
            onMouseOver={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.25)")
            }
            onMouseOut={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.15)")
            }
          >
            Nuova chat
          </button>
        )}
      </header>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "24px",
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              textAlign: "center",
              padding: "40px 20px",
            }}
          >
            <div style={{ fontSize: "56px", marginBottom: "16px" }}>🌡️</div>
            <h2
              style={{
                fontSize: "24px",
                fontWeight: 700,
                color: "var(--panasonic-blue)",
                margin: "0 0 8px",
              }}
            >
              Benvenuto in Aquarea Assistant
            </h2>
            <p
              style={{
                color: "var(--text-secondary)",
                maxWidth: "500px",
                lineHeight: 1.6,
                margin: "0 0 32px",
              }}
            >
              Chiedimi qualsiasi cosa sui manuali della tua pompa di calore
              Panasonic Aquarea. Rispondo in italiano, inglese o qualsiasi
              lingua tu preferisca.
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                gap: "10px",
                width: "100%",
                maxWidth: "600px",
              }}
            >
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(q)}
                  style={{
                    background: "var(--panasonic-light)",
                    border: "1px solid transparent",
                    borderRadius: "12px",
                    padding: "12px 16px",
                    fontSize: "13px",
                    color: "var(--panasonic-blue)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s",
                    lineHeight: 1.4,
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.borderColor = "var(--panasonic-blue)";
                    e.currentTarget.style.background = "#dbe8fd";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.borderColor = "transparent";
                    e.currentTarget.style.background = "var(--panasonic-light)";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "16px 0",
                }}
              >
                <div
                  style={{
                    background: "var(--bot-bubble)",
                    borderRadius: "16px",
                    padding: "14px 20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div
          style={{
            margin: "0 24px",
            padding: "12px 16px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "10px",
            color: "#dc2626",
            fontSize: "13px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>⚠️ {error}</span>
          <button
            onClick={() => setError(null)}
            style={{
              background: "none",
              border: "none",
              color: "#dc2626",
              cursor: "pointer",
              fontSize: "16px",
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: "16px 24px 24px",
          borderTop: "1px solid var(--border-color)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "12px",
            alignItems: "flex-end",
          }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Scrivi la tua domanda..."
            rows={1}
            style={{
              flex: 1,
              resize: "none",
              border: "2px solid var(--border-color)",
              borderRadius: "14px",
              padding: "12px 16px",
              fontSize: "15px",
              lineHeight: 1.5,
              outline: "none",
              transition: "border-color 0.2s",
              fontFamily: "inherit",
              maxHeight: "150px",
            }}
            onFocus={(e) =>
              (e.currentTarget.style.borderColor = "var(--panasonic-blue)")
            }
            onBlur={(e) =>
              (e.currentTarget.style.borderColor = "var(--border-color)")
            }
          />
          <button
            onClick={() => sendMessage()}
            disabled={isLoading || !input.trim()}
            style={{
              background:
                isLoading || !input.trim()
                  ? "#94a3b8"
                  : "var(--panasonic-blue)",
              color: "white",
              border: "none",
              borderRadius: "14px",
              width: "48px",
              height: "48px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor:
                isLoading || !input.trim() ? "not-allowed" : "pointer",
              fontSize: "20px",
              transition: "background 0.2s",
              flexShrink: 0,
            }}
          >
            ➤
          </button>
        </div>
        <p
          style={{
            textAlign: "center",
            fontSize: "11px",
            color: "var(--text-secondary)",
            marginTop: "8px",
          }}
        >
          Powered by Gemini AI — Le risposte sono basate sui manuali Panasonic
          Aquarea
        </p>
      </div>
    </div>
  );
}
