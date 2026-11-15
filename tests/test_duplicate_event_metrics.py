
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import (
    LEASE_EVENTS_DUPLICATE,
    LEASE_EVENTS_FAILED,
    LEASE_EVENTS_PROCESSED,
    LEASE_EVENTS_RECEIVED,
)


def test_duplicate_event_increments_duplicate_counter_only():
    client = TestClient(app)

    event_id = str(uuid4())

    payload = {
        "event_id": event_id,
        "driver_id": f"duplicate-test-{uuid4().hex}",
        "event_type": "PAYMENT_MADE",
        "amount": "250.00",
        "currency": "KES",
    }

    received_before = LEASE_EVENTS_RECEIVED._value.get()
    processed_before = LEASE_EVENTS_PROCESSED._value.get()
    duplicate_before = LEASE_EVENTS_DUPLICATE._value.get()
    failed_before = LEASE_EVENTS_FAILED._value.get()

    first_response = client.post(
        "/leases/events",
        json=payload,
    )

    second_response = client.post(
        "/leases/events",
        json=payload,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409

    assert LEASE_EVENTS_RECEIVED._value.get() == received_before + 2

    assert LEASE_EVENTS_PROCESSED._value.get() == processed_before + 1

    assert LEASE_EVENTS_DUPLICATE._value.get() == duplicate_before + 1

    assert LEASE_EVENTS_FAILED._value.get() == failed_before
