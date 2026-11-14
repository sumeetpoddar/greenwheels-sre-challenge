
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LeaseEventType(str, Enum):
    PAYMENT_MADE = "PAYMENT_MADE"
    PAYMENT_MISSED = "PAYMENT_MISSED"
    LEASE_PAUSED = "LEASE_PAUSED"
    LEASE_RESUMED = "LEASE_RESUMED"


class LeaseEvent(BaseModel):
    """
    Represents an immutable business fact associated with a driver's lease.

    Each event records something that happened. It does not directly
    overwrite the driver's current lease state.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    event_id: UUID = Field(default_factory=uuid4)
    driver_id: str = Field(min_length=1, max_length=100)
    event_type: LeaseEventType
    amount: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            value = value.upper()
            if not value.isalpha():
                raise ValueError("Currency must contain three letters")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_payment_details(self):
        if self.event_type == LeaseEventType.PAYMENT_MADE:
            if self.amount is None:
                raise ValueError("amount is required for PAYMENT_MADE")
            if self.currency is None:
                raise ValueError("currency is required for PAYMENT_MADE")

        return self
