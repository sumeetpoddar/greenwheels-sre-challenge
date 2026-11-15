
from prometheus_client import Counter, Histogram


# --------------------------------------------------
# HTTP REQUEST METRICS
# --------------------------------------------------

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)


HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(
        0.05,
        0.1,
        0.2,
        0.3,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
)


# --------------------------------------------------
# LEASE EVENT METRICS
# --------------------------------------------------

LEASE_EVENTS_RECEIVED = Counter(
    "lease_events_received_total",
    "Total valid lease event ingestion attempts",
)


LEASE_EVENTS_PROCESSED = Counter(
    "lease_events_processed_total",
    "Total lease events successfully persisted and processed",
)


LEASE_EVENTS_FAILED = Counter(
    "lease_events_failed_total",
    "Total lease event processing attempts that failed unexpectedly",
)


LEASE_EVENTS_DUPLICATE = Counter(
    "lease_events_duplicate_total",
    "Total duplicate lease event submissions rejected with HTTP 409",
)


# --------------------------------------------------
# EVENT PROCESSING LATENCY
# --------------------------------------------------

LEASE_EVENT_PROCESSING_DURATION = Histogram(
    "lease_event_processing_duration_seconds",
    "Time taken to persist and process a lease event ingestion attempt",
    buckets=(
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
    ),
)
