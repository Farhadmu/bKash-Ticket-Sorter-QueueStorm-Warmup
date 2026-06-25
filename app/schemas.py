"""Pydantic request and response models for the QueueStorm sort-ticket API.

These mirror the schema in the problem statement exactly.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Channel(str, Enum):
    APP = "app"
    SMS = "sms"
    CALL_CENTER = "call_center"
    MERCHANT_PORTAL = "merchant_portal"


class Locale(str, Enum):
    BN = "bn"
    EN = "en"
    MIXED = "mixed"


class CaseType(str, Enum):
    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    PHISHING = "phishing_or_social_engineering"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Department(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    FRAUD_RISK = "fraud_risk"


class SortTicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=128)
    channel: Optional[Channel] = None
    locale: Optional[Locale] = None
    message: str = Field(..., min_length=1)

    @field_validator("ticket_id")
    @classmethod
    def _strip_ticket_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ticket_id must not be blank")
        return v


class SortTicketResponse(BaseModel):
    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str = Field(..., min_length=1, max_length=600)
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
