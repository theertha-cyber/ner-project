"""Provision the four demo/showcase tenants over the admin API.

Requires the gateway running and seeded (`python -m src.gateway.seed`) so the
bootstrap System Admin exists. Only creates tenant rows + admin logins;
data-source/data-plane connections are configured by hand in the portal.

Usage:
    python scripts/setup_demo_tenants.py [--base-url http://localhost:8000]
"""
import argparse
import sys

import requests

DEFAULT_BASE_URL = "http://localhost:8000"
SYSADMIN_EMAIL = "admin@nerplatform.io"
SYSADMIN_PASSWORD = "Admin123!"

TENANTS = [
    {
        "name": "Tenant A",
        "slug": "tenant-a",
        "data_plane_mode": "tenant_owned",
        "admin_email": "admin@tenant-a.io",
        "admin_password": "TenantA123!",
    },
    {
        "name": "Tenant B",
        "slug": "tenant-b",
        "data_plane_mode": "tenant_owned",
        "admin_email": "admin@tenant-b.io",
        "admin_password": "TenantB123!",
    },
    {
        "name": "Tenant C",
        "slug": "tenant-c",
        "data_plane_mode": "platform",
        "admin_email": "admin@tenant-c.io",
        "admin_password": "TenantC123!",
    },
    {
        "name": "Tenant D",
        "slug": "tenant-d",
        "data_plane_mode": "tenant_owned",
        "admin_email": "admin@tenant-d.io",
        "admin_password": "TenantD123!",
    },
]


def login(base_url: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": SYSADMIN_EMAIL, "password": SYSADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_tenant(base_url: str, token: str, payload: dict) -> dict:
    resp = requests.post(
        f"{base_url}/api/v1/admin/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    if resp.status_code == 409:
        print(f"  already exists, skipping: {payload['slug']}")
        return {}
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print(f"Logging in as {SYSADMIN_EMAIL} against {args.base_url}")
    token = login(args.base_url)

    for spec in TENANTS:
        print(f"Creating {spec['slug']} (data_plane_mode={spec['data_plane_mode']})")
        result = create_tenant(args.base_url, token, spec)
        if result:
            tenant = result.get("tenant", result)
            print(f"  id={tenant.get('id')} status={tenant.get('status')} "
                  f"data_plane={tenant.get('data_plane')}")

    print()
    print("Done. Admin logins:")
    for spec in TENANTS:
        print(f"  {spec['slug']}: {spec['admin_email']} / {spec['admin_password']}")
    print()
    print("Next: configure each tenant's data source / data plane connections in the portal.")


if __name__ == "__main__":
    sys.exit(main())
