"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/auth-fetch";
import { GATEWAY_URL } from "@/lib/api";

interface TenantDetail {
  id: string;
  name: string;
  slug: string;
  status: string;
  max_users: number;
  max_documents: number;
  max_storage_gb: number;
  max_model_versions: number;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export default function TenantDetailPage({ params }: { params: { id: string } }) {
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    max_users: 0,
    max_documents: 0,
    max_storage_gb: 0,
    max_model_versions: 0,
  });
  const router = useRouter();

  useEffect(() => {
    authFetch(`${GATEWAY_URL}/api/v1/admin/tenants/${params.id}`)
      .then((r) => r.json() as Promise<{ tenant: TenantDetail }>)
      .then((data) => {
        setTenant(data.tenant);
        setForm({
          max_users: data.tenant.max_users,
          max_documents: data.tenant.max_documents,
          max_storage_gb: data.tenant.max_storage_gb,
          max_model_versions: data.tenant.max_model_versions,
        });
      })
      .catch((err: Error) => alert(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  const handleUpdate = async () => {
    try {
      const r = await authFetch(`${GATEWAY_URL}/api/v1/admin/tenants/${params.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = (await r.json()) as { tenant: TenantDetail };
      setTenant(data.tenant);
      setEditing(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Update failed");
    }
  };

  const handleDeactivate = async () => {
    if (!confirm("Deactivate this tenant? This will block all tenant-scoped requests.")) return;
    try {
      const r = await authFetch(`${GATEWAY_URL}/api/v1/admin/tenants/${params.id}/deactivate`, {
        method: "POST",
      });
      const data = (await r.json()) as { tenant: TenantDetail };
      setTenant(data.tenant);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!tenant) return <p className="text-gray-500">Tenant not found.</p>;

  return (
    <div>
      <button
        onClick={() => router.push("/admin/tenants")}
        className="mb-4 text-sm text-brand-primary hover:text-brand-hover"
      >
        &larr; Back to Tenants
      </button>

      <div className="rounded-lg bg-white p-6 shadow">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{tenant.name}</h1>
            <p className="text-sm text-gray-500">Slug: {tenant.slug}</p>
          </div>
          <span
            className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${
              tenant.status === "active" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
            }`}
          >
            {tenant.status}
          </span>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-4">
          <div className="rounded-md bg-gray-50 p-4">
            <p className="text-sm text-gray-500">Users</p>
            <p className="text-2xl font-bold">
              {tenant.user_count} / {tenant.max_users}
            </p>
          </div>
          <div className="rounded-md bg-gray-50 p-4">
            <p className="text-sm text-gray-500">Documents</p>
            <p className="text-2xl font-bold">0 / {tenant.max_documents}</p>
          </div>
          <div className="rounded-md bg-gray-50 p-4">
            <p className="text-sm text-gray-500">Storage</p>
            <p className="text-2xl font-bold">0 GB / {tenant.max_storage_gb} GB</p>
          </div>
          <div className="rounded-md bg-gray-50 p-4">
            <p className="text-sm text-gray-500">Model Versions</p>
            <p className="text-2xl font-bold">0 / {tenant.max_model_versions}</p>
          </div>
        </div>

        {editing ? (
          <div className="mb-6 space-y-4 rounded-md border p-4">
            <h3 className="font-medium text-gray-900">Edit Quotas</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700">Max Users</label>
                <input
                  type="number"
                  value={form.max_users}
                  onChange={(e) => setForm({ ...form, max_users: +e.target.value })}
                  className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700">Max Documents</label>
                <input
                  type="number"
                  value={form.max_documents}
                  onChange={(e) => setForm({ ...form, max_documents: +e.target.value })}
                  className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700">Max Storage (GB)</label>
                <input
                  type="number"
                  value={form.max_storage_gb}
                  onChange={(e) => setForm({ ...form, max_storage_gb: +e.target.value })}
                  className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700">Max Model Versions</label>
                <input
                  type="number"
                  value={form.max_model_versions}
                  onChange={(e) => setForm({ ...form, max_model_versions: +e.target.value })}
                  className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleUpdate}
                className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-md bg-gray-200 px-4 py-2 text-sm hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="mb-6 flex gap-3">
            <button
              onClick={() => setEditing(true)}
              className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover"
            >
              Edit Quotas
            </button>
            {tenant.status === "active" && (
              <button
                onClick={handleDeactivate}
                className="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
              >
                Deactivate Tenant
              </button>
            )}
          </div>
        )}

        <div className="text-sm text-gray-500">
          <p>Created: {new Date(tenant.created_at).toLocaleString()}</p>
          <p>Updated: {new Date(tenant.updated_at).toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}
