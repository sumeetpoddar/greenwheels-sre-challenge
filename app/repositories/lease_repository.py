
import sqlite3

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db_models import LeaseDB, LeaseEventDB
from app.models.lease import LeaseEvent, LeaseEventType


class DuplicateEventRecordError(Exception):
    """Raised when an event ID already exists in PostgreSQL."""


class LeaseRepository:
    """
    Handles persistent lease event storage and lease projections.

    Event insertion and projection updates are performed
    within a single database transaction.
    """

    def __init__(self, db: Session):
        self.db = db

    def ingest_event(self, event: LeaseEvent) -> dict:
        """
        Persist an event and update the driver's current lease state.

        A PostgreSQL advisory transaction lock serializes
        concurrent updates for the same driver.
        """

        try:
            with self.db.begin():

                # PostgreSQL advisory locks serialize updates per driver.
                if self.db.get_bind().dialect.name == "postgresql":
                    self.db.execute(
                        select(
                            func.pg_advisory_xact_lock(
                                func.hashtextextended(event.driver_id, 0)
                            )
                        )
                    )

                # Convert API event into a database record.
                event_record = LeaseEventDB(
                    event_id=event.event_id,
                    driver_id=event.driver_id,
                    event_type=event.event_type.value,
                    amount=event.amount,
                    currency=event.currency,
                    occurred_at=event.occurred_at,
                )

                self.db.add(event_record)
                self.db.flush()

                # Retrieve all events in chronological order.
                ordered_events = self.db.scalars(
                    select(LeaseEventDB)
                    .where(LeaseEventDB.driver_id == event.driver_id)
                    .order_by(
                        LeaseEventDB.occurred_at,
                        LeaseEventDB.event_id,
                    )
                ).all()

                # Rebuild the current lease projection.
                projection = self._build_projection(ordered_events)

                lease = self.db.get(LeaseDB, event.driver_id)

                if lease is None:
                    lease = LeaseDB(
                        driver_id=event.driver_id,
                        **projection,
                    )
                    self.db.add(lease)
                else:
                    for field, value in projection.items():
                        setattr(lease, field, value)

                self.db.flush()

            return {
                "message": "Lease event accepted successfully",
                "event_id": str(event.event_id),
                "driver_id": event.driver_id,
                "event_type": event.event_type.value,
            }

        except IntegrityError as exc:
            sqlstate = getattr(exc.orig, "sqlstate", None)
            sqlite_error = getattr(exc.orig, "sqlite_errorcode", None)

            if sqlstate == "23505" or sqlite_error in {
                sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
                sqlite3.SQLITE_CONSTRAINT_UNIQUE,
            }:
                raise DuplicateEventRecordError(
                    f"Event {event.event_id} has already been ingested"
                ) from exc

            raise

    def get_lease(self, driver_id: str) -> dict | None:
        """
        Retrieve the current lease projection for a driver.

        The read-only transaction is explicitly ended so that
        a subsequent write operation can start a new transaction
        on the same SQLAlchemy session.
        """

        try:
            lease = self.db.get(LeaseDB, driver_id)

            if lease is None:
                return None

            return {
                "driver_id": lease.driver_id,
                "lease_status": lease.lease_status,
                "payment_status": lease.payment_status,
                "last_payment_at": lease.last_payment_at,
                "last_payment_amount": lease.last_payment_amount,
                "last_payment_currency": lease.last_payment_currency,
                "last_event_at": lease.last_event_at,
                "last_event_type": lease.last_event_type,
                "events_count": lease.events_count,
            }

        finally:
            # End the read-only transaction started by SQLAlchemy autobegin.
            self.db.rollback()

    @staticmethod
    def _build_projection(events: list[LeaseEventDB]) -> dict:
        """
        Reconstruct the current lease state from ordered events.

        Events are treated as immutable business facts.
        The projection is derived from their chronological sequence.
        """

        lease_status = "ACTIVE"
        payment_status = "UNKNOWN"

        last_payment_at = None
        last_payment_amount = None
        last_payment_currency = None

        for event in events:

            if event.event_type == LeaseEventType.PAYMENT_MADE.value:
                payment_status = "CURRENT"
                last_payment_at = event.occurred_at
                last_payment_amount = event.amount
                last_payment_currency = event.currency

            elif event.event_type == LeaseEventType.PAYMENT_MISSED.value:
                payment_status = "OVERDUE"

            elif event.event_type == LeaseEventType.LEASE_PAUSED.value:
                lease_status = "PAUSED"

            elif event.event_type == LeaseEventType.LEASE_RESUMED.value:
                lease_status = "ACTIVE"

        latest_event = events[-1]

        return {
            "lease_status": lease_status,
            "payment_status": payment_status,
            "last_payment_at": last_payment_at,
            "last_payment_amount": last_payment_amount,
            "last_payment_currency": last_payment_currency,
            "last_event_at": latest_event.occurred_at,
            "last_event_type": latest_event.event_type,
            "events_count": len(events),
        }
