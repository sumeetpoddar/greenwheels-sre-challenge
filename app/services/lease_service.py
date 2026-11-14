
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.models.lease import LeaseEvent, LeaseEventType


class DuplicateEventError(Exception):
    """Raised when an event ID has already been ingested."""


class LeaseService:
    """
    Initial in-memory implementation of the lease service.

    Responsibilities:
    1. Ingest lease events.
    2. Prevent duplicate event ingestion.
    3. Calculate current lease status by replaying events.

    Note:
    This implementation is for local development.
    Production storage will use PostgreSQL.
    """

    def __init__(self):
        # Store events grouped by driver ID.
        self.events_by_driver: dict[str, list[LeaseEvent]] = defaultdict(list)

        # Maintain event IDs for duplicate detection.
        self.processed_event_ids: set[UUID] = set()

    def ingest_event(self, event: LeaseEvent) -> dict:
        """
        Accept a lease event after checking for duplicates.
        """

        if event.event_id in self.processed_event_ids:
            raise DuplicateEventError(
                f"Event {event.event_id} has already been ingested"
            )

        self.events_by_driver[event.driver_id].append(event)
        self.processed_event_ids.add(event.event_id)

        return {
            "message": "Lease event accepted successfully",
            "event_id": str(event.event_id),
            "driver_id": event.driver_id,
            "event_type": event.event_type.value,
        }

    def get_lease(self, driver_id: str) -> Optional[dict]:
        """
        Calculate the driver's current lease status
        by replaying historical events.
        """

        events = self.events_by_driver.get(driver_id)

        if not events:
            return None

        # Process events in chronological order.
        ordered_events = sorted(
            events,
            key=lambda event: (event.occurred_at, str(event.event_id)),
        )

        lease_status = "ACTIVE"
        payment_status = "UNKNOWN"

        last_payment_at = None
        last_payment_amount = None
        last_payment_currency = None

        for event in ordered_events:

            if event.event_type == LeaseEventType.PAYMENT_MADE:
                payment_status = "CURRENT"
                last_payment_at = event.occurred_at
                last_payment_amount = event.amount
                last_payment_currency = event.currency

            elif event.event_type == LeaseEventType.PAYMENT_MISSED:
                payment_status = "OVERDUE"

            elif event.event_type == LeaseEventType.LEASE_PAUSED:
                lease_status = "PAUSED"

            elif event.event_type == LeaseEventType.LEASE_RESUMED:
                lease_status = "ACTIVE"

        latest_event = ordered_events[-1]

        return {
            "driver_id": driver_id,
            "lease_status": lease_status,
            "payment_status": payment_status,
            "last_payment_at": last_payment_at,
            "last_payment_amount": last_payment_amount,
            "last_payment_currency": last_payment_currency,
            "last_event_at": latest_event.occurred_at,
            "last_event_type": latest_event.event_type.value,
            "events_count": len(ordered_events),
        }
