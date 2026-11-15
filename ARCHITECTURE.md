# Greenwheels Scale Exercise — Architecture Design Note

## Status and assumptions

This is a design exercise, not an implementation plan already deployed. The
current Greenwheels service processes lease events synchronously through
PostgreSQL. This repository does not run Kafka, ECS, ElastiCache, or Amazon RDS.
The design below describes how I would evolve it for the assumed scale:

- 500,000 registered drivers across eight countries.
- 50,000 active leases generating daily payment events.
- Peak ingestion of 500 lease events per second during end-of-day processing.
- Degraded RDS read latency during the peak.
- A Kafka consumer group falling behind during an ECS deployment rollout.

The initial design assumes one authoritative write region. If legal or
contractual data-residency requirements require country-local storage, isolate
the data plane by approved residency boundary and route each driver to its
home region; do not treat a cross-region replica as a substitute for residency
controls.

## Proposed event and projection flow

```text
Clients
  │ POST /leases/events (stable event_id)
  ▼
FastAPI API ── durable publish ──► Replicated Kafka topic
                                      │ key = driver_id
                                      ▼
                              Lease projector group
                                      │ DB transaction:
                                      │ event fact + projection
                                      ▼
                               RDS writer endpoint
                                      │
                           ┌──────────┴──────────┐
                           ▼                     ▼
                    Read replicas         Cache invalidation
                           │
                     Read API/cache
```

Return `202 Accepted` only after Kafka has acknowledged the event according to
the durability policy. The response means “durably accepted for processing,”
not “the database projection is already visible.” Return the stable event ID
and document the asynchronous read-after-write behavior. If synchronous
read-after-write is a product requirement, serve that request from the writer
or provide a bounded consistency token/wait mechanism instead of silently
reading a lagging replica.

The event ID is the idempotency key across client retries and consumer
reprocessing. The consumer writes the immutable event fact and updates its
projection in one RDS transaction. Commit the Kafka offset only after that
database transaction commits. This is at-least-once delivery with idempotent
database effects; it avoids claiming a distributed Kafka/RDS exactly-once
transaction that the system does not have.

If product requirements instead require the API to synchronously commit to
the database before acceptance, keep the current database-first behavior and
introduce Kafka through a transactional outbox. The outbox row and business
write must commit atomically, and a relay publishes the outbox afterward. Do
not implement a naive “write database, then publish to Kafka” sequence: a
process failure between the two writes can lose an event from one system.

## 1. Horizontal scaling and partitioning

### Partitioning strategy

- Partition the lease-event topic by **`driver_id`**. All events for one driver
  then go to one partition, preserving their order within that driver's
  lease-state stream while spreading different drivers across partitions.
- Do not partition by event type or timestamp: those choices can split one
  driver's state transitions across partitions or create end-of-day hot
  partitions.
- Use a stable, well-distributed partitioner and monitor per-partition
  throughput. A very large customer or unusually active driver can still make
  one key hot; identify that from partition-level metrics before considering a
  more complex keying scheme that would weaken per-driver ordering.
- As a starting capacity hypothesis, provision **96 partitions** for the
  peak topic. This permits up to 96 active consumer tasks in one group, but is
  not a guaranteed throughput number. Load-test serialized message size,
  broker/network limits, consumer processing time, and RDS write capacity
  before fixing the production count. Kafka partition counts are difficult to
  reduce, so validate the plan before creating the topic.
- If country-specific data residency applies, first route each driver to the
  correct regional cluster, then partition by driver ID inside that region.
  Avoid putting country in the key unless needed for routing; it does not
  improve ordering for a driver beyond `driver_id`.

### Consumer-group design and scaling policy

- Run one named, stable consumer group for the authoritative lease projection
  (for example, `greenwheels-lease-projector-v1`). All replicas in that group
  share partitions; Kafka assigns a partition to at most one active member of
  the group at a time.
- Scale consumer tasks horizontally when sustained incoming rate exceeds
  completed processing rate or oldest-message age is rising. Keep the task
  count at or below useful partition parallelism; additional same-group tasks
  beyond the partition count add no processing capacity.
- Bound consumer concurrency by the RDS writer's safe transaction and
  connection capacity. Scale based on both Kafka lag and database latency/
  connections; do not “solve” lag by overwhelming a degraded writer.
- Keep independent consumers (for example, audit export or analytics) in
  separate groups so they have independent offsets and cannot steal projector
  work.
- Use graceful revocation/assignment handling: stop fetching on partition
  revocation, finish or safely abort in-flight work, commit only completed
  offsets, and resume with idempotent processing after reassignment.

## 2. Database read/write split

First determine whether peak read latency is caused by CPU, I/O, locks, query
plans, cache misses, or connection saturation. Optimize expensive queries and
indexes and verify connection-pool sizing before adding replicas. A read
replica moves eligible reads; it does not increase writer capacity or fix a
write/lock bottleneck.

Introduce an RDS read replica when measurements show read workload is a
material contributor to writer saturation or read latency, and the product can
tolerate measured replication lag. Use the RDS reader endpoint or an explicit
read pool for read-only projection/list/reporting traffic. Keep these
operations on the writer:

- Event inserts, projection updates, idempotency checks, and transactions.
- Reads requiring strong consistency, especially read-after-write.
- Operational or reconciliation queries that must reflect the latest commit.

Monitor replica lag and reader latency. Define a product-approved maximum
staleness. If lag exceeds that limit, route consistency-sensitive requests to
the writer or return a clearly documented retry response; do not silently
serve arbitrarily stale payment state. Use bounded connection pools for each
endpoint and include all replicas/tasks in the total RDS connection budget.
Test failover and reader-endpoint behavior before enabling production
routing.

## 3. Caching strategy

### What and where to cache

- Cache the **derived lease projection** (`lease_status`, `payment_status`,
  last payment summary, and projection version) by `driver_id` in a
  distributed cache such as ElastiCache/Redis. This is read-heavy and
  derivable from the durable event log.
- Consider a short-lived in-process cache only for non-sensitive,
  low-volatility reference/configuration data. Do not rely on per-task local
  caches for lease correctness because ECS tasks do not share them.
- Do not treat cached values as the system of record. Do not cache event
  acceptance, idempotency decisions, or a payment fact in place of its durable
  write.

### Cache pattern and invalidation

Use cache-aside for projection reads: read Redis, and on miss fetch the
appropriate database endpoint and populate the cache with a bounded TTL.
After a consumer commits a new projection to RDS, publish an invalidation or
versioned update. Make cache mutation conditional on projection version so a
delayed older invalidation/update cannot overwrite a newer value. Deliver
invalidation through a transactional outbox or another durable mechanism;
best-effort process-local invalidation alone is not sufficient.

Choose TTL based on the product's maximum tolerated staleness and measured
invalidation reliability, not only on performance. Include a small TTL as a
backstop for lost invalidations. On cache timeout/failure, degrade to the
database with concurrency limits and request coalescing so a cache outage
doesn't create a thundering herd against RDS. For a read-after-write request,
bypass the cache or require a version at least as new as the accepted event.

## 4. Detecting, alerting on, and recovering Kafka lag

### Signals and alerts

Collect consumer-group lag per topic/partition, time-based oldest-message age,
consumer throughput, incoming record rate, processing duration, retry/DLQ
rate, rebalance count, failed commits, and database connection/transaction
latency. Export these to Prometheus or CloudWatch with bounded-cardinality
labels; retain group/topic/partition identity but avoid driver IDs as metric
labels.

Alert on actionable conditions rather than one arbitrary lag number:

- **Warning:** oldest-message age exceeds the end-of-day processing objective
  for 5 minutes, or group lag grows for 10 minutes while arrival rate exceeds
  completion rate.
- **Critical:** estimated time-to-drain exceeds the recovery objective, lag
  threatens the event-retention/replay window, or end-to-end payment-state
  freshness breaches its SLO.
- **Critical independent signals:** consumer group has no active members,
  sustained commit failures, rapidly rising poison-message/DLQ rate, or
  database errors preventing commits.

Set numeric limits from a measured normal peak and the business recovery
objective. Alert notifications should identify topic/group/partition, lag and
oldest age, recent deployment, runbook, and immediate action. Monitor the
monitoring pipeline itself so exporter or telemetry loss is not mistaken for
zero lag.

### Recovery sequence

1. Acknowledge the incident and pause or roll back the deployment if lag began
   during rollout. Check consumer health, rebalances, partition assignment,
   recent error logs, broker health, and RDS writer/readiness.
2. Compare arrival and completion rates and locate whether lag is uniform or
   concentrated on a partition/key. Check database transaction latency,
   connection pool saturation, retries, and poison messages.
3. If RDS is healthy and consumers are CPU-bound, scale tasks up to the
   partition count and within the approved writer-connection/concurrency
   budget. If RDS is degraded, reduce consumer concurrency or pause fetching
   briefly while protecting the database, then fix the database bottleneck.
4. Fix a repeated failing message using a bounded retry and approved
   dead-letter/replay procedure. Preserve the original record and audit trail;
   never skip, delete, or reset offsets for payment facts as an ad hoc
   mitigation.
5. Commit only after the database transaction has committed. Verify
   idempotency on replay and reconcile a sample or the complete affected range
   of event IDs against persisted facts and projections.
6. Confirm lag and oldest-message age are falling, estimate time-to-drain,
   confirm event freshness and database health meet objectives, and only then
   close the incident.

For rollout-specific actions, see the deployment section below. The current
[incident runbook](./RUNBOOK.md#scenario-a--lease-event-processing-backlog)
also distinguishes the existing synchronous service from a future Kafka
deployment.

## 5. Reliable rolling ECS deployment

### Consumer service

- Use an ECS rolling deployment with a minimum healthy percentage of 100% and
  maximum percentage of 200% as an initial policy, subject to cluster and
  database capacity. This starts replacement tasks before removing healthy
  old tasks, while still allowing deployment to stop safely if the cluster is
  constrained.
- Enable the ECS deployment circuit breaker with automatic rollback and
  CloudWatch deployment alarms for API 5xx, health failures, consumer lag/
  oldest age, and RDS pressure. Configure alarms with enough sample traffic
  and evaluation time to avoid rolling back on a single transient datapoint.
- Mark a consumer task healthy only after it can reach required dependencies
  and join the group. On shutdown, stop polling, finish or abort in-flight
  records safely, commit completed work, leave the group cleanly, and exit
  within the ECS stop timeout. Ensure the container handles `SIGTERM`.
- Use a controlled rollout/canary for higher-risk changes and keep the
  previous task definition/image available for rollback. During a lag event,
  stop feature rollouts and prioritize recovery.

### API service and event durability

- Keep API tasks stateless; spread tasks across Availability Zones and use an
  ALB health check against readiness. Configure a startup grace period long
  enough for normal initialization, but keep readiness meaningful.
- Use rolling deployment health percentages that preserve capacity, circuit
  breaker/automatic rollback, and deployment alarms on 5xx, latency, health,
  and database/Kafka availability. Drain ALB connections before task
  termination and handle `SIGTERM` for in-flight requests.
- Make API retries safe with a stable event ID and Kafka idempotent producer.
  Require durable broker acknowledgement with replication across AZs and an
  appropriate minimum in-sync replica policy before returning `202`.
- If using an outbox instead, commit the event/outbox transaction before
  acknowledging the request, and relay idempotently. Never rely on
  fire-and-forget background tasks in an API process for durable event
  delivery.
- For the consumer, database fact/projection commit precedes offset commit;
  replay after a crash is safe because the database enforces event-ID
  idempotency. Configure broker retention to cover the tested maximum outage
  and recovery window, and monitor remaining retention headroom.

Do not use a fixed “health within 10 seconds” gate as the only deployment
signal at this scale. Combine startup/readiness checks with sustained
post-deployment error/latency and lag alarms, while keeping deployment
evaluation fast enough to limit customer impact.

## 6. Cost decisions

1. **Use right-sized Graviton capacity for stateless API and consumer tasks
   where dependencies support ARM64.** Benchmark representative peak traffic
   and memory/CPU headroom first, keep minimum on-demand capacity for
   availability, and use Spot only for interruptible consumer capacity with
   graceful rebalancing and enough on-demand baseline to continue processing.
   Do not put the only copy of a partition's work on interruptible capacity.
2. **Control data-retention and database spend with measured lifecycle tiers
   and workload separation.** Keep the operational Kafka retention window
   long enough for recovery, then archive required historical facts to
   compressed S3 storage with lifecycle policies if compliance allows. Add
   only the read-replica capacity justified by measured read load and lag/SLO
   needs; right-size RDS using load tests and Performance Insights rather than
   scaling down during an incident. Preserve multi-AZ writer resilience,
   backups, recovery tests, and sufficient peak headroom.

Review spend and reliability together: cost reductions must not shrink
replication, recovery retention, backups, or safe peak capacity below tested
requirements.

## Capacity validation before launch

The 500 events/second figure is a peak target, not proof that any fixed
partition or instance count will meet it. Before production rollout:

1. Load-test realistic event sizes, key distribution, duplicate/retry rates,
   and end-of-day burst duration.
2. Measure producer acknowledgement latency, per-partition throughput,
   consumer processing time, RDS write/read latency, replica lag, cache hit
   rate, and recovery time after a consumer outage.
3. Test rolling deployments, task interruptions, broker/AZ failure, RDS
   failover, cache outage, and replay from the oldest supported offset.
4. Confirm the system can process above peak arrival rate long enough to drain
   the measured backlog before Kafka retention is exhausted.
5. Adjust topic partition count, ECS limits, database pools, read-replica
   routing, cache TTL, alarms, and cost forecasts from the results.

## What this design does not claim

This document does not provision AWS resources or implement Kafka, ECS, RDS,
read replicas, Redis, or autoscaling. The existing [SLOs](./SLO.md) describe
the current synchronous service; define and validate end-to-end freshness,
lag, and recovery objectives before using this design as a production
architecture.
