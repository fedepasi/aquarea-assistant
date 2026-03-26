"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

export function MessageBubble({ message }: { message: Message }) {
  const [showCitations, setShowCitations] = useState(false);
  const [lightboxImage, setLightboxImage] = useState<ImageResult | null>(null);
  const isUser = message.role === "user";

  return (
    <>
      {/* Lightbox overlay */}
      {lightboxImage && (
        <div
          onClick={() => setLightboxImage(null)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.85)",
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            cursor: "zoom-out",
            padding: "20px",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              maxWidth: "90vw",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
            }}
          >
            <img
              src={`/images/v4/${lightboxImage.filename}`}
              alt={`${lightboxImage.docName} - pag. ${lightboxImage.page}`}
              style={{
                maxWidth: "100%",
                maxHeight: "78vh",
                objectFit: "contain",
                borderRadius: "8px",
                background: "white",
              }}
            />
            <div
              style={{
                color: "white",
                marginTop: "12px",
                textAlign: "center",
                fontSize: "14px",
              }}
            >
              <strong>{lightboxImage.docName}</strong>
              {" \u2014 "}Pagina {lightboxImage.page}
              {" \u00B7 "}Rilevanza: {Math.round(lightboxImage.score * 100)}%
            </div>
          </div>
          <button
            onClick={() => setLightboxImage(null)}
            style={{
              position: "absolute",
              top: "16px",
              right: "24px",
              background: "rgba(255,255,255,0.2)",
              border: "none",
              color: "white",
              fontSize: "28px",
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              lineHeight: 1,
            }}
          >
            \u00D7
          </button>
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
          marginBottom: "16px",
        }}
      >
        {/* Role label */}
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-secondary)",
            marginBottom: "4px",
            padding: "0 4px",
          }}
        >
          {isUser ? "Tu" : "Aquarea Assistant"}
        </span>

        {/* Bubble */}
        <div
          style={{
            background: isUser ? "var(--user-bubble)" : "var(--bot-bubble)",
            color: isUser ? "white" : "var(--text-primary)",
            borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
            padding: "14px 18px",
            maxWidth: "85%",
            lineHeight: 1.6,
            fontSize: "14.5px",
            wordBreak: "break-word",
          }}
        >
          {isUser ? (
            <p style={{ margin: 0 }}>{message.text}</p>
          ) : (
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.text}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Related images from manuals */}
        {!isUser && message.images && message.images.length > 0 && (
          <div
            style={{
              maxWidth: "85%",
              marginTop: "10px",
            }}
          >
            <div
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--panasonic-blue)",
                marginBottom: "8px",
                padding: "0 4px",
              }}
            >
              Immagini dai manuali
            </div>
            <div
              style={{
                display: "flex",
                gap: "10px",
                flexWrap: "wrap",
              }}
            >
              {message.images.map((img, i) => (
                <div
                  key={i}
                  style={{
                    border: "1px solid var(--border-color)",
                    borderRadius: "10px",
                    overflow: "hidden",
                    background: "white",
                    cursor: "zoom-in",
                    transition: "box-shadow 0.2s, transform 0.2s",
                    maxWidth: "220px",
                  }}
                  onClick={() => setLightboxImage(img)}
                  onMouseOver={(e) => {
                    e.currentTarget.style.boxShadow =
                      "0 4px 12px rgba(0,84,166,0.2)";
                    e.currentTarget.style.transform = "scale(1.02)";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.boxShadow = "none";
                    e.currentTarget.style.transform = "scale(1)";
                  }}
                >
                  <img
                    src={`/images/v4/${img.filename}`}
                    alt={`${img.docName} - pag. ${img.page}`}
                    style={{
                      width: "100%",
                      height: "160px",
                      objectFit: "cover",
                      display: "block",
                    }}
                    loading="lazy"
                  />
                  <div
                    style={{
                      padding: "8px 10px",
                      fontSize: "11px",
                      borderTop: "1px solid var(--border-color)",
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: "var(--panasonic-blue)",
                      }}
                    >
                      {img.docName}
                    </div>
                    <div style={{ color: "var(--text-secondary)" }}>
                      Pagina {img.page} {"\u00B7"} Rilevanza:{" "}
                      {Math.round(img.score * 100)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Citations toggle */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div style={{ maxWidth: "85%", marginTop: "6px" }}>
            <button
              onClick={() => setShowCitations(!showCitations)}
              style={{
                background: "none",
                border: "none",
                color: "var(--panasonic-blue)",
                cursor: "pointer",
                fontSize: "12px",
                padding: "4px 8px",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                transition: "background 0.2s",
              }}
              onMouseOver={(e) =>
                (e.currentTarget.style.background = "var(--panasonic-light)")
              }
              onMouseOut={(e) =>
                (e.currentTarget.style.background = "none")
              }
            >
              {message.citations.length}{" "}
              {message.citations.length === 1 ? "fonte" : "fonti"}{" "}
              {showCitations ? "\u25B2" : "\u25BC"}
            </button>

            {showCitations && (
              <div
                style={{
                  marginTop: "8px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                {message.citations.map((cit, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid var(--border-color)",
                      borderRadius: "10px",
                      padding: "10px 14px",
                      fontSize: "12px",
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: "var(--panasonic-blue)",
                        marginBottom: "4px",
                        fontSize: "11px",
                      }}
                    >
                      Fonte: {cit.source}
                    </div>
                    {cit.content && (
                      <p
                        style={{
                          margin: 0,
                          color: "var(--text-secondary)",
                          lineHeight: 1.5,
                        }}
                      >
                        {cit.content.length > 300
                          ? cit.content.substring(0, 300) + "..."
                          : cit.content}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <span
          style={{
            fontSize: "10px",
            color: "#9ca3af",
            marginTop: "4px",
            padding: "0 4px",
          }}
        >
          {message.timestamp.toLocaleTimeString("it-IT", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </>
  );
}