
import pytest
from uuid import uuid4

from app.core.database import SessionLocal
from app.models.lease import LeaseEvent, LeaseEventType
from app.repositories.lease_repository import LeaseRepository
from app.services.lease_service import (
    DuplicateEventError,
    LeaseService,
)


@pytest.fixture
def lease_service():
    """Create a database-backed lease service for every test."""

    with SessionLocal() as db:
        repository = LeaseRepository(db)
        service = LeaseService(repository)
        yield service


@pytest.fixture
def driver_id():
    """Generate a unique driver ID to isolate test data."""

    return f"driver-test-{uuid4().hex}"


def test_successful_event_ingestion(lease_service, driver_id):
    event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    result = lease_service.ingest_event(event)

    assert result["message"] == "Lease event accepted successfully"
    assert result["driver_id"] == driver_id
    assert result["event_type"] == "PAYMENT_MADE"

    lease = lease_service.get_lease(driver_id)
    assert lease is not None
    assert lease["payment_status"] == "CURRENT"


def test_duplicate_event_rejected(lease_service, driver_id):
    event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    lease_service.ingest_event(event)

    with pytest.raises(DuplicateEventError):
        lease_service.ingest_event(event)


def test_missed_payment_changes_payment_status(
    lease_service,
    driver_id,
):
    payment_event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.PAYMENT_MADE,
        amount="250.00",
        currency="KES",
    )

    missed_event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.PAYMENT_MISSED,
    )

    lease_service.ingest_event(payment_event)
    lease_service.ingest_event(missed_event)

    lease = lease_service.get_lease(driver_id)

    assert lease["payment_status"] == "OVERDUE"
    assert lease["events_count"] == 2


def test_lease_pause_and_resume(lease_service, driver_id):
    pause_event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.LEASE_PAUSED,
    )

    resume_event = LeaseEvent(
        driver_id=driver_id,
        event_type=LeaseEventType.LEASE_RESUMED,
    )

    lease_service.ingest_event(pause_event)

    paused_lease = lease_service.get_lease(driver_id)
    assert paused_lease["lease_status"] == "PAUSED"

    lease_service.ingest_event(resume_event)

    resumed_lease = lease_service.get_lease(driver_id)
    assert resumed_lease["lease_status"] == "ACTIVE"


def test_unknown_driver_returns_none(lease_service, driver_id):
    result = lease_service.get_lease(driver_id)

    assert result is None
