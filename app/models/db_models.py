
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeaseEventDB(Base):
    """
    Database model for immutable lease event history.

    Each event represents a business fact.
    Events are never overwritten.
    """

    __tablename__ = "lease_events"

    # Unique event ID provides database-level duplicate protection.
    event_id: Mapped[UUID] = mapped_column(
        primary_key=True,
    )

    driver_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    currency: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LeaseDB(Base):
    """
    Database model for the current lease state.

    This is a read-optimized projection derived from lease events.
    """

    __tablename__ = "leases"

    driver_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    lease_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ACTIVE",
    )

    payment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UNKNOWN",
    )

    last_payment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_payment_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    last_payment_currency: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
    )

    last_event_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_event_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    events_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
