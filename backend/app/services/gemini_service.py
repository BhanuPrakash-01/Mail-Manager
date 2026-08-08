from google import genai

from app.config import settings

from app.schemas.extraction import EmailExtraction

MODEL_NAME = "gemini-3.1-flash-lite"

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

    def extract(self, cleaned_email: str) -> EmailExtraction:
        prompt = EXTRACTION_PROMPT + cleaned_email

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": EmailExtraction,
            },
        )

        return EmailExtraction.model_validate_json(
            response.text
        )