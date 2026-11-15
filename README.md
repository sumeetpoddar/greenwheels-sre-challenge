# Greenwheels Fleet Lease Service

FastAPI service for recording lease events and serving each driver's current
lease projection. PostgreSQL stores the event history and projection;
Prometheus and Grafana provide metrics and dashboards.

## Run the full stack

Requirements: Docker Desktop with Docker Compose enabled.

If you do not already have a local `.env`, copy the example:

```powershell
Copy-Item .env.example .env
```

Start the services from the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

The API is available at <http://localhost:8000>, Prometheus at
<http://localhost:9090>, and Grafana at <http://localhost:3000>. API startup
waits for PostgreSQL and creates any missing application tables. The API health
check becomes healthy only after PostgreSQL is reachable.

Submit an event with `POST /leases/events`, retrieve a driver's projection
with `GET /leases/{driver_id}`, and check API readiness at `/health`.

To follow startup logs:

```powershell
docker compose logs -f api postgres
```

For incident triage steps, see [RUNBOOK.md](./RUNBOOK.md).

Stop the services without deleting persistent data:

```powershell
docker compose down
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests use an in-memory SQLite database by default and can use PostgreSQL by
setting `DATABASE_URL` in the process environment before running pytest.
