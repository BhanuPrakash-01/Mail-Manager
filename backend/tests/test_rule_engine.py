from datetime import datetime

from app.schemas.extraction import (
    EmailDirection,
    EmailExtraction,
    EmailIntent,
    OrganizationType,
)
from app.schemas.routing import (
    RoutingDecision,
    TaskPriority,
)
from app.services.rule_engine import RuleEngine


# ================================================================
# Helper
# ================================================================

def route(
    extraction: EmailExtraction,
    received_at: datetime | None = None,
):
    return RuleEngine().route(
        extraction,
        received_at,
    )


# ================================================================
# SKIP RULES
# ================================================================

def test_spam_is_skipped():
    extraction = EmailExtraction(
        intent=EmailIntent.SPAM,
        direction=EmailDirection.INBOUND,
        confidence=0.99,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.SKIP


def test_newsletter_is_skipped():
    extraction = EmailExtraction(
        intent=EmailIntent.NEWSLETTER,
        direction=EmailDirection.INBOUND,
        confidence=0.99,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.SKIP


def test_auto_reply_is_skipped():
    extraction = EmailExtraction(
        intent=EmailIntent.AUTO_REPLY,
        direction=EmailDirection.INBOUND,
        confidence=0.99,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.SKIP


def test_outbound_vendor_email_is_skipped():
    """
    Another company is selling its services to us.

    This must NEVER create a task.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.SPONSORSHIP,
        direction=EmailDirection.OUTBOUND,
        signals=[
            "marketing services",
            "webinar promotion",
            "content marketing",
        ],
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.SKIP


def test_vendor_spam_with_marketing_keywords_is_skipped():
    """
    Important evaluation trap:

    The email contains marketing keywords, but the sender
    is actually selling SEO/marketing services to us.

    It must NOT go to Meera.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.SPONSORSHIP,
        direction=EmailDirection.INBOUND,
        signals=[
            "seo",
            "digital marketing services",
            "content marketing",
            "pr outreach",
            "webinar promotion",
        ],
        confidence=0.90,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.SKIP
    assert result.assignee_id is None
    assert result.category is None


# ================================================================
# TRIAGE
# ================================================================

def test_ambiguous_goes_to_triage():
    extraction = EmailExtraction(
        intent=EmailIntent.AMBIGUOUS,
        direction=EmailDirection.INBOUND,
        confidence=0.42,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_triage"
    assert result.category == "triage"
    assert result.priority == TaskPriority.MEDIUM


# ================================================================
# ENTERPRISE / AARTI
# ================================================================

def test_rfp_routes_to_aarti():
    extraction = EmailExtraction(
        intent=EmailIntent.RFP,
        direction=EmailDirection.INBOUND,
        company_name="Meridian Steel",
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_aarti"
    assert result.category == "enterprise_rfp"
    assert result.priority == TaskPriority.MEDIUM


def test_rfi_routes_to_aarti():
    extraction = EmailExtraction(
        intent=EmailIntent.RFI,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_aarti"
    assert result.category == "enterprise_rfp"


def test_tender_routes_to_aarti():
    extraction = EmailExtraction(
        intent=EmailIntent.TENDER,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_aarti"
    assert result.category == "enterprise_rfp"


def test_psu_tender_routes_to_aarti_even_below_10_lakh():
    """
    Government/PSU override.

    ₹6.5L PSU tender must still go to Aarti.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.TENDER,
        direction=EmailDirection.INBOUND,
        organization_type=OrganizationType.PSU,
        deal_value_inr=650_000,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_aarti"
    assert result.category == "enterprise_rfp"


def test_large_inbound_deal_routes_to_aarti():
    extraction = EmailExtraction(
        intent=EmailIntent.PRODUCT_ENQUIRY,
        direction=EmailDirection.INBOUND,
        deal_value_inr=2_500_000,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_aarti"
    assert result.category == "enterprise_rfp"


def test_exactly_10_lakh_does_not_trigger_enterprise_rule():
    """
    The enterprise rule is > ₹10L.

    Exactly ₹10L belongs to the SMB side.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.PRODUCT_ENQUIRY,
        direction=EmailDirection.INBOUND,
        deal_value_inr=1_000_000,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_rohit"
    assert result.category == "smb_enquiry"


# ================================================================
# SMB / ROHIT
# ================================================================

def test_product_enquiry_goes_to_rohit():
    extraction = EmailExtraction(
        intent=EmailIntent.PRODUCT_ENQUIRY,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_rohit"
    assert result.category == "smb_enquiry"
    assert result.priority == TaskPriority.LOW


def test_demo_request_goes_to_rohit():
    extraction = EmailExtraction(
        intent=EmailIntent.DEMO_REQUEST,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_rohit"
    assert result.category == "smb_enquiry"
    assert result.priority == TaskPriority.LOW


# ================================================================
# MARKETING / MEERA
# ================================================================

def test_sponsorship_goes_to_meera():
    extraction = EmailExtraction(
        intent=EmailIntent.SPONSORSHIP,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_meera"
    assert result.category == "marketing"
    assert result.priority == TaskPriority.MEDIUM


# ================================================================
# ALLIANCES / KARAN
# ================================================================

def test_partnership_goes_to_karan():
    extraction = EmailExtraction(
        intent=EmailIntent.PARTNERSHIP,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_karan"
    assert result.category == "alliances"
    assert result.priority == TaskPriority.MEDIUM


def test_integration_goes_to_karan():
    extraction = EmailExtraction(
        intent=EmailIntent.INTEGRATION,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_karan"
    assert result.category == "alliances"


# ================================================================
# FINANCE / DIVYA
# ================================================================

def test_invoice_goes_to_divya():
    extraction = EmailExtraction(
        intent=EmailIntent.INVOICE,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_divya"
    assert result.category == "finance"
    assert result.priority == TaskPriority.MEDIUM


def test_payment_goes_to_divya():
    extraction = EmailExtraction(
        intent=EmailIntent.PAYMENT,
        direction=EmailDirection.INBOUND,
        confidence=0.95,
    )

    result = route(extraction)

    assert result.assignee_id == "u_divya"
    assert result.category == "finance"


# ================================================================
# PRIORITY
# ================================================================

def test_deadline_tomorrow_is_high_priority():
    extraction = EmailExtraction(
        intent=EmailIntent.RFP,
        direction=EmailDirection.INBOUND,
        due_date=datetime(
            2026,
            8,
            9,
        ).date(),
        confidence=0.95,
    )

    received_at = datetime(
        2026,
        8,
        8,
        10,
        0,
    )

    result = route(
        extraction,
        received_at,
    )

    assert result.priority == TaskPriority.HIGH


def test_deadline_two_days_away_is_high_priority():
    extraction = EmailExtraction(
        intent=EmailIntent.SPONSORSHIP,
        direction=EmailDirection.INBOUND,
        due_date=datetime(
            2026,
            8,
            10,
        ).date(),
        confidence=0.95,
    )

    received_at = datetime(
        2026,
        8,
        8,
        10,
        0,
    )

    result = route(
        extraction,
        received_at,
    )

    assert result.assignee_id == "u_meera"
    assert result.priority == TaskPriority.HIGH


def test_far_deadline_does_not_become_high():
    extraction = EmailExtraction(
        intent=EmailIntent.RFP,
        direction=EmailDirection.INBOUND,
        due_date=datetime(
            2026,
            8,
            19,
        ).date(),
        confidence=0.95,
    )

    received_at = datetime(
        2026,
        8,
        8,
        10,
        0,
    )

    result = route(
        extraction,
        received_at,
    )

    assert result.assignee_id == "u_aarti"
    assert result.priority == TaskPriority.MEDIUM


def test_deadline_overrides_normal_smb_priority():
    """
    Demo normally = LOW.

    But an urgent deadline overrides the owner-specific
    default priority and becomes HIGH.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.DEMO_REQUEST,
        direction=EmailDirection.INBOUND,
        due_date=datetime(
            2026,
            8,
            9,
        ).date(),
        confidence=0.95,
    )

    received_at = datetime(
        2026,
        8,
        8,
        10,
        0,
    )

    result = route(
        extraction,
        received_at,
    )

    assert result.assignee_id == "u_rohit"
    assert result.priority == TaskPriority.HIGH


def test_deadline_overrides_marketing_priority():
    extraction = EmailExtraction(
        intent=EmailIntent.SPONSORSHIP,
        direction=EmailDirection.INBOUND,
        due_date=datetime(
            2026,
            8,
            9,
        ).date(),
        confidence=0.95,
    )

    received_at = datetime(
        2026,
        8,
        8,
        10,
        0,
    )

    result = route(
        extraction,
        received_at,
    )

    assert result.assignee_id == "u_meera"
    assert result.priority == TaskPriority.HIGH


# ================================================================
# FALLBACK
# ================================================================

def test_unknown_intent_goes_to_triage():
    """
    Any valid but unsupported intent must not silently disappear.
    """

    extraction = EmailExtraction(
        intent=EmailIntent.AMBIGUOUS,
        direction=EmailDirection.INBOUND,
        confidence=0.30,
    )

    result = route(extraction)

    assert result.decision == RoutingDecision.CREATE_TASK
    assert result.assignee_id == "u_triage"
    assert result.category == "triage"