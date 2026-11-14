
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_and_request_id():
    """
    Verify health endpoint and request ID propagation.
    """

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    request_id = response.headers.get("X-Request-ID")

    assert request_id is not None

    # Validate request ID format.
    UUID(request_id)


def test_lease_event_ingestion_and_lookup():
    """
    Verify event ingestion and current lease calculation.
    """

    driver_id = f"driver-{uuid4().hex}"

    payload = {
        "event_id": str(uuid4()),
        "driver_id": driver_id,
        "event_type": "PAYMENT_MADE",
        "amount": "250.00",
        "currency": "KES",
    }

    # Submit a payment event.
    ingest_response = client.post(
        "/leases/events",
        json=payload,
    )

    assert ingest_response.status_code == 202

    assert (
        ingest_response.json()["event_type"]
        == "PAYMENT_MADE"
    )

    # Retrieve the driver's current lease status.
    lease_response = client.get(
        f"/leases/{driver_id}"
    )

    assert lease_response.status_code == 200

    lease = lease_response.json()

    assert lease["driver_id"] == driver_id
    assert lease["lease_status"] == "ACTIVE"
    assert lease["payment_status"] == "CURRENT"
    assert lease["events_count"] == 1


def test_prometheus_metrics_endpoint():
    """
    Verify Prometheus exposes expected HTTP
    and lease event metrics.
    """

    driver_id = f"metrics-driver-{uuid4().hex}"

    payload = {
        "event_id": str(uuid4()),
        "driver_id": driver_id,
        "event_type": "PAYMENT_MADE",
        "amount": "500.00",
        "currency": "KES",
    }

    # Generate application traffic.
    health_response = client.get("/health")

    assert health_response.status_code == 200

    event_response = client.post(
        "/leases/events",
        json=payload,
    )

    assert event_response.status_code == 202

    # Scrape Prometheus metrics.
    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200

    metrics = metrics_response.text

    # Verify HTTP request metrics.
    assert "http_requests_total" in metrics

    assert (
        "http_request_duration_seconds_count"
        in metrics
    )

    # Verify normalized route labels.
    assert 'endpoint="/health"' in metrics

    assert 'endpoint="/leases/events"' in metrics

    assert 'status_code="200"' in metrics

    assert 'status_code="202"' in metrics

    # Verify lease event processing metrics.
    assert "lease_events_received_total" in metrics

    assert "lease_events_processed_total" in metrics

    assert "lease_events_failed_total" in metrics
