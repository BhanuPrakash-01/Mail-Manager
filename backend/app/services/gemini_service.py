import time

from google import genai

from app.config import settings
from app.schemas.extraction import EmailExtraction


MODEL_NAME = "gemini-3.1-flash-lite"

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


EXTRACTION_PROMPT = """
You are an email understanding component in a sales inbox routing system.

Your job is ONLY to extract facts and intent from the provided email.

Do NOT decide which employee should receive the email.
Do NOT invent missing values.

Rules:

1. Extract the primary intent.
2. Determine whether the message is inbound or outbound.
3. Extract company_name only when it is supported by the email.
4. Extract deal_value_inr only when an explicit or clearly stated monetary
   value is present. Never estimate.
5. Extract due_date only when a deadline is explicitly stated or unambiguously
   expressed.
6. Identify government/PSU/private/NGO status only when supported by evidence.
7. Provide useful intent signals.
8. Set confidence between 0 and 1.
9. If the intent is genuinely unclear, use "ambiguous".
10. Ignore quoted historical replies that are not part of the current message.

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

        last_exception = None

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

            except Exception as exc:
                last_exception = exc

                if attempt == MAX_RETRIES:
                    raise

                delay = INITIAL_BACKOFF_SECONDS * (2 ** attempt)

                time.sleep(delay)

            raise last_exception

    def extract(self, cleaned_email: str) -> EmailExtraction:
        prompt = EXTRACTION_PROMPT + cleaned_email

        response = self._generate_content(prompt)

        return EmailExtraction.model_validate_json(
            response.text
        )