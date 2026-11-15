
from app.models.lease import LeaseEvent
from app.repositories.lease_repository import (
    DuplicateEventRecordError,
    LeaseRepository,
)


class DuplicateEventError(Exception):
    """Raised when an event ID has already been ingested."""


class LeaseService:
    """
    Application service for lease event ingestion and retrieval.

    Business operations are delegated to the persistent repository.
    """

    def __init__(self, repository: LeaseRepository):
        self.repository = repository

    def ingest_event(self, event: LeaseEvent) -> dict:
        """Persist a lease event and update its projection."""

        try:
            return self.repository.ingest_event(event)

        except DuplicateEventRecordError as exc:
            raise DuplicateEventError(str(exc)) from exc

    def get_lease(self, driver_id: str) -> dict | None:
        """Retrieve the driver's current lease state."""

        return self.repository.get_lease(driver_id)
