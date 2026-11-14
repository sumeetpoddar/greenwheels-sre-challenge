
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.lease import LeaseEvent
from app.services.lease_service import (
    DuplicateEventError,
    LeaseService,
)
from app.observability.metrics import (
    LEASE_EVENTS_RECEIVED,
    LEASE_EVENTS_PROCESSED,
    LEASE_EVENTS_FAILED,
)


router = APIRouter()

# Temporary in-memory service instance.
# This will be replaced with persistent storage later.
lease_service = LeaseService()


# --------------------------------------------------
# HEALTH CHECKS
# --------------------------------------------------

def check_liveness() -> bool:
    """
    Liveness probe.

    Verifies that the application process is alive
    and capable of responding.

    Does not check external dependencies such as
    PostgreSQL or Kafka.
    """
    return True


def check_readiness() -> bool:
    """
    Readiness probe.

    Verifies whether the application is ready
    to accept incoming requests.

    Currently, the application uses in-memory storage,
    so no external dependency check is required.

    PostgreSQL and other required dependency checks
    will be added during infrastructure integration.
    """
    return True


@router.get("/health/live")
def liveness_check():
    """
    Dedicated liveness endpoint.

    Returns HTTP 200 when the application is alive.
    Returns HTTP 503 when the application is unhealthy.
    """

    live = check_liveness()

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if live
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "healthy" if live else "unhealthy"
        },
    )


@router.get("/health/ready")
def readiness_check():
    """
    Dedicated readiness endpoint.

    Returns HTTP 200 when the application can serve traffic.
    Returns HTTP 503 when the application is not ready.
    """

    ready = check_readiness()

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if ready
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ready" if ready else "not_ready"
        },
    )


@router.get("/health")
def health_check():
    """
    Combined health endpoint required by the case study.

    Reports both liveness and readiness status.
    """

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
                "liveness": (
                    "healthy" if live else "unhealthy"
                ),
                "readiness": (
                    "ready" if ready else "not_ready"
                ),
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
def ingest_lease_event(event: LeaseEvent):
    """
    Accept and ingest a lease event.

    Duplicate event IDs are rejected with HTTP 409.
    """

    LEASE_EVENTS_RECEIVED.inc()

    try:
        result = lease_service.ingest_event(event)

        LEASE_EVENTS_PROCESSED.inc()

        return result

    except DuplicateEventError as exc:
        LEASE_EVENTS_FAILED.inc()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# GET CURRENT LEASE STATUS
# --------------------------------------------------

@router.get("/leases/{driver_id}")
def get_lease_status(driver_id: str):
    """
    Retrieve the current lease status for a driver.
    """

    lease = lease_service.get_lease(driver_id)

    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lease events found for driver {driver_id}",
        )

    return lease
