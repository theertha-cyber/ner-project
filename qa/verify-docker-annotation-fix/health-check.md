# CAP-6 Health Check

- Docker daemon: PASS (`docker info` succeeded).
- Compose dependencies: PostgreSQL and Redis healthy; MinIO healthy; db-init exited 0.
- Portal: `GET http://localhost:3000` → HTTP 200.
- Gateway: `GET http://localhost:8000/health` → HTTP 200, database reachable.
- Annotation service: `GET http://localhost:8005/health` → HTTP 200, `{"status":"ok"}`.
- Result: PASS for deployment reachability.
# CAP-6 Health Checks

- Timestamp: 2026-09-11T09:53:44Z
- Portal `http://localhost:3000`: HTTP 200.
- Gateway `http://localhost:8000/health`: HTTP 200; database reachable.
- Annotation service `http://localhost:8005/health`: HTTP 200.
- Compose services were recreated; database and Redis reported healthy.
