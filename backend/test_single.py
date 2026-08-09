import json
import traceback
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.schemas.email import EmailInput
from app.services.email_processor import EmailProcessor
from app.services.gemini_service import GeminiService
from app.services.rule_engine import RuleEngine
from app.services.task_api import TaskAPIClient
from app.services.preprocessor import EmailPreprocessor

def test_one_email():
    with open("../inbox_test_250.json", "r") as f:
        emails = json.load(f)
        
    email_data = emails[0]
    email_input = EmailInput(**email_data)
    
    db = SessionLocal()
    processor = EmailProcessor(
        db=db,
        preprocessor=EmailPreprocessor(),
        gemini_service=GeminiService(),
        rule_engine=RuleEngine(),
        task_api=TaskAPIClient()
    )
    
    print("Processing email:", email_input.email_id)
    try:
        result = processor.process(email_input, "test_candidate_id", run_id="test_run_id")
        print("Result:", result)
        db.commit()
    except Exception as e:
        db.rollback()
        print("Exception during processing:")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_one_email()
