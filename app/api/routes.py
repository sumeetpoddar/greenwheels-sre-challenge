
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import check_database_connection, get_db
from app.core.logging import logger
from app.models.lease import LeaseEvent
from app.observability.metrics import (
    LEASE_EVENTS_DUPLICATE,
    LEASE_EVENTS_FAILED,
    LEASE_EVENTS_PROCESSED,
    LEASE_EVENTS_RECEIVED,
    LEASE_EVENT_PROCESSING_DURATION,
)
from app.repositories.lease_repository import LeaseRepository
from app.services.lease_service import DuplicateEventError, LeaseService

router = APIRouter()


# --------------------------------------------------
# DEPENDENCY INJECTION
# --------------------------------------------------

def get_lease_service(db: Session = Depends(get_db)) -> LeaseService:
    """Create a request-scoped lease service."""

    repository = LeaseRepository(db)
    return LeaseService(repository)


# --------------------------------------------------
# HEALTH CHECKS
# --------------------------------------------------

def check_liveness() -> bool:
    """Check whether the application process is alive."""

    return True


def check_readiness() -> bool:
    """Check whether the application can access PostgreSQL."""

    return check_database_connection()


@router.get("/health/live")
def liveness_check():
    """Kubernetes liveness probe."""

    live = check_liveness()

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if live
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={"status": "healthy" if live else "unhealthy"},
    )


@router.get("/health/ready")
def readiness_check():
    """Kubernetes readiness probe."""

    ready = check_readiness()

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if ready
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={"status": "ready" if ready else "not_ready"},
    )


@router.get("/health")
def health_check():
    """Combined application health check."""

    live = check_liveness()
    ready = check_readiness()

    healthy = live and ready

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "healthy" if healthy else "unhealthy",
            "checks": {
                "liveness": "healthy" if live else "unhealthy",
                "readiness": "ready" if ready else "not_ready",
            },
        },
    )


# --------------------------------------------------
# LEASE EVENT INGESTION
# --------------------------------------------------

@router.post(
    "/leases/events",
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_lease_event(
    event: LeaseEvent,
    request: Request,
    lease_service: LeaseService = Depends(get_lease_service),
):
    """
    Ingest a lease event and record structured logs and metrics.

    Duplicate events are expected idempotency conflicts.
    Unexpected exceptions are counted as processing failures.
    """

    request_id = getattr(request.state, "request_id", "unknown")
    start_time = time.perf_counter()

    LEASE_EVENTS_RECEIVED.inc()

    try:
        result = lease_service.ingest_event(event)

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        LEASE_EVENTS_PROCESSED.inc()

        logger.info(
            "Lease event processed successfully",
            extra={
                "request_id": request_id,
                "driver_id": event.driver_id,
                "event_type": event.event_type.value,
                "latency_ms": latency_ms,
            },
        )

        return result

    except DuplicateEventError as exc:
        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        LEASE_EVENTS_DUPLICATE.inc()

        logger.warning(
            "Duplicate lease event rejected",
            extra={
                "request_id": request_id,
                "driver_id": event.driver_id,
                "event_type": event.event_type.value,
                "latency_ms": latency_ms,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except Exception:
        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        LEASE_EVENTS_FAILED.inc()

        logger.exception(
            "Lease event processing failed",
            extra={
                "request_id": request_id,
                "driver_id": event.driver_id,
                "event_type": event.event_type.value,
                "latency_ms": latency_ms,
            },
        )

        raise

    finally:
        processing_duration = time.perf_counter() - start_time

        LEASE_EVENT_PROCESSING_DURATION.observe(processing_duration)


# --------------------------------------------------
# LEASE STATUS LOOKUP
# --------------------------------------------------

@router.get("/leases/{driver_id}")
def get_lease_status(
    driver_id: str,
    lease_service: LeaseService = Depends(get_lease_service),
):
    """Retrieve the current lease projection for a driver."""

    lease = lease_service.get_lease(driver_id)

    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lease events found for driver {driver_id}",
        )

    return lease
