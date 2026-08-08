from datetime import date, datetime

from app.schemas.extraction import (
    EmailDirection,
    EmailExtraction,
    EmailIntent,
    OrganizationType,
)
from app.schemas.routing import (
    RoutingDecision,
    RoutingResult,
    TaskPriority,
)


class RuleEngine:
    """
    Deterministic routing engine.

    Gemini extracts information.
    This class makes the final routing decision.

    Important:
    - No Gemini calls happen here.
    - No Task API calls happen here.
    - The output must use only valid Task API categories.
    """

    def route(
        self,
        extraction: EmailExtraction,
        received_at: datetime | None = None,
    ) -> RoutingResult:

        # =========================================================
        # RULE 1 — OUTBOUND / VENDOR PITCH → SKIP
        # =========================================================

        #
        if extraction.direction == EmailDirection.OUTBOUND:
            return RoutingResult(
                decision=RoutingDecision.SKIP,
                reason=(
                    "Outbound/vendor pitch: sender is selling "
                    "a service or solution to the organization"
                ),
            )

        # =========================================================
        # RULE 2 — NON-ACTIONABLE EMAILS → SKIP
        # =========================================================

        if extraction.intent in {
            EmailIntent.SPAM,
            EmailIntent.NEWSLETTER,
            EmailIntent.AUTO_REPLY,
        }:
            return RoutingResult(
                decision=RoutingDecision.SKIP,
                reason=(
                    f"Non-actionable email: "
                    f"{extraction.intent.value}"
                ),
            )

        # =========================================================
        # RULE 3 — VENDOR SPAM SIGNALS → SKIP
        # =========================================================
        if self._is_vendor_spam(extraction):
            return RoutingResult(
                decision=RoutingDecision.SKIP,
                reason=(
                    "Unsolicited vendor spam detected: "
                    "sender is selling services to the organization"
                ),
            )

        # =========================================================
        # RULE 4 — AMBIGUOUS → TRIAGE
        # =========================================================

        if extraction.intent == EmailIntent.AMBIGUOUS:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="triage",
                assignee_id="u_triage",
                priority=TaskPriority.MEDIUM,
                reason=(
                    "Multiple competing intents or insufficient "
                    "information for deterministic routing"
                ),
            )

        # =========================================================
        # RULE 5 — GOVERNMENT / PSU TENDER → AARTI
        # =========================================================

        if (
            extraction.organization_type
            in {
                OrganizationType.GOVERNMENT,
                OrganizationType.PSU,
            }
            and extraction.intent
            in {
                EmailIntent.RFP,
                EmailIntent.RFI,
                EmailIntent.TENDER,
            }
        ):
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="enterprise_rfp",
                assignee_id="u_aarti",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "Government/PSU procurement opportunity "
                    "overrides the monetary threshold and "
                    "routes to enterprise sales"
                ),
            )

        # =========================================================
        # RULE 6 — RFP / RFI / TENDER → AARTI
        # =========================================================

        if extraction.intent in {
            EmailIntent.RFP,
            EmailIntent.RFI,
            EmailIntent.TENDER,
        }:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="enterprise_rfp",
                assignee_id="u_aarti",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "RFP/RFI/tender routed to enterprise sales"
                ),
            )

        # =========================================================
        # RULE 7 — INBOUND DEAL > ₹10L → AARTI
        # =========================================================

        if (
            extraction.direction == EmailDirection.INBOUND
            and extraction.deal_value_inr is not None
            and extraction.deal_value_inr > 1_000_000
        ):
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="enterprise_rfp",
                assignee_id="u_aarti",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "Inbound deal exceeds ₹10,00,000 and "
                    "is therefore routed to enterprise sales"
                ),
            )

        # =========================================================
        # RULE 8 — PRODUCT ENQUIRY / DEMO → ROHIT
        # =========================================================

        if extraction.intent in {
            EmailIntent.PRODUCT_ENQUIRY,
            EmailIntent.DEMO_REQUEST,
        }:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="smb_enquiry",
                assignee_id="u_rohit",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.LOW,
                ),
                reason=(
                    "Product enquiry/demo routed to SMB sales"
                ),
            )

        # =========================================================
        # RULE 9 — SPONSORSHIP → MEERA
        # =========================================================

        if extraction.intent == EmailIntent.SPONSORSHIP:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="marketing",
                assignee_id="u_meera",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "Sponsorship/event opportunity routed "
                    "to marketing"
                ),
            )

        # =========================================================
        # RULE 10 — PARTNERSHIP / INTEGRATION → KARAN
        # =========================================================

        if extraction.intent in {
            EmailIntent.PARTNERSHIP,
            EmailIntent.INTEGRATION,
        }:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="alliances",
                assignee_id="u_karan",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "Partnership/integration opportunity "
                    "routed to alliances"
                ),
            )

        # =========================================================
        # RULE 11 — FINANCE → DIVYA
        # =========================================================

        if extraction.intent in {
            EmailIntent.INVOICE,
            EmailIntent.PAYMENT,
        }:
            return RoutingResult(
                decision=RoutingDecision.CREATE_TASK,
                category="finance",
                assignee_id="u_divya",
                priority=self._get_priority(
                    extraction=extraction,
                    received_at=received_at,
                    default_priority=TaskPriority.MEDIUM,
                ),
                reason=(
                    "Finance-related email routed to finance"
                ),
            )

        # =========================================================
        # RULE 12 — FALLBACK → TRIAGE
        # =========================================================

        return RoutingResult(
            decision=RoutingDecision.CREATE_TASK,
            category="triage",
            assignee_id="u_triage",
            priority=TaskPriority.MEDIUM,
            reason=(
                "No deterministic routing rule matched; "
                "human review is required"
            ),
        )

    # =============================================================
    # Vendor Spam Detection
    # =============================================================

    def _is_vendor_spam(
        self,
        extraction: EmailExtraction,
    ) -> bool:
        """
        Detect unsolicited vendor/service pitches that could be
        incorrectly classified as marketing.

        Example:
            "We help SaaS companies improve SEO."
            "We provide PR outreach."
            "We offer content marketing."
            "Interested in a free audit?"

        These should be SKIPPED.
        """

        if not extraction.signals:
            return False

        vendor_signals = {
            "seo",
            "seo services",
            "digital marketing",
            "digital marketing services",
            "marketing agency",
            "marketing services",
            "content marketing",
            "content marketing services",
            "pr",
            "pr outreach",
            "public relations",
            "webinar promotion",
            "webinar services",
            "lead generation",
            "lead generation services",
            "social media marketing",
            "social media services",
            "web development services",
            "software development services",
            "development services",
            "consulting services",
            "consulting",
            "agency",
            "vendor",
            "vendor services",
            "service provider",
            "outsourcing",
            "outsource",
        }

        normalized_signals = {
            signal.strip().lower()
            for signal in extraction.signals
            if signal
        }

        return bool(
            normalized_signals.intersection(vendor_signals)
        )

    # =============================================================
    # Priority
    # =============================================================

    def _get_priority(
        self,
        extraction: EmailExtraction,
        received_at: datetime | None,
        default_priority: TaskPriority,
    ) -> TaskPriority:
        """
        Deadline within 72 hours overrides the normal priority.

        Our current extraction schema stores due_date as a DATE,
        not a timestamp. Therefore we use calendar-day distance
        conservatively.

        Examples:

            received Aug 8
            due Aug 9 → HIGH

            received Aug 8
            due Aug 10 → HIGH

            received Aug 8
            due Aug 19 → default priority
        """

        if extraction.due_date is None:
            return default_priority

        if received_at is None:
            return default_priority

        received_date: date = received_at.date()

        days_until_due = (
            extraction.due_date - received_date
        ).days

        # With date-only extraction, 0–2 days is safely inside
        # the 72-hour window.
        if 0 <= days_until_due <= 2:
            return TaskPriority.HIGH

        return default_priority