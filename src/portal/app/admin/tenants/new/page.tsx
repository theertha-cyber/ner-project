"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function NewTenantPage() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [maxUsers, setMaxUsers] = useState(10);
  const [maxDocuments, setMaxDocuments] = useState(1000);
  const [maxStorageGb, setMaxStorageGb] = useState(5);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiFetch<{ tenant: { id: string } }>("/api/v1/admin/tenants", {
        method: "POST",
        body: {
          name,
          slug: slug || undefined,
          max_users: maxUsers,
          max_documents: maxDocuments,
          max_storage_gb: maxStorageGb,
        },
      });
      router.push(`/admin/tenants/${data.tenant.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <button onClick={() => router.push("/admin/tenants")} className="mb-4 text-sm text-blue-600 hover:text-blue-900">
        &larr; Back to Tenants
      </button>

      <div className="rounded-lg bg-white p-6 shadow">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">Create Tenant</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name *</label>
            <input
              type="text" required value={name}
              onChange={(e) => { setName(e.target.value); if (!slug) setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 63)); }}
              className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Slug</label>
            <input
              type="text" value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 63))}
              className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">Auto-generated from name. Used in tenant URL.</p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Max Users</label>
              <input type="number" value={maxUsers} min={1} onChange={(e) => setMaxUsers(+e.target.value)}
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Max Documents</label>
              <input type="number" value={maxDocuments} min={1} onChange={(e) => setMaxDocuments(+e.target.value)}
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Max Storage (GB)</label>
              <input type="number" value={maxStorageGb} min={1} onChange={(e) => setMaxStorageGb(+e.target.value)}
                className="mt-1 block w-full rounded-md border px-3 py-2 text-sm" />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
            {loading ? "Creating..." : "Create Tenant"}
          </button>
        </form>
      </div>
    </div>
  );
}
