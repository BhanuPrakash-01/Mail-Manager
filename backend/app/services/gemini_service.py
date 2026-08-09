import time

from google import genai

from app.config import settings
from app.schemas.extraction import EmailExtraction


MODEL_NAME = "gemini-3.1-flash-lite"

MAX_RETRIES = 40
INITIAL_BACKOFF_SECONDS = 1.0


EXTRACTION_PROMPT = """
You are an email understanding component in a sales inbox routing system
for a B2B services company. Their sales@ inbox receives RFPs, demo requests,
sponsorship asks, partnership pitches, invoices, and a lot of noise.

Your job is ONLY to extract facts and intent from the provided email.
Do NOT decide which employee should receive the email.
Do NOT invent missing values — null is always better than a guess.

═══════════════════════════════════════════════════════════════
INTENT CLASSIFICATION
═══════════════════════════════════════════════════════════════

Pick the single best intent from:
  rfp, rfi, tender, product_enquiry, demo_request, sponsorship,
  partnership, integration, invoice, payment, newsletter, spam,
  auto_reply, ambiguous

Key distinctions:
- "rfp" / "rfi" / "tender": The sender wants US to submit a proposal or bid.
  Government/PSU procurement notices are tenders.
- "product_enquiry" / "demo_request": The sender wants to learn about or try
  OUR product. Small company, startup, casual inquiry → product_enquiry.
- "sponsorship": The sender invites us to sponsor an event, conference,
  webinar, or summit. Money flows FROM us TO them for branding/keynote.
- "partnership" / "integration": Reseller, channel partner, or tech
  integration proposals. NOT a deal — they want to collaborate, not buy.
- "invoice" / "payment": Bills, POs, payment reminders, GST queries.
- "newsletter": Bulk email with [Unsubscribe] or editorial content.
- "spam": Unsolicited vendor pitches, SEO offers, cold outreach selling
  services TO us.
- "auto_reply": Out-of-office, delivery receipts, vacation responders.
- "ambiguous": Two or more competing intents that cannot be separated,
  OR the email genuinely doesn't fit any category.

═══════════════════════════════════════════════════════════════
DIRECTION OF INTENT  (CRITICAL — most common failure)
═══════════════════════════════════════════════════════════════

- "inbound" = the sender wants something FROM our company (to buy our
  product, request a proposal, ask for a demo, send an invoice for us to
  pay, sponsor an event we'd attend, etc.)
- "outbound" = the sender is SELLING or PITCHING their own services TO us.
  Examples: SEO agencies, marketing agencies, PR outreach, content
  marketing, lead generation, webinar promotion, "free audit" offers.

If someone says "we help SaaS companies with X" or "we offer Y services"
or "interested in a quick call?" and they are NOT a customer — that is
OUTBOUND (vendor pitch / spam). Even if they mention keywords like
"webinar", "PR", "content marketing" — if they are selling TO us, it is
outbound/spam, NOT marketing.

═══════════════════════════════════════════════════════════════
INDIAN CURRENCY PARSING  (deal_value_inr)
═══════════════════════════════════════════════════════════════

Convert to integer INR. MUST BE A PURE INTEGER NUMBER. No commas, no text, no decimals.
Examples:
  "Rs. 25 lakhs" → 2500000
  "₹10,00,000" → 1000000
  "Rs. 6,50,000" → 650000
  "1.2 cr" or "1.2 crore" → 12000000
  "₹4,00,000" → 400000
  "Rs. 1,18,000" → 118000
  "budget approx 1.2 cr" → 12000000

CRITICAL RULE — Invoice/payment amounts are NOT deal values:
  If the intent is "invoice" or "payment", set deal_value_inr = null.
  An invoice amount (₹1,18,000 against PO-88214) is money we OWE,
  not a deal we are winning. Only extract deal_value_inr for actual
  business deals, RFPs, tenders, and product enquiries.

═══════════════════════════════════════════════════════════════
DUE DATE EXTRACTION
═══════════════════════════════════════════════════════════════

Extract due_date ONLY when a specific date or unambiguous relative date
is stated:
  "by 12th August 2026" → "2026-08-12"
  "last date 03-08-2026" → "2026-08-03"
  "tomorrow EOD" → the next calendar day from received_at
  "board review 20th ko hai" → "2026-08-20" (infer month from context)

Do NOT extract due_date for:
  "sometime next week" → null
  "no rush" / "nothing urgent" → null
  "12 days overdue" → null (this is about the past, not a future deadline)
  "Net 30 payment terms" → null (payment terms, not a submission deadline)

═══════════════════════════════════════════════════════════════
COMPANY NAME
═══════════════════════════════════════════════════════════════

Extract company_name aggressively. Look in the email body, signature, and infer from the email domain.
Examples:
  "Meridian Steel invites proposals" → "Meridian Steel"
  "— Ankit Bose, Founder, Railyard Logistics" → "Railyard Logistics"
  "Sender is john@acmecorp.com" → "Acme Corp"
  "Bharat Heavy Electricals Limited invites bids" → "Bharat Heavy Electricals Limited"
  "India SaaS Summit" (event name) → "India SaaS Summit"

Use the domain name (e.g., @infosys.com -> Infosys) if no explicit company name is stated in the text.

═══════════════════════════════════════════════════════════════
ORGANIZATION TYPE
═══════════════════════════════════════════════════════════════

Only set when there is clear evidence:
  "government" — ministries, departments, municipal/state/central government bodies,
    ESIC, government hospitals, armed forces, etc.
  "psu" — BHEL, BSNL, ONGC, SAIL, Indian Oil, NTPC, Coal India, etc.
    Also: any entity whose name includes "Limited" and is a known PSU,
    or whose tender number follows government procurement formats.
  "private" — clearly private companies, startups, LLPs
  "ngo" — non-profit, foundation, trust
  "unknown" — when not determinable

═══════════════════════════════════════════════════════════════
HINGLISH / MIXED LANGUAGE
═══════════════════════════════════════════════════════════════

Emails may mix Hindi and English. Understand naturally:
  "humko aapka product chahiye" → they want our product
  "1.2 cr allocated hai" → deal_value_inr = 12000000
  "board review 20th ko hai" → due_date is the 20th
  "Thoda jaldi" → some urgency but not necessarily high priority
  "Bhai" → informal greeting, ignore

═══════════════════════════════════════════════════════════════
CONFIDENCE
═══════════════════════════════════════════════════════════════

Set confidence between 0.0 and 1.0 based on how clearly the email maps
to a single intent:
  0.85–0.95: Clear, unambiguous intent (clean RFP, obvious spam, etc.)
  0.60–0.80: Mostly clear but some minor ambiguity
  0.40–0.55: Genuinely ambiguous — two competing intents, or unclear
  < 0.40: Very uncertain

If the email has TWO distinct asks for different departments (e.g.,
"evaluate your platform" AND "co-host a webinar"), set intent to
"ambiguous" and confidence to 0.40–0.50.

═══════════════════════════════════════════════════════════════
SIGNALS
═══════════════════════════════════════════════════════════════

Provide 1–5 short signal strings that capture key aspects:
  ["rfp", "government", "deadline_72h"]
  ["demo_request", "startup", "no_urgency"]
  ["seo", "vendor", "cold_outreach"]
  ["invoice", "overdue", "gst_update"]
  ["sponsorship", "event", "hard_deadline"]

For finance emails with urgency markers, include "overdue" or "urgent"
in signals.

═══════════════════════════════════════════════════════════════
QUOTED REPLIES
═══════════════════════════════════════════════════════════════

If the email contains quoted replies (lines starting with ">", or sections
after "On ... wrote:" or "--- Original Message ---"), IGNORE the quoted
text. Only extract from the NEW message content. Do not re-extract
information from the original email in a reply chain.

Email:

"""


class GeminiService:

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

    def _generate_content(self, prompt: str):
        """
        Call Gemini with bounded exponential-backoff retries.

        Retries:
            attempt 1 -> immediate
            attempt 2 -> wait 1s
            attempt 3 -> wait 2s
            attempt 4 -> wait 4s

        The final exception is propagated to EmailProcessor so that the
        processing run can record the failure.
        """

        import random
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": EmailExtraction,
                    },
                )
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt == MAX_RETRIES:
                        raise Exception("Your daily Gemini API quota has expired. Please try again later or upgrade your plan.") from e
                    # For rate limits, we sleep up to 30 seconds + jitter to let the quota reset
                    delay = 30 + random.uniform(1, 5)
                    time.sleep(delay)
                else:
                    # For other transient errors, use standard backoff but only try a few times
                    if attempt >= 3:
                        raise e
                    delay = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    time.sleep(delay)

        raise RuntimeError("Unreachable")

    def extract(self, cleaned_email: str) -> EmailExtraction:
        prompt = EXTRACTION_PROMPT + cleaned_email

        response = self._generate_content(prompt)

        return EmailExtraction.model_validate_json(
            response.text
        )