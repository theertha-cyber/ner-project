"use client";

import { useState, FormEvent } from "react";

export interface CreateUserPayload {
  email: string;
  password: string;
  role: string;
}

interface CreateUserFormProps {
  roles: readonly string[];
  onSubmit: (payload: CreateUserPayload) => Promise<{ ok: boolean; errorMessage?: string; status?: number }>;
  onSuccess: () => void;
  onCancel: () => void;
  tenantLabel?: string;
}

export function CreateUserForm({ roles, onSubmit, onSuccess, onCancel, tenantLabel }: CreateUserFormProps) {
  const [form, setForm] = useState<CreateUserPayload>({ email: "", password: "", role: roles[0] });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const result = await onSubmit(form);
      if (!result.ok) {
        const msg = result.errorMessage ?? "Request failed";
        if (result.status === 409) setError(`Email already taken: ${msg}`);
        else if (result.status === 429) setError(`Quota exceeded: ${msg}`);
        else if (result.status === 403) setError(`Tenant deactivated: ${msg}`);
        else setError(msg);
        return;
      }
      setForm({ email: "", password: "", role: roles[0] });
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mb-6 rounded-lg border p-4 shadow-sm" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <h2 className="mb-3 text-sm font-medium" style={{ color: "var(--ink)" }}>New User</h2>
      {tenantLabel && (
        <p className="mb-3 text-xs" style={{ color: "var(--ink-2)" }}>
          Tenant: <span style={{ color: "var(--ink)" }}>{tenantLabel}</span>
        </p>
      )}
      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="create-user-email" className="block text-xs" style={{ color: "var(--ink-2)" }}>Email</label>
          <input
            id="create-user-email"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="mt-1 block w-full rounded-md px-3 py-2 text-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          />
        </div>
        <div>
          <label htmlFor="create-user-password" className="block text-xs" style={{ color: "var(--ink-2)" }}>Password</label>
          <input
            id="create-user-password"
            type="password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Min 8 characters"
            className="mt-1 block w-full rounded-md px-3 py-2 text-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          />
        </div>
        <div>
          <label htmlFor="create-user-role" className="block text-xs" style={{ color: "var(--ink-2)" }}>Role</label>
          <select
            id="create-user-role"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="mt-1 block w-full rounded-md px-3 py-2 text-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          >
            {roles.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        {error && (
          <p className="col-span-full text-sm" style={{ color: "var(--bad)" }}>{error}</p>
        )}
        <div className="col-span-full flex gap-2">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md px-4 py-2 text-sm"
            style={{ background: "var(--surface-3)", color: "var(--ink)" }}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
