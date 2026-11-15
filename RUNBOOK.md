# Greenwheels Incident Runbook

This runbook covers lease-event processing backlog and database connection-pool
exhaustion. It distinguishes the current local Compose deployment from
infrastructure that is not currently part of this repository.

## Before you start

- Confirm the affected environment, incident severity, and incident commander.
- Use the approved production access path and least-privilege credentials.
- Do not paste database URLs, passwords, access tokens, or customer data into
  incident tickets or chat.
- Record the time, observed impact, commands/actions taken, and outcome in the
  incident timeline.
- Do not delete, replay, or discard payment events unless the service owner
  approves the action and idempotency/reconciliation safeguards are understood.

For the local Docker Compose deployment, run commands from the repository root
with Docker Desktop running. Production Kubernetes, Kafka, and AWS commands
below are examples: adapt cluster, namespace, topic, consumer-group, and region
names to the deployed environment.

Prometheus alert rules are in `monitoring/prometheus/alerting_rules.yml`.
When the Compose `notifications` profile is enabled, Alertmanager groups
alerts and sends firing/resolved notifications to the configured Slack
Incoming Webhook. Follow the README instructions to create the ignored local
webhook secret file; never commit the webhook URL. If notifications do not
arrive, check the `alertmanager` and `blackbox-exporter` containers, the
Prometheus `Alerts` and `Targets` pages, and Alertmanager's status at
`http://localhost:9093`.

---

## Scenario A — Lease event processing backlog

### Scope and applicability

The current Greenwheels application processes lease events synchronously:
`POST /leases/events` writes to PostgreSQL and updates the lease projection in
the same request. This repository does **not** contain Kafka, a Kafka producer,
or a Kafka consumer. Therefore, Kafka consumer lag cannot currently be
diagnosed from this Compose stack.

Use the **Current Compose deployment** steps below if event requests are slow or
failing. Use the **Kafka deployment** steps only if a separate deployment has
added Kafka and an asynchronous consumer.

### Detection signals

For the current synchronous service, investigate when one or more of these
signals occurs:

- `POST /leases/events` has elevated HTTP 5xx responses or clients report
  accepted events are not reflected in lease lookups.
- The `lease_events_failed_total` counter increases.
- `lease_event_processing_duration_seconds` shows sustained high processing
  latency (the documented objective is that 95% complete within 500 ms).
- The API health endpoint returns 503, or PostgreSQL/API containers are
  unhealthy.
- Event counts or known event IDs do not reconcile between client records,
  `lease_events`, and the lease projection.

For a Kafka-enabled deployment, additionally investigate when consumer-group
lag is increasing over successive observations, oldest-message age is growing,
or the consumer reports repeated processing errors. Set numeric alert
thresholds from normal throughput and the service's recovery objectives; this
repository does not define Kafka lag thresholds or Kafka metrics.

### Immediate triage

1. Acknowledge the incident and establish an incident lead. Confirm the
   affected environment, start time, impacted drivers/events, and whether
   requests are being rejected, timing out, or accepted without visible
   projection changes.
2. Check API health, error rate, processing latency, and recent application
   logs. Check PostgreSQL health and available connections before attributing
   the symptom to event processing.
3. Preserve event IDs and timestamps for a small, approved sample. Avoid
   replaying requests until duplicate handling and the expected response are
   clear; event IDs are intended to prevent duplicate writes.
4. If payment state may be incorrect, notify the lease-service owner and
   payment/business operations contact early. Do not manually edit projection
   rows to make dashboards appear healthy.

### Diagnosis commands

#### Current Compose deployment

```powershell
docker compose ps
curl.exe -i http://localhost:8000/health
curl.exe -s http://localhost:8000/metrics
docker compose logs --since 15m api postgres
```

In the metrics output, inspect `lease_events_failed_total`,
`lease_events_processed_total`, `lease_event_processing_duration_seconds`, and
`http_requests_total`. Compare rates over time rather than relying on a single
counter value.

Check whether PostgreSQL has recent connections and active/blocked queries:

```powershell
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY state ORDER BY state;"'
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pid, state, wait_event_type, wait_event, now() - query_start AS query_age, left(query, 160) AS query FROM pg_stat_activity WHERE datname = current_database() AND state <> ''idle'' ORDER BY query_start;"'
```

Use authorized application/database access to reconcile a reported event ID;
do not include payment details in shared output:

```sql
SELECT event_id, driver_id, event_type, occurred_at
FROM lease_events
WHERE event_id = '<approved-event-id>';

SELECT driver_id, lease_status, payment_status, events_count, last_event_at
FROM leases
WHERE driver_id = '<approved-driver-id>';
```

#### Kafka-enabled deployment only

Run these from an approved Kafka administration environment where the Kafka
CLI is installed and `BOOTSTRAP_SERVERS` and `GROUP_ID` refer to the affected
cluster and consumer group:

```sh
kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP_SERVERS" \
  --group "$GROUP_ID" \
  --describe

kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP_SERVERS" \
  --group "$GROUP_ID" \
  --describe --members --verbose

kafka-topics.sh \
  --bootstrap-server "$BOOTSTRAP_SERVERS" \
  --describe --topic "$TOPIC"
```

Inspect consumer logs and metrics for processing duration, commit failures,
rebalances, retries, poison messages, and database errors. For Kubernetes, for
example:

```sh
kubectl -n "$NAMESPACE" get pods
kubectl -n "$NAMESPACE" logs deploy/"$CONSUMER_DEPLOYMENT" --since=15m
kubectl -n "$NAMESPACE" describe deploy "$CONSUMER_DEPLOYMENT"
```

Compare lag by partition with consumer assignment and partition count. A single
blocked partition, repeated retries on one event, insufficient consumer
capacity, a broker/network issue, or a downstream database slowdown require
different remedies.

### Resolution

#### Current Compose deployment

1. If PostgreSQL is unavailable, follow Scenario B. If the API is unhealthy,
   inspect its logs and database connectivity before restarting anything.
2. If the API is healthy but event writes fail, preserve the failed event IDs
   and investigate transaction/constraint errors. Correct the underlying
   database or application issue, then have the caller retry with the **same**
   event ID according to the client retry policy.
3. If an event exists but the projection is inconsistent, stop repeated
   retries and escalate to the service owner to determine a safe projection
   rebuild/reconciliation procedure. This repository has no dedicated
   production repair command.
4. Restart a service only when evidence points to a transient process problem
   and the service owner agrees. Restarting does not repair bad data or an
   unavailable database:

   ```powershell
   docker compose restart api
   docker compose ps
   curl.exe -i http://localhost:8000/health
   ```

#### Kafka-enabled deployment only

1. Fix the demonstrated bottleneck first (for example, restore the database or
   broker path, resolve a consumer crash, or correct a bad deployment).
2. If consumers are saturated and the downstream database has headroom, scale
   consumers only up to the useful partition parallelism and the database's
   safe connection/query capacity. Monitor lag, processing errors, and
   downstream latency while scaling.
3. For a poison message, follow the approved retry/dead-letter procedure and
   preserve the original event and audit trail. Do not skip or delete payment
   messages as a shortcut.
4. Do not reset consumer offsets or mass-replay a topic without approval from
   the service owner and data/platform on-call. Verify idempotency and
   reconciliation plans first.
5. Confirm lag and oldest-message age are falling, processing succeeds, and
   resulting lease/payment state reconciles before declaring recovery.

### Escalation

- **First:** Greenwheels API/lease-service on-call or service owner.
- **Kafka-enabled deployment:** escalate broker, partition, or consumer-runtime
  issues to the Kafka/data-platform on-call.
- **Database bottleneck:** involve the database on-call/DBA (and AWS/RDS
  platform owner when applicable).
- **Payment-state discrepancy or risk to customer operations:** notify the
  payment/business operations owner and incident commander.
- Escalate to the engineering manager/incident commander if recovery exceeds
  the incident response objective, the affected event set cannot be identified,
  or safe replay/reconciliation is uncertain.

---

## Scenario B — Database connection-pool exhaustion

### Scope and applicability

The application uses a SQLAlchemy connection pool configured by
`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT`. The default maximum
per API process is `pool_size + max_overflow` (5 + 5 = 10 connections), and a
checkout may wait up to the configured timeout (default 30 seconds).
Multiply the per-process maximum by the number of API processes/replicas when
checking database capacity.

The checked-in Compose stack uses a PostgreSQL 16 container, not AWS RDS. Use
the RDS-specific checks only in an environment that actually uses RDS.

### Detection signals

- `GET /health/ready` or `GET /health` returns 503 because PostgreSQL cannot be
  reached.
- `/leases/events` or `/leases/{driver_id}` requests return 500 or time out;
  inspect API logs for SQLAlchemy pool timeout/checkout errors and psycopg
  connection errors.
- PostgreSQL reports too many connections, or active connections approach the
  configured server limit.
- In an RDS deployment, CloudWatch `DatabaseConnections`, CPU, memory, and
  storage/IO indicators show pressure. Check Performance Insights if enabled.
- This repository does not currently export SQLAlchemy pool-checkout metrics;
  use logs, health checks, and database-side connection counts unless
  application-level pool instrumentation has been added.

### Immediate triage

1. Declare/acknowledge the incident and establish an incident lead. Confirm
   which endpoints, API replicas, and customers are affected.
2. Check API health and logs; check database reachability and connection
   counts. Determine whether the issue is connection exhaustion, slow/blocked
   queries, database unavailability, or a network/credential failure.
3. Check recent deploys, traffic changes, number of API workers/replicas, pool
   configuration, long-running transactions, and connection leaks.
4. Do not immediately increase pool sizes or terminate all database sessions.
   Both actions can increase database load or interrupt valid work.
5. If payment ingestion is affected, preserve request/event IDs and inform the
   lease-service owner. Communicate whether writes were rejected or their
   outcome is uncertain; clients should retry using the same event ID.

### Diagnosis commands

#### Current Compose PostgreSQL deployment

Run from the repository root:

```powershell
docker compose ps
curl.exe -i http://localhost:8000/health
docker compose logs --since 15m api postgres
```

Check PostgreSQL connection count by state:

```powershell
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY state ORDER BY state;"'
```

Compare total client connections with the configured server limit and inspect
active/long-running queries:

```powershell
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SHOW max_connections;"'
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pid, usename, application_name, client_addr, state, wait_event_type, wait_event, now() - xact_start AS transaction_age, now() - query_start AS query_age, left(query, 160) AS query FROM pg_stat_activity WHERE datname = current_database() ORDER BY xact_start NULLS LAST;"'
```

The pool's configured upper bound per API process is:

```text
DB_POOL_SIZE + DB_MAX_OVERFLOW
```

Estimate the application's possible connection demand as that value times
the maximum number of API processes/replicas. Include other database clients
and reserve capacity for administration and maintenance. Compose environment
values come from the local `.env`; do not paste them or the database URL into
incident output.

#### AWS RDS deployment only

1. In the AWS console, select the correct account, region, and DB instance.
   Check CloudWatch `DatabaseConnections`, CPU, freeable memory, and storage
   latency/IO for the incident window. Review Performance Insights and RDS
   events if enabled.
2. From an approved host with network access and `psql` installed, connect
   using the deployment's secret manager/injected environment. Do not put a
   password directly in shell history:

   ```sh
   psql "$DATABASE_URL"
   ```

3. Run the PostgreSQL queries above against RDS to distinguish idle sessions,
   active work, long transactions, and blocked queries.
4. Check the deployed API replica/worker count and configured pool maximum
   against the RDS instance's connection capacity. RDS connection limits vary
   by instance and engine configuration; verify the actual limit instead of
   assuming a fixed number.

### Resolution

1. **If a recent deployment caused the issue:** follow the change rollback
   procedure if approved, then check health, 5xx rate, and database connection
   counts.
2. **If slow or blocked queries are consuming connections:** identify the
   owning service/query and coordinate with the DBA/service owner. Resolve the
   blocking workload or query cause; terminate a specific backend only after
   confirming its owner and impact with the DBA.
3. **If application connections are leaked or held too long:** mitigate
   affected API instances one at a time if safe, and escalate for a code fix
   that reliably closes sessions/transactions. A restart is a temporary
   mitigation only; it does not fix a leak.
4. **If legitimate concurrency exceeds the pool:** first confirm database
   headroom and the total possible connections across all replicas and
   processes. With DBA approval, adjust pool/replica settings conservatively;
   never raise each replica's pool independently without recalculating the
   aggregate.
5. **If the database itself has reached capacity:** involve the DBA/platform
   owner to determine a safe capacity change or workload reduction. For RDS,
   follow the approved change process for instance/class or parameter changes.
6. Confirm recovery with healthy readiness, successful lease reads and event
   writes, falling 5xx/timeout rates, and database connection headroom.
   Reconcile any event whose request outcome was uncertain.

For local Compose only, after diagnosing a transient API-process fault, a
controlled API restart is:

```powershell
docker compose restart api
docker compose ps
curl.exe -i http://localhost:8000/health/ready
```

Do not run `docker compose down -v` during an incident; deleting named volumes
can destroy local database data.

### Escalation

- **First:** Greenwheels API/lease-service on-call or service owner.
- **Database connections, locks, or capacity:** database on-call/DBA.
- **RDS networking, instance, or CloudWatch/Performance Insights issues:** AWS
  platform/cloud on-call and the RDS owner.
- **Customer/payment impact or uncertain event outcomes:** incident commander
  and payment/business operations owner.
- Escalate to the engineering manager/incident commander if errors continue
  after the first mitigation, a capacity change is needed, data integrity is
  uncertain, or the database approaches its safe operating limit again.

---

## Recovery and follow-up

Before resolving either incident:

- Verify API liveness/readiness and successful representative lease reads and
  event writes.
- Verify error and latency metrics return to normal and stay stable for the
  agreed observation period.
- Reconcile affected event IDs and lease projections with the service owner.
- Communicate recovery to affected stakeholders and document customer impact.
- Capture a timeline, root cause, contributing factors, and follow-up actions.
- Update alert thresholds, dashboards, capacity assumptions, and this runbook
  when the incident reveals a gap.
