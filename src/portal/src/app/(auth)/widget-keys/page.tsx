"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { authFetch } from "@/lib/auth-fetch";
import { GATEWAY_URL } from "@/lib/api";

interface WidgetKey {
  id: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-mono, monospace)",
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 20,
        background: active ? "rgba(34,197,94,0.1)" : "rgba(107,114,128,0.1)",
        color: active ? "#16a34a" : "var(--ink-3)",
      }}
    >
      {active ? "active" : "revoked"}
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
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<{ id: string; raw_key: string; key_prefix: string } | null>(null);

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
    navigator.clipboard.writeText(key.key_prefix).then(() => {
      setCopiedId(key.id);
      setTimeout(() => setCopiedId(null), 1500);
    });
  }

  async function handleCreate() {
    if (!user?.tenantSlug || creating) return;
    setCreating(true);
    try {
      const res = await authFetch(`${GATEWAY_URL}/api/v1/tenants/${user.tenantSlug}/widget-keys`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setNewKey(data);
        setKeys((prev) => [{ id: data.id, key_prefix: data.key_prefix, created_at: new Date().toISOString(), last_used_at: null }, ...prev]);
      }
    } catch {
      // silent
    } finally {
      setCreating(false);
    }
  }

  return (
    <div
      className="animate-fade-up"
      style={{ padding: "28px 32px 60px", maxWidth: 1100, margin: "0 auto" }}
    >
      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
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
          onClick={handleCreate}
          disabled={creating}
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontSize: 13,
            fontWeight: 600,
            padding: "8px 16px",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-3)",
            color: "var(--ink)",
            cursor: creating ? "not-allowed" : "pointer",
            opacity: creating ? 0.6 : 1,
          }}
        >
          {creating ? "Creating…" : "+ Create Key"}
        </button>
      </div>

      {/* New key reveal banner */}
      {newKey && (
        <div
          style={{
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.3)",
            borderRadius: 12,
            padding: "16px 20px",
            marginBottom: 16,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              fontWeight: 600,
              color: "#16a34a",
              marginBottom: 8,
            }}
          >
            Key created — copy it now, it won&apos;t be shown again.
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <code
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 13,
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
                borderRadius: 6,
                padding: "6px 12px",
                color: "var(--ink)",
                flex: 1,
                overflowX: "auto",
              }}
            >
              {newKey.raw_key}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newKey.raw_key);
                setCopiedId(newKey.id);
                setTimeout(() => setCopiedId(null), 1500);
              }}
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                fontWeight: 600,
                padding: "6px 14px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: copiedId === newKey.id ? "var(--primary-soft)" : "transparent",
                color: copiedId === newKey.id ? "var(--primary)" : "var(--ink-3)",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {copiedId === newKey.id ? "Copied!" : "Copy"}
            </button>
            <button
              onClick={() => setNewKey(null)}
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                fontWeight: 600,
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "transparent",
                color: "var(--ink-3)",
                cursor: "pointer",
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

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
            onClick={handleCreate}
            disabled={creating}
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              fontWeight: 600,
              padding: "8px 20px",
              borderRadius: 8,
              border: "1px solid var(--primary-line)",
              background: "var(--primary-soft)",
              color: "var(--primary)",
              cursor: creating ? "not-allowed" : "pointer",
              opacity: creating ? 0.6 : 1,
            }}
          >
            {creating ? "Creating…" : "Create Key"}
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
                {["Key Prefix", "Created", "Last Used", ""].map((h) => (
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
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: 12,
                      color: "var(--ink-2)",
                    }}
                  >
                    {key.key_prefix}…
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
                  <td
                    style={{
                      padding: "12px 16px",
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: 11,
                      color: "var(--ink-3)",
                    }}
                  >
                    {key.last_used_at ? formatDate(key.last_used_at) : "—"}
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
