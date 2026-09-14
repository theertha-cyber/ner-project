## Environment Ladder
| Environment | Priority | Target | Production? |
| --- | --- | --- | --- |
| dev/local | 1 | docker-compose | No |

## Approval Policy
final-only — the single dev/local environment is gated as the final deployment step.

## Rollout Strategy
recreate — the stack is stopped and replaced in place.

This requires the application to tolerate a brief restart during deployment. No traffic split or router is needed, and rollback is the reverse recreate of the local stack.

## Per-Environment Configuration
### dev/local
- Entry point: localhost / provider-assigned local docker endpoint
- Scale / replica intent: single local stack, one replica per service
- Configuration names: `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `JWT_SECRET`, `OPENAI_API_KEY` if chat generation is enabled locally
- Secret sources: developer-local environment, not committed files

## Access Handoff
- Entry point: localhost / provider-assigned local docker endpoint
- Seeded/demo account: none specified in the baseline; deployer must report if one is created and where it is seeded
- Admin/dashboard surfaces: portal UI and any service health endpoints exposed by the compose stack
- Health endpoint: the service health route(s) used by the stack, if present
- User-facing guide path: none specified in the baseline; deployer must report any generated guide path if one is produced

## Preconditions
- Docker Desktop or equivalent local Docker engine is installed and running.
- Ambient access to the repository checkout and local environment variables is available.
- Any required service credentials come from developer-local environment variables or a secret manager; this pipeline never handles credentials itself.
