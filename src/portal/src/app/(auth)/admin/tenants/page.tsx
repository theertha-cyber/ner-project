"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/auth-fetch";
import { GATEWAY_URL } from "@/lib/api";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  status: string;
  max_users: number;
  max_documents: number;
  max_storage_gb: number;
  created_at: string;
}

interface TenantsResponse {
  tenants: Tenant[];
  total: number;
  page: number;
  per_page: number;
}

export default function TenantsPage() {
  const [data, setData] = useState<TenantsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    authFetch(`${GATEWAY_URL}/api/v1/admin/tenants?page=${page}&per_page=20`)
      .then((r) => r.json() as Promise<TenantsResponse>)
      .then(setData)
      .catch((err: Error) => alert(err.message))
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div className="animate-fade-up">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Tenants</h1>
        <Link
          href="/admin/tenants/new"
          className="rounded-md bg-brand-primary px-4 py-2 text-sm text-white hover:bg-brand-hover"
        >
          Create Tenant
        </Link>
      </div>

      {loading ? (
        <p style={{ color: "var(--ink-3)" }}>Loading...</p>
      ) : data ? (
        <>
          <div className="overflow-hidden rounded-lg shadow" style={{ background: "var(--surface-2)" }}>
            <table className="min-w-full" style={{ borderCollapse: "collapse" }}>
              <thead style={{ background: "var(--surface-3)" }}>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                    Slug
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                    Users
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                    Created
                  </th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.tenants.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid var(--line)" }} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium" style={{ color: "var(--ink)" }}>
                      {t.name}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm" style={{ color: "var(--ink-3)" }}>{t.slug}</td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${
                          t.status === "active"
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm" style={{ color: "var(--ink-3)" }}>
                      {t.max_users}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm" style={{ color: "var(--ink-3)" }}>
                      {new Date(t.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                      <Link
                        href={`/admin/tenants/${t.id}`}
                        className="text-brand-primary hover:text-brand-hover"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm" style={{ color: "var(--ink-3)" }}>
              Showing {data.tenants.length} of {data.total} tenants
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-md px-3 py-1 text-sm shadow disabled:opacity-50"
                style={{ background: "var(--surface-2)" }}
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * data.per_page >= data.total}
                className="rounded-md px-3 py-1 text-sm shadow disabled:opacity-50"
                style={{ background: "var(--surface-2)" }}
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : (
        <p style={{ color: "var(--ink-3)" }}>No tenants found.</p>
      )}
    </div>
  );
}
