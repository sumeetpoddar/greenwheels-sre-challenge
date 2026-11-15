
# Greenwheels Fleet Lease Service — SLI/SLO Definitions

## 1. Purpose

This document defines the Service Level Indicators (SLIs),
Service Level Objectives (SLOs), measurement windows, and
error budgets for the Greenwheels Fleet Lease Service.

The objectives focus on API availability, request latency,
event processing reliability, and event ingestion latency.

## 2. SLO Measurement Window

All SLOs use a rolling 30-day measurement window.

Prometheus collects application metrics from the `/metrics`
endpoint.

Counters and histograms are used to calculate the SLIs.

## 3. API Availability SLO

### Objective

Maintain 99.9% successful API requests over a rolling 30-day window.

### SLI definition

Successful requests divided by eligible API requests.

HTTP 5xx responses are considered failures.

HTTP 4xx responses are excluded because they generally represent
client-side errors or expected business outcomes.

### Target

99.9% successful requests.

### Error budget

0.1% of eligible requests may fail.

### Prometheus metrics

- `http_requests_total`

### Operational response

If the error budget is consumed rapidly:

- Investigate application exceptions.
- Check PostgreSQL connectivity.
- Inspect database connection pool utilization.
- Review recent deployments.
- Consider pausing non-critical deployments.

## 4. API Latency SLO

### Objective

Ensure that 95% of eligible API requests complete within 300 ms.

### SLI definition

Percentage of eligible API requests with latency less than
or equal to 300 milliseconds.

### Target

95% of requests <= 300 ms.

### Error budget

5% of eligible requests may exceed 300 ms.

### Prometheus metrics

- `http_request_duration_seconds`

### Operational response

If latency degrades:

- Inspect p95 and p99 latency.
- Check PostgreSQL query performance.
- Inspect database connection pool exhaustion.
- Check CPU and memory utilization.
- Investigate network and downstream dependencies.

## 5. Event Processing Success SLO

### Objective

Maintain a 99.5% successful lease event processing rate.

### SLI definition

Successfully processed events divided by valid, non-duplicate
event processing attempts.

Formula:

Successful Event Rate =
Processed Events / (Received Events - Duplicate Events) * 100

Duplicate submissions returning HTTP 409 are excluded.

Unexpected processing failures count against the SLO.

### Target

99.5% successful event processing.

### Error budget

0.5% of eligible event processing attempts may fail.

### Prometheus metrics

- `lease_events_received_total`
- `lease_events_processed_total`
- `lease_events_failed_total`
- `lease_events_duplicate_total`

### Operational response

If event processing reliability degrades:

- Inspect application exception logs.
- Check PostgreSQL availability.
- Inspect database connection pool utilization.
- Investigate transaction failures.
- Check duplicate-event handling.

## 6. Event Ingestion Latency SLO

### Objective

Ensure that 95% of valid event ingestion attempts complete
within 500 milliseconds.

### SLI definition

Percentage of event ingestion attempts whose synchronous
persistence and projection-update duration is <= 500 ms.

This measures API-side PostgreSQL processing time.

It does not measure asynchronous Kafka consumer processing
or end-to-end event delivery latency.

### Target

95% of event ingestion attempts complete within 500 ms.

### Error budget

5% of eligible event ingestion attempts may exceed 500 ms.

### Prometheus metrics

- `lease_event_processing_duration_seconds`

### Operational response

If event ingestion latency increases:

- Inspect PostgreSQL query latency.
- Check database connection pool saturation.
- Investigate transaction lock contention.
- Inspect database CPU and storage utilization.
- Review application logs for slow operations.

## 7. Error Budget Policy

The error budget represents the amount of unreliability
permitted by each SLO.

When error-budget consumption accelerates:

1. Investigate the source of reliability degradation.
2. Prioritize reliability fixes over feature development.
3. Pause high-risk production deployments when necessary.
4. Resume normal deployment activity after reliability improves.

Deployment decisions should consider both the remaining
error budget and the severity of active incidents.

## 8. Current Implementation Limitations

- Event persistence is currently synchronous through PostgreSQL.
- Kafka and asynchronous consumer processing are not yet implemented.
- Event ingestion latency is therefore not an end-to-end
  asynchronous processing measurement.
- Prometheus metrics are currently application-process metrics.
  A multi-replica deployment requires correctly aggregated
  metrics across replicas.
- SLO calculations depend on sufficient traffic and valid
  Prometheus observations.

## 9. Review

SLOs should be reviewed periodically using actual production
traffic, incident history, and business requirements.

Targets may be adjusted as the platform scales.
