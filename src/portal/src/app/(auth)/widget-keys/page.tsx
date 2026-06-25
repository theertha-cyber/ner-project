"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { authFetch } from "@/lib/auth-fetch";
import { GATEWAY_URL } from "@/lib/api";

interface WidgetKey {
  id: string;
  name: string;
  value: string;
  created_at: string;
  status: "active" | "revoked";
}

function StatusBadge({ status }: { status: "active" | "revoked" }) {
  const isActive = status === "active";
  return (
    <span
      style={{
        fontFamily: "var(--font-mono, monospace)",
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 20,
        background: isActive ? "rgba(34,197,94,0.1)" : "rgba(107,114,128,0.1)",
        color: isActive ? "#16a34a" : "var(--ink-3)",
      }}
    >
      {status}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

export default function WidgetKeysPage() {
  const { user } = useAuth();
  const [keys, setKeys] = useState<WidgetKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.tenantSlug) {
      setLoading(false);
      return;
    }
    authFetch(`${GATEWAY_URL}/api/v1/tenants/${user.tenantSlug}/widget-keys`)
      .then((res) => (res.ok ? res.json() : Promise.resolve([])))
      .then((data) => setKeys(Array.isArray(data) ? data : []))
      .catch(() => setKeys([]))
      .finally(() => setLoading(false));
  }, [user?.tenantSlug]);

  function handleCopy(key: WidgetKey) {
    navigator.clipboard.writeText(key.value).then(() => {
      setCopiedId(key.id);
      setTimeout(() => setCopiedId(null), 1500);
    });
  }

  const slug = user?.tenantSlug ?? "{slug}";

  return (
    <div
      className="animate-fade-up"
      style={{ padding: "28px 32px 60px", maxWidth: 1100, margin: "0 auto" }}
    >
      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <div
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 11,
            color: "var(--ink-3)",
            marginBottom: 6,
          }}
        >
          /api/v1/tenants/{slug}/widget-keys · port 8006
        </div>
        <h1
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontWeight: 800,
            fontSize: 34,
            color: "var(--ink)",
            lineHeight: 1.1,
            margin: 0,
          }}
        >
          Widget Keys
        </h1>
        <p
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontSize: 14,
            color: "var(--ink-3)",
            marginTop: 8,
          }}
        >
          API keys for embedding the NER widget in external applications.
        </p>
      </div>

      {/* Toolbar row */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button
          onClick={() => console.log("Create Key — not implemented")}
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontSize: 13,
            fontWeight: 600,
            padding: "8px 16px",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-3)",
            color: "var(--ink)",
            cursor: "pointer",
          }}
        >
          + Create Key
        </button>
      </div>

      {/* Keys table or empty state */}
      {loading ? (
        <div
          style={{
            background: "var(--surface-3)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            padding: "40px 24px",
            textAlign: "center",
            color: "var(--ink-3)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 13,
          }}
        >
          Loading…
        </div>
      ) : keys.length === 0 ? (
        /* Empty state */
        <div
          style={{
            background: "var(--surface-3)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            padding: "56px 24px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: 32,
              marginBottom: 12,
              opacity: 0.4,
            }}
          >
            ⊟
          </div>
          <p
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 600,
              fontSize: 15,
              color: "var(--ink)",
              margin: "0 0 6px",
            }}
          >
            No widget keys configured
          </p>
          <p
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              color: "var(--ink-3)",
              margin: "0 0 24px",
            }}
          >
            Create a key to start embedding the NER widget in your application.
          </p>
          <button
            onClick={() => console.log("Create Key — not implemented")}
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              fontWeight: 600,
              padding: "8px 20px",
              borderRadius: 8,
              border: "1px solid var(--primary-line)",
              background: "var(--primary-soft)",
              color: "var(--primary)",
              cursor: "pointer",
            }}
          >
            Create Key
          </button>
        </div>
      ) : (
        /* Keys table */
        <div
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  background: "var(--surface-3)",
                  borderBottom: "1px solid var(--line)",
                }}
              >
                {["Name", "Key Prefix", "Created", "Status", ""].map((h) => (
                  <th
                    key={h}
                    style={{
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--ink-3)",
                      padding: "10px 16px",
                      textAlign: "left",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {keys.map((key, i) => (
                <tr
                  key={key.id}
                  style={{
                    borderBottom: i < keys.length - 1 ? "1px solid var(--line)" : "none",
                  }}
                >
                  <td
                    style={{
                      padding: "12px 16px",
                      fontFamily: "var(--font-display, sans-serif)",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "var(--ink)",
                    }}
                  >
                    {key.name}
                  </td>
                  <td
                    style={{
                      padding: "12px 16px",
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: 12,
                      color: "var(--ink-2)",
                    }}
                  >
                    {key.value.slice(0, 8)}…
                  </td>
                  <td
                    style={{
                      padding: "12px 16px",
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: 11,
                      color: "var(--ink-3)",
                    }}
                  >
                    {formatDate(key.created_at)}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <StatusBadge status={key.status} />
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      onClick={() => handleCopy(key)}
                      style={{
                        fontFamily: "var(--font-mono, monospace)",
                        fontSize: 11,
                        fontWeight: 600,
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "1px solid var(--line)",
                        background: copiedId === key.id ? "var(--primary-soft)" : "transparent",
                        color: copiedId === key.id ? "var(--primary)" : "var(--ink-3)",
                        cursor: "pointer",
                        transition: "background 0.15s, color 0.15s",
                      }}
                    >
                      {copiedId === key.id ? "Copied!" : "Copy"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
