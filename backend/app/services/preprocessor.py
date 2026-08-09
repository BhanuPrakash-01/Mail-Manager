import re

from bs4 import BeautifulSoup

from app.schemas.email import EmailInput


class EmailPreprocessor:

    def clean_html(self, text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")

        return soup.get_text(" ", strip=True)

    def normalize_whitespace(self, text: str) -> str:
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def remove_quoted_replies(self, text: str) -> str:
        patterns = [
            r"\nOn .+?wrote:\n",
            r"\nFrom: .+\nSent: .+\nTo: .+",
            r"\n-{2,}\s*Original Message\s*-{2,}",
            r"\nBegin forwarded message:",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if match:
                text = text[:match.start()]

        lines = text.splitlines()

        cleaned_lines = []

        for line in lines:
            if line.strip().startswith(">"):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def remove_signature(self, text: str) -> str:
        signature_markers = [
            "\nBest regards,",
            "\nRegards,",
            "\nKind regards,",
            "\nThanks & Regards,",
            "\nThanks,",
            "\nWarm regards,",
        ]

        lower_text = text.lower()

        positions = []

        for marker in signature_markers:
            position = lower_text.find(marker.lower())

            if position != -1:
                positions.append(position)

        if positions:
            first_position = min(positions)
            text = text[:first_position]

        return text.strip()

    def preprocess(self, email: EmailInput) -> str:
        text = email.body or ""

        text = self.clean_html(text)
        text = self.remove_quoted_replies(text)
        # text = self.remove_signature(text)  # Disabled to preserve Company Names in signatures
        text = self.normalize_whitespace(text)

        return text