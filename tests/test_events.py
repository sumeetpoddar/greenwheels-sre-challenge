
import pytest

from app.models.lease import LeaseEvent, LeaseEventType
from app.services.lease_service import (
    DuplicateEventError,
    LeaseService,
)


@pytest.fixture
def lease_service():
    """Create a fresh lease service for every test."""
    return LeaseService()


def test_successful_event_ingestion(lease_service):
    event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    result = lease_service.ingest_event(event)

    assert result["message"] == "Lease event accepted successfully"
    assert result["driver_id"] == "driver-101"
    assert result["event_type"] == "PAYMENT_MADE"


def test_duplicate_event_rejected(lease_service):
    event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    lease_service.ingest_event(event)

    with pytest.raises(DuplicateEventError):
        lease_service.ingest_event(event)


def test_missed_payment_changes_payment_status(lease_service):
    payment_event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    missed_event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.PAYMENT_MISSED,
    )

    lease_service.ingest_event(payment_event)
    lease_service.ingest_event(missed_event)

    lease = lease_service.get_lease("driver-101")

    assert lease["payment_status"] == "OVERDUE"


def test_lease_pause_and_resume(lease_service):
    pause_event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.LEASE_PAUSED,
    )

    resume_event = LeaseEvent(
        driver_id="driver-101",
        event_type=LeaseEventType.LEASE_RESUMED,
    )

    lease_service.ingest_event(pause_event)

    paused_lease = lease_service.get_lease("driver-101")
    assert paused_lease["lease_status"] == "PAUSED"

    lease_service.ingest_event(resume_event)

    resumed_lease = lease_service.get_lease("driver-101")
    assert resumed_lease["lease_status"] == "ACTIVE"


def test_unknown_driver_returns_none(lease_service):
    result = lease_service.get_lease("unknown-driver")

    assert result is None
