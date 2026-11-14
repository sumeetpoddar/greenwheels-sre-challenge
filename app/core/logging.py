
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    """
    Format application logs as structured JSON.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception details when an exception is logged.
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom structured fields supplied through `extra`.
        for field in ("request_id", "driver_id", "event_type", "latency_ms"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        return json.dumps(log_entry, default=str)


def configure_logging() -> None:
    """
    Configure application-wide JSON logging to stdout.
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())


logger = logging.getLogger("greenwheels")
