# Greenwheels Fleet Lease Service

FastAPI service for recording lease events and serving each driver's current
lease projection. PostgreSQL stores the event history and projection;
Prometheus and Grafana provide metrics and dashboards.

## Architecture

![Greenwheels service and observability architecture](docs/images/greenwheels-architecture.svg)

Alertmanager and Slack notifications are optional and require local webhook
configuration. Kafka, ECS, RDS, and Redis are described as future scale-design
options, not as components in the current Compose deployment.

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
<http://localhost:9090>, Grafana at <http://localhost:3000>, and (when enabled)
Alertmanager at <http://localhost:9093>. API startup waits for PostgreSQL and
creates any missing application tables. The API health check becomes healthy
only after PostgreSQL is reachable.

## What to verify in the dashboards and alerts

After the containers are healthy, open Grafana and sign in with the
`GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` values in `.env` (the example
defaults are `admin` and `change_this_local_password`). Open
**Dashboards → Greenwheels → Greenwheels Fleet Lease Service**. The dashboard
refreshes every 30 seconds and initially shows the last hour.

Generate a successful event and read back its lease projection from
PowerShell with `curl.exe`:

```powershell
$eventId = [guid]::NewGuid().ToString()
$event = @{
  event_id = $eventId
  driver_id = "demo-driver"
  event_type = "PAYMENT_MADE"
  amount = "250.00"
  currency = "KES"
} | ConvertTo-Json -Compress

curl.exe -i -X POST http://localhost:8000/leases/events `
  -H "Content-Type: application/json" `
  -d $event

curl.exe -i http://localhost:8000/leases/demo-driver
```

The event request should return `202`; the lookup should show the driver's
current lease projection and one event. To verify duplicate handling, run the
same POST command again with the same `$event` body; it should return
`409 Conflict`. This expected client error increments the duplicate metric; it
is not a server error and should not trigger a 5xx alert.

In the Grafana dashboard, verify that:

- **HTTP request rate** shows the requests you just made by method and route.
- **HTTP request latency (p95)** shows observed API latency.
- **Lease event processing rate** shows processed events and, after the
  duplicate test, a duplicate; failures should remain at zero for this check.
- **HTTP 5xx responses** remains at zero for these successful requests.
- **API readiness** reports `HEALTHY` while the API and PostgreSQL are
  reachable.

Prometheus collects metrics and evaluates alerts at
<http://localhost:9090/alerts>; check <http://localhost:9090/targets> to confirm
the API, blackbox exporter, and health-probe targets are up. The alert rules
cover sustained API and lease-event 5xx/error rates, API and event-ingestion
latency SLOs, API health/readiness, and monitoring-target availability. With a
healthy local stack, these alerts are normally **inactive**—that is the
expected result, not a missing setup. Rules include thresholds and pending
durations, so a single test request will not fire an alert. Consult
`monitoring/prometheus/alerting_rules.yml` for exact conditions. If the
notifications profile is enabled and a Slack webhook is configured, firing
and resolved alerts are also sent to that channel.

Prometheus evaluates the rules in `monitoring/prometheus/alerting_rules.yml`,
including lease-event 5xx rate, the API latency SLO, and an external probe of
`/health` that also checks database readiness. To enable Slack notifications,
create a Slack Incoming Webhook and store its URL in the ignored local secret
file, then start the notifications profile:

```powershell
New-Item -ItemType Directory -Force .secrets
Set-Content -NoNewline .secrets\slack_webhook_url '<your Slack Incoming Webhook URL>'
docker compose --profile notifications up --build -d
```

The webhook is read from `.secrets/slack_webhook_url` by Alertmanager and is
not stored in `.env` or committed to Git. Without this file and profile,
Prometheus still evaluates and displays firing alerts, but Slack delivery is
disabled. Alert definitions include triage actions and links into `RUNBOOK.md`.

Submit an event with `POST /leases/events`, retrieve a driver's projection
with `GET /leases/{driver_id}`, and check API readiness at `/health`.

To follow startup logs:

```powershell
docker compose logs -f api postgres
```

For incident triage steps, see [RUNBOOK.md](./RUNBOOK.md).
For the proposed four-engineer on-call and escalation model, see
[ONCALL.md](./ONCALL.md).
For the scale-exercise design (Kafka, RDS read scaling, caching, lag recovery,
and ECS deployment reliability), see [ARCHITECTURE.md](./ARCHITECTURE.md).

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
