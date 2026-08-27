# NER Platform — Internal Deployment Plan

**Status:** Draft
**Audience:** Infrastructure / IT networking. Assumes solid Linux, Docker, DNS, and VPN knowledge, but no prior familiarity with this application.
**Target URL:** `https://ner.hr.inapp.com`
**Access model:** Reachable only from inside the company network — on LAN, or connected through the corporate VPN client. Nothing exposed to the public internet.

---

## 1. What is being deployed

The NER Platform is an internal document-processing web application. Users upload documents through a browser, the platform extracts named entities from them (names, dates, amounts, and similar tenant-defined types), and users query and review the results.

From an infrastructure point of view it is a **single Docker Compose stack**, roughly a dozen containers, all on one host:

| Group | What it does | Rough count |
|---|---|---|
| Web UI | A Next.js frontend, the only thing end users see | 1 container |
| Backend APIs | Several small HTTP services (FastAPI) behind one gateway: auth, documents, extraction, model serving, training, annotation, analytics, chat | ~8 containers |
| Background workers | Long-running job processors that pick work off a queue (document extraction, model training) | 2 containers |
| Data stores | PostgreSQL (with the pgvector extension), Redis (queue and cache), MinIO (S3-compatible object storage for uploaded files), MLflow (ML experiment tracking) | 4 containers |

Two properties matter for this plan:

1. **It is chatty internally but simple externally.** Those services talk to each other constantly, but a user's browser only ever needs to reach one hostname over HTTPS. Everything else can and should stay invisible.
2. **It calls out to a hosted LLM.** One of the services sends text to OpenAI (or Azure OpenAI) for the chat and search features. That is the only mandatory outbound dependency at runtime, and it drives several decisions below.

There is no production deployment today. The repository contains a development Compose file intended for a single developer's laptop, and that file is not safe to run as-is on a shared host. Section 6 lists exactly what must change.

---

## 2. Target architecture

```
Employee laptop
   |  corporate VPN client, or on-LAN
   v
Company network  (inapp.com)
   |  internal DNS: ner.hr.inapp.com  ->  10.x.y.z
   v
+---------------------------------------------------+
|  VM  (Ubuntu 22.04 LTS)                           |
|                                                   |
|  VPN client  (persistent tunnel, static IP)       |
|  Host firewall: inbound 443 + 22 only             |
|                                                   |
|  +---------------------------------------------+  |
|  |  Reverse proxy (nginx/Caddy) — TLS on 443   |  |
|  +----------------------+----------------------+  |
|                         |                         |
|         private Docker network (no host ports)    |
|                         |                         |
|   web UI  ·  backend APIs  ·  workers             |
|   PostgreSQL  ·  Redis  ·  MinIO  ·  MLflow       |
|                                                   |
|   persistent volumes: database, object storage    |
+---------------------------------------------------+
```

One VM. One published port. The reverse proxy is the single entry point; every other container is reachable only from inside the Docker network.

---

## 3. VM specification

| Item | Sizing | Notes |
|---|---|---|
| OS | Ubuntu Server 22.04 LTS | Any Docker-capable Linux is fine |
| vCPU | 8 | The background workers are the load, not the web traffic |
| RAM | 32 GB | Database, object storage, an in-process ML model cache, and a Node.js frontend all share the host |
| Disk | 300 GB SSD | Grows continuously: uploaded documents, database, ML artifacts, container images |
| GPU | Not required | Model training currently runs on CPU. A GPU is a possible later optimisation, and would need the NVIDIA container toolkit |
| Snapshots | Daily, hypervisor-level | In addition to the logical backups in section 8 |

Base packages: Docker Engine and the Compose plugin, git, the corporate VPN client, a host firewall (`ufw`), `unattended-upgrades`, and `fail2ban` for SSH.

---

## 4. Network and VPN

### 4.1 The tunnel

The VM lives outside the corporate LAN (cloud or lab hypervisor) and joins the company network as a VPN client.

1. **Machine identity.** IT issues a dedicated VPN identity for the VM — a service account or device certificate. Not a personal employee credential, which would tie the service's availability to one person's account lifecycle.
2. **Client.** WireGuard is the preferred choice: small, stateless, native to systemd, and it reconnects cleanly. OpenVPN or strongSwan/IPsec are fine if either is the company standard.
3. **Boot ordering.** The tunnel must come up before the application. Enable the VPN as a systemd unit and order the Docker service after it.
4. **Static internal IP** on the VPN subnet, e.g. `10.20.30.40`. The DNS record points here, so the address must survive reconnects.
5. **Routing — decision needed from IT:**
   - *Split tunnel (recommended).* Only corporate ranges route over the VPN; the VM keeps its own default route for internet egress. The application needs that egress for the hosted LLM, container image pulls, and OS updates.
   - *Full tunnel.* All egress traverses the corporate proxy. Workable, but then the Docker daemon and the containers need proxy environment variables, and the LLM endpoint must be allowlisted on the corporate egress firewall. Without that allowlist, the chat and search features fail.
6. **Watchdog.** A systemd timer that probes an internal host every 60 seconds and restarts the tunnel on failure. If the tunnel drops, the application is simply unreachable — there is no partial degradation to observe.

### 4.2 Host firewall

Default deny inbound. Permit only:

| Port | Source | Purpose |
|---|---|---|
| 443/tcp | corporate ranges, via the VPN interface | HTTPS to the application |
| 80/tcp | corporate ranges | Redirect to 443 only |
| 22/tcp | IT admin subnet or bastion | SSH management |

Everything else stays closed. The development Compose file publishes roughly a dozen additional ports to the host — database, cache, object storage, admin consoles, and every individual API. None of them may be published in production. That is the single most important hardening step in this plan.

### 4.3 Egress

Allowlist outbound to: the OpenAI or Azure OpenAI endpoint, the container registry, OS package mirrors, and NTP. Deny the rest.

---

## 5. DNS and TLS

### 5.1 The record

The company owns `inapp.com` and already operates `hr.inapp.com`. This adds one nested record beneath it.

- **Scope:** internal (split-horizon) DNS only — corporate AD DNS or internal BIND. No record in the public authoritative zone. The name must not resolve from the internet.
- **Record**, depending on how `hr.inapp.com` is delegated:
  - If `hr.inapp.com` is its own delegated zone, add an `ner` A record inside it.
  - If `inapp.com` is one flat zone, add an A record for the full label `ner.hr`.

```
ner.hr.inapp.com.   IN  A   10.20.30.40    ; TTL 300
```

- **TTL:** 300s during rollout, raised to 3600s once stable.
- **Verification:** from a VPN-connected laptop, the name resolves to the internal IP; from an off-VPN machine, it returns NXDOMAIN.
- **Optional:** a second name such as `ner-staging.hr.inapp.com` on the same VM, as a separate proxy virtual host and a separate Compose project, if a pre-production slot is wanted.

### 5.2 Certificate

In preference order:

1. **Internal corporate CA** issues a certificate for `ner.hr.inapp.com`. Corporate machines already trust that CA, so browsers show no warning. This is the clean answer.
2. **Public CA via DNS-01 ACME.** Works without any public inbound path, but requires API access to the DNS provider.
3. **Self-signed.** Browser warnings, and the frontend's own API calls will be blocked by the browser. Acceptable only for the very first smoke test.

Mount the certificate and key read-only into the proxy container. If not automated through ACME, set a renewal reminder about 30 days ahead of expiry.

---

## 6. Reverse proxy and routing

A single nginx or Caddy container is the only process bound to a host port. It terminates TLS and routes by URL path under the one hostname — the browser sees one origin, and the split into multiple backend services stays invisible.

The shape of the routing table:

- `/` → the web UI container.
- `/api/…` → the backend services, one path prefix per service (documents, extraction, models, training, annotation, analytics, chat), with the gateway handling the root of that prefix.
- Admin interfaces (the ML tracking UI, the object-storage console) are internal tools with weak or absent authentication. Leave them unrouted, or restrict them to an admin source-IP allowlist. Do not expose them alongside the app.

Three proxy settings this application specifically needs:

- **Large request bodies** on the document-upload path — users upload real documents; the default 1 MB limit will reject them. Allow around 100 MB.
- **No response buffering and a long read timeout** on the chat path — those responses stream token by token, and a buffering proxy makes the feature appear frozen.
- **Standard security headers**: HSTS, `nosniff`, `X-Frame-Options: DENY`, a referrer policy, and forwarding of the original scheme so the backends generate correct URLs.

The alternative design is one subdomain per service (`api.ner.hr.inapp.com` and so on). Path routing is recommended instead: one DNS record, one certificate, and no cross-origin configuration to maintain.

---

## 7. Application configuration for production

The repository's Compose file targets a developer laptop. The production deployment should be a separate overlay file layered on top of it. The required deltas, in plain terms — exact variable names are in Appendix A.

**a. The frontend's backend URL is compiled in, not read at runtime.**
This is the one item that will silently break the deployment if missed. The Next.js frontend has its backend addresses baked into the image at build time, and the committed defaults point at `localhost`. `localhost` resolves on the *user's own laptop*, so every remote user gets a UI that loads and then fails on every request. The image must be rebuilt with the public hostname. A corollary for the runbook: **changing the hostname later requires rebuilding the frontend image, not just restarting it.**

**b. Every default credential must be replaced.**
The development configuration ships with placeholder or well-known credentials for the database, the object storage admin account, and the token-signing secret. All must be regenerated as unique production values, held in an environment file readable only by the deploy user and excluded from version control. The database password in particular is currently hardcoded across many entries in the Compose file rather than parameterised; that needs fixing before it can be rotated.

**c. Remove the development conveniences.**
Two of the worker containers mount the source tree from the host over the top of the image, so what runs is whatever is on disk rather than what was built. Remove those mounts; a production deploy must be reproducible from an image tag.

**d. Publish no ports except the proxy's,** per section 4.2.

**e. Standard production Compose settings:** restart policies on all long-running services, memory and CPU limits (particularly on the training worker, which can consume a lot), health checks so restarts are meaningful, pinned image tags built from a tagged commit, and log rotation.

**f. Database migrations are already handled.**
The stack includes an initialisation container that applies schema migrations, seeds baseline data, verifies the result, and exits. The other services are already configured to wait for it to finish successfully. Keep that mechanism. Operationally, the rule is: take a database dump before any deploy that includes a migration.

---

## 8. Implementation plan

One sequence, executed in order. Steps 4 and 5 depend on external teams, so raise those requests at the start and continue with the rest while they are in flight.

1. Provision the VM; install Docker and Compose.
2. Install and enable the VPN client as a persistent systemd unit, ordered before Docker. Confirm the static internal IP and reachability of an internal host.
3. Apply firewall rules. Verify from another host on the network that everything except 443 and 22 is closed.
4. Raise the IT request for the `ner.hr.inapp.com` A record on internal DNS, pointing at the VM's static IP.
5. Obtain the TLS certificate for that name from the internal CA.
6. Confirm the name resolves from a VPN-connected laptop, and returns NXDOMAIN from an off-VPN machine.
7. Check out the release tag on the VM; create the production environment file with freshly generated secrets (Appendix B).
8. Write the production Compose overlay: no published ports, no source bind mounts, restart policies, resource limits, health checks, log rotation (section 7).
9. Build the images, including the frontend with the production hostname compiled in (section 7a, Appendix A).
10. Bring the stack up. Watch the initialisation container apply migrations and exit cleanly before trusting anything above it.
11. Configure the reverse proxy — routing table, upload body size, chat streaming settings, security headers — install the certificate, and start it last. Verify the TLS handshake and certificate chain.
12. End-to-end smoke test: log in, upload a document, run an extraction, query the results through chat, open the analytics view.
13. Confirm access from a second machine on the VPN, and confirm failure from off-VPN. Both halves matter.
14. Run one concurrent extraction batch to size worker concurrency before real users arrive.
15. Put backups, monitoring, and the runbook in place per sections 9 and 10, then announce the URL.

---

## 9. Operations

**Backups**
- Nightly database dumps to a mounted company share, 30-day retention.
- Nightly mirror of the object-storage bucket — this holds the users' uploaded source documents and is not reconstructible.
- Weekly VM snapshot.
- Quarterly restore drill on a scratch VM. An untested backup is not a backup.

**Monitoring**
- Uptime check against the application's health endpoint from an internal monitor.
- Alarms on: VPN tunnel state, disk usage (the database and object storage both grow steadily), container restart counts, and background-queue depth. A growing queue is the earliest signal that extraction is wedged.
- Alerts to the team channel or on-call email.

**Updates and rollback**
- Deploy: pull the new tag, rebuild, restart. Brief downtime is acceptable for an internal tool of this kind.
- Rollback: redeploy the previous image tag. If the release contained a migration, restore the pre-deploy dump as well.
- Monthly OS patch window, with unattended security updates in between.

---

## 10. Security notes

- **Network isolation is one control, not the whole answer.** The application still enforces its own authentication and per-tenant data separation. Otherwise, a single compromised laptop on the VPN would reach every tenant's documents.
- **Data leaves the network for the LLM.** Documents processed here may contain HR or personal data, and the chat and search features send text to a hosted LLM. Legal and security must sign off. If they will not, the options are Azure OpenAI under a company tenant with data-residency terms, or running inference entirely locally at some cost to quality.
- **Do not expose the admin UIs.** The ML tracking interface and the object-storage console both display data and neither ships with meaningful authentication.
- Scan container images before deploy; retain access and query logs for whatever period security requires.

---

## 11. Open questions for IT and security

1. Which VPN technology, and which team issues the machine identity for the VM?
2. Split tunnel or full tunnel? If full — what is the egress proxy, and can the LLM endpoint be allowlisted?
3. Is `hr.inapp.com` a delegated zone, and who approves records within it?
4. Is an internal CA available for the certificate, or do we use DNS-01 ACME?
5. Where does the VM live — corporate hypervisor, or cloud with a tunnel back?
6. What data classification applies to the documents this platform will process, and what does that imply for the external LLM calls?
7. What retention is required for uploaded documents and extracted results?

---

## Appendix A — Frontend build variables

For whoever builds the image. These are compile-time build arguments, per section 7a, and the committed defaults point at `localhost`:

```
NEXT_PUBLIC_API_URL=https://ner.hr.inapp.com/api
NEXT_PUBLIC_GATEWAY_URL=https://ner.hr.inapp.com/api
NEXT_PUBLIC_DOCUMENT_URL=https://ner.hr.inapp.com/api/documents
NEXT_PUBLIC_ANNOTATION_URL=https://ner.hr.inapp.com/api/annotation
NEXT_PUBLIC_TRAINING_URL=https://ner.hr.inapp.com/api/training
NEXT_PUBLIC_MODEL_SERVING_URL=https://ner.hr.inapp.com/api/models
NEXT_PUBLIC_EXTRACTION_URL=https://ner.hr.inapp.com/api/extraction
NEXT_PUBLIC_ANALYTICS_URL=https://ner.hr.inapp.com/api/analytics
```

These values must match the proxy routing table in section 6. If a path prefix changes there, it changes here too, and the image is rebuilt.

## Appendix B — Secrets to generate

| Secret | Notes |
|---|---|
| Token-signing key | 32 random bytes, hex encoded. Must differ from any development value |
| Database password | Replaces the development default; currently hardcoded in the Compose file and needs parameterising first |
| Object-storage access key and secret | Replaces the default admin account. The same pair is consumed by the ML tracking service under its own variable names — all four must agree |
| LLM API key | Company-billed account, not a personal key |

Stored in a `0600` environment file owned by the deploy user, excluded from version control, and moved into a secret manager when one is available.
