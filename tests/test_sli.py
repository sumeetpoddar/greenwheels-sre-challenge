
from app.observability.metrics import (
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
    LEASE_EVENTS_RECEIVED,
    LEASE_EVENTS_PROCESSED,
    LEASE_EVENTS_FAILED,
)


def test_http_request_counter():
    before = HTTP_REQUESTS.labels(
        method="GET",
        endpoint="/health",
        status_code="200",
    )._value.get()

    HTTP_REQUESTS.labels(
        method="GET",
        endpoint="/health",
        status_code="200",
    ).inc()

    after = HTTP_REQUESTS.labels(
        method="GET",
        endpoint="/health",
        status_code="200",
    )._value.get()

    assert after - before == 1


def test_http_request_duration():
    histogram = HTTP_REQUEST_DURATION.labels(
        method="GET",
        endpoint="/health",
    )

    before = histogram._sum.get()

    histogram.observe(0.25)

    after = histogram._sum.get()

    assert after - before == 0.25


def test_lease_events_received_counter():
    before = LEASE_EVENTS_RECEIVED._value.get()

    LEASE_EVENTS_RECEIVED.inc()

    after = LEASE_EVENTS_RECEIVED._value.get()

    assert after - before == 1


def test_lease_events_processed_counter():
    before = LEASE_EVENTS_PROCESSED._value.get()

    LEASE_EVENTS_PROCESSED.inc()

    after = LEASE_EVENTS_PROCESSED._value.get()

    assert after - before == 1


def test_lease_events_failed_counter():
    before = LEASE_EVENTS_FAILED._value.get()

    LEASE_EVENTS_FAILED.inc()

    after = LEASE_EVENTS_FAILED._value.get()

    assert after - before == 1
