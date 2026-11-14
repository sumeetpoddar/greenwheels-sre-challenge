
from prometheus_client import Counter, Histogram


# Total HTTP requests received by the API.
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)


# HTTP request latency in seconds.
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0),
)


# Total lease events accepted by the API.
LEASE_EVENTS_RECEIVED = Counter(
    "lease_events_received_total",
    "Total number of lease events received",
)


# Total lease events successfully processed.
LEASE_EVENTS_PROCESSED = Counter(
    "lease_events_processed_total",
    "Total number of lease events successfully processed",
)


# Total lease events that failed processing.
LEASE_EVENTS_FAILED = Counter(
    "lease_events_failed_total",
    "Total number of lease events that failed processing",
)
