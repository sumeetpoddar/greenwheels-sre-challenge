
from contextlib import asynccontextmanager
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from app.api.routes import router
from app.core.config import settings
from app.core.database import initialize_database
from app.core.logging import configure_logging, logger
from app.observability.metrics import (
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
)


# --------------------------------------------------
# APPLICATION INITIALIZATION
# --------------------------------------------------

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Fleet Lease Service API for Greenwheels",
    lifespan=lifespan,
)


# --------------------------------------------------
# API ROUTE REGISTRATION
# --------------------------------------------------

app.include_router(router)


# --------------------------------------------------
# REQUEST MIDDLEWARE
# --------------------------------------------------

@app.middleware("http")
async def observability_middleware(
    request: Request,
    call_next,
):
    """
    Middleware responsibilities:

    1. Generate a unique request ID.
    2. Measure HTTP request latency.
    3. Record request count and duration metrics.
    4. Log request details in JSON format.
    5. Return request ID in the response header.
    """

    request_id = str(uuid4())

    request.state.request_id = request_id

    start_time = time.perf_counter()

    status_code = 500

    try:
        response = await call_next(request)

        status_code = response.status_code

        response.headers["X-Request-ID"] = request_id

        return response

    except Exception:
        logger.exception(
            "Unhandled request exception",
            extra={
                "request_id": request_id,
                "latency_ms": round(
                    (time.perf_counter() - start_time) * 1000,
                    2,
                ),
            },
        )

        raise

    finally:
        latency_seconds = time.perf_counter() - start_time

        latency_ms = round(latency_seconds * 1000, 2)

        # Use the registered route template rather than the
        # actual URL to prevent high-cardinality metric labels.
        route = request.scope.get("route")

        endpoint = (
            route.path
            if route is not None
            else "unmatched"
        )

        # Do not include Prometheus scrape requests in
        # application HTTP request metrics.
        if endpoint != "/metrics":
            HTTP_REQUESTS.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(latency_seconds)

        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "latency_ms": latency_ms,
            },
        )


# --------------------------------------------------
# PROMETHEUS METRICS ENDPOINT
# --------------------------------------------------

@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """
    Expose application metrics in Prometheus format.

    Prometheus periodically scrapes this endpoint
    to collect application observability data.
    """

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# --------------------------------------------------
# ROOT ENDPOINT
# --------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    """
    Basic application information.
    """

    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }
