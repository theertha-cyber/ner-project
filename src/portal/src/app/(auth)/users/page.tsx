"use client";

import { useState, useEffect, FormEvent } from "react";
import { authFetch } from "@/lib/auth-fetch";
import { GATEWAY_URL } from "@/lib/api";

interface User {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
}

const ROLES = ["annotator", "business_user", "tenant_admin"] as const;
type Role = (typeof ROLES)[number];

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ email: "", password: "", role: "annotator" as Role });
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<Role>("annotator");

  const fetchUsers = async (role?: string) => {
    setLoading(true);
    const url = role
      ? `${GATEWAY_URL}/api/v1/users?role=${encodeURIComponent(role)}`
      : `${GATEWAY_URL}/api/v1/users`;
    try {
      const r = await authFetch(url);
      const data = (await r.json()) as { users: User[] };
      setUsers(data.users ?? []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers(roleFilter || undefined);
  }, [roleFilter]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      const r = await authFetch(`${GATEWAY_URL}/api/v1/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createForm),
      });
      if (!r.ok) {
        const data = (await r.json()) as { error?: { message?: string } };
        const msg = data.error?.message ?? "Request failed";
        if (r.status === 409) setCreateError(`Email already taken: ${msg}`);
        else if (r.status === 429) setCreateError(`Quota exceeded: ${msg}`);
        else setCreateError(msg);
        return;
      }
      const data = (await r.json()) as { user: User };
      setUsers((prev) => [data.user, ...prev]);
      setCreateForm({ email: "", password: "", role: "annotator" });
      setShowCreate(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setCreating(false);
    }
  };

  const handleRoleUpdate = async (userId: string, newRole: Role) => {
    try {
      const r = await authFetch(`${GATEWAY_URL}/api/v1/users/${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      if (!r.ok) {
        const data = (await r.json()) as { error?: { message?: string } };
        alert(data.error?.message ?? "Update failed");
        return;
      }
      const data = (await r.json()) as { user: User };
      setUsers((prev) => prev.map((u) => (u.id === userId ? data.user : u)));
      setEditingId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Update failed");
    }
  };

  const handleDeactivate = async (userId: string) => {
    if (!confirm("Deactivate this user? They will no longer be able to log in.")) return;
    try {
      const r = await authFetch(`${GATEWAY_URL}/api/v1/users/${userId}`, {
        method: "DELETE",
      });
      if (!r.ok) {
        const data = (await r.json()) as { error?: { message?: string } };
        alert(data.error?.message ?? "Deactivation failed");
        return;
      }
      const data = (await r.json()) as { user: User };
      setUsers((prev) => prev.map((u) => (u.id === userId ? data.user : u)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  return (
    <div className="animate-fade-up">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <button
          onClick={() => { setShowCreate((v) => !v); setCreateError(""); }}
          className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover"
        >
          {showCreate ? "Cancel" : "Create User"}
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-medium text-gray-900">New User</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs text-gray-700">Email</label>
              <input
                type="email"
                required
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-700">Password</label>
              <input
                type="password"
                required
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                placeholder="Min 8 characters"
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-700">Role</label>
              <select
                value={createForm.role}
                onChange={(e) => setCreateForm({ ...createForm, role: e.target.value as Role })}
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            {createError && (
              <p className="col-span-full text-sm text-red-600">{createError}</p>
            )}
            <div className="col-span-full">
              <button
                type="submit"
                disabled={creating}
                className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter by role:</label>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          <option value="">All roles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : users.length === 0 ? (
        <p className="text-gray-500">No users found.</p>
      ) : (
        <div className="overflow-hidden rounded-lg bg-white shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Role</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Created</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">{u.email}</td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {editingId === u.id ? (
                      <div className="flex items-center gap-2">
                        <select
                          value={editRole}
                          onChange={(e) => setEditRole(e.target.value as Role)}
                          className="rounded border px-2 py-1 text-sm"
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                        <button
                          onClick={() => handleRoleUpdate(u.id, editRole)}
                          className="rounded bg-brand-primary px-2 py-1 text-xs text-white hover:bg-brand-hover"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="rounded bg-gray-200 px-2 py-1 text-xs hover:bg-gray-300"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <span
                        className="cursor-pointer hover:text-brand-primary"
                        title="Click to edit role"
                        onClick={() => { setEditingId(u.id); setEditRole(u.role as Role); }}
                      >
                        {u.role}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${
                        u.status === "active"
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {u.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                    {u.status === "active" && editingId !== u.id && (
                      <button
                        onClick={() => handleDeactivate(u.id)}
                        className="text-red-600 hover:text-red-800"
                      >
                        Deactivate
                      </button>
                    )}
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
