from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class EmailIntent(str, Enum):
    RFP = "rfp"
    RFI = "rfi"
    TENDER = "tender"
    PRODUCT_ENQUIRY = "product_enquiry"
    DEMO_REQUEST = "demo_request"
    SPONSORSHIP = "sponsorship"
    PARTNERSHIP = "partnership"
    INTEGRATION = "integration"
    INVOICE = "invoice"
    PAYMENT = "payment"
    NEWSLETTER = "newsletter"
    SPAM = "spam"
    AUTO_REPLY = "auto_reply"
    AMBIGUOUS = "ambiguous"


class EmailDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class OrganizationType(str, Enum):
    GOVERNMENT = "government"
    PSU = "psu"
    PRIVATE = "private"
    NGO = "ngo"
    UNKNOWN = "unknown"


class EmailExtraction(BaseModel):
    intent: EmailIntent
    direction: EmailDirection

    company_name: str | None = None

    deal_value_inr: int | None = Field(
        default=None,
        ge=0,
    )

    due_date: date | None = None

    organization_type: OrganizationType = OrganizationType.UNKNOWN

    signals: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )