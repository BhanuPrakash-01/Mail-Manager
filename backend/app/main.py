from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import engine, get_db
from app.models.base import Base
import app.models
from app.schemas.email import EmailInput
from app.services.preprocessor import EmailPreprocessor
from app.services.gemini_service import GeminiService

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.app_name,
    description="AI-powered sales inbox task routing system",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "service": "sales-inbox-router",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "environment": settings.environment,
    }


@app.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {
        "database": "connected",
    }

@app.post("/api/test-email")
def test_email(email: EmailInput):
    return {
        "email_id": email.email_id,
        "thread_id": email.thread_id,
        "received_at": email.received_at.isoformat(),
        "is_reply": email.is_reply,
    }


@app.post("/api/test-preprocess")
def test_preprocess(email: EmailInput):
    preprocessor = EmailPreprocessor()

    cleaned_text = preprocessor.preprocess(email)

    return {
        "email_id": email.email_id,
        "original_length": len(email.body),
        "cleaned_length": len(cleaned_text),
        "cleaned_body": cleaned_text,
    }

@app.post("/api/test-gemini")
def test_gemini(email: EmailInput):
    preprocessor = EmailPreprocessor()
    gemini = GeminiService()

    cleaned_text = preprocessor.preprocess(email)

    extraction = gemini.extract(cleaned_text)

    return extraction.model_dump(mode="json")