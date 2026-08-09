"""
Chat service – uses Gemini Function Calling to answer natural-language
questions about processed email data.  No raw SQL generation.

Functions are pre-defined, typed, and safe.  Gemini picks which one(s)
to call based on the user's question, then phrases the answer.
"""

import json
import traceback
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.db.session import SessionLocal
from sqlalchemy import text


MODEL_NAME = "gemini-3.1-flash-lite"

# ──────────────────────────────────────────────
#  Query functions — the only DB access the chat has
# ──────────────────────────────────────────────

def _db_rows(sql: str, params: dict | None = None) -> list[dict]:
    with SessionLocal() as db:
        result = db.execute(text(sql), params or {})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def count_by_category() -> dict:
    """Count processed emails grouped by routing category."""
    rows = _db_rows("""
        SELECT category, COUNT(*) as count
        FROM email_processing
        WHERE decision IN ('create_task', 'update_task')
        GROUP BY category
        ORDER BY count DESC
    """)
    return {"categories": {r["category"]: r["count"] for r in rows}}


def count_by_priority() -> dict:
    """Count processed emails grouped by priority level."""
    rows = _db_rows("""
        SELECT priority, COUNT(*) as count
        FROM email_processing
        WHERE decision IN ('create_task', 'update_task')
        GROUP BY priority
        ORDER BY count DESC
    """)
    return {"priorities": {r["priority"]: r["count"] for r in rows}}


def count_by_assignee() -> dict:
    """Count processed emails grouped by assignee."""
    NAMES = {
        "u_aarti": "Aarti Menon (Enterprise Sales)",
        "u_rohit": "Rohit Sharma (SMB Sales)",
        "u_meera": "Meera Iyer (Marketing)",
        "u_karan": "Karan Doshi (Alliances)",
        "u_divya": "Divya Rao (Finance)",
        "u_triage": "Triage Queue",
    }
    rows = _db_rows("""
        SELECT assignee_id, COUNT(*) as count
        FROM email_processing
        WHERE decision IN ('create_task', 'update_task')
        GROUP BY assignee_id
        ORDER BY count DESC
    """)
    return {
        "assignees": {
            NAMES.get(r["assignee_id"], r["assignee_id"]): r["count"]
            for r in rows
        }
    }


def count_by_decision() -> dict:
    """Count all emails grouped by routing decision (create_task, update_task, skip, processing_error)."""
    rows = _db_rows("""
        SELECT decision, COUNT(*) as count
        FROM email_processing
        GROUP BY decision
        ORDER BY count DESC
    """)
    return {"decisions": {r["decision"]: r["count"] for r in rows}}


def get_overall_stats() -> dict:
    """Get aggregate processing statistics: total processed, created, updated, skipped, errors."""
    rows = _db_rows("""
        SELECT
            COUNT(*) as total_processed,
            COUNT(*) FILTER (WHERE decision = 'create_task') as created,
            COUNT(*) FILTER (WHERE decision = 'update_task') as updated,
            COUNT(*) FILTER (WHERE decision = 'skip') as skipped,
            COUNT(*) FILTER (WHERE decision = 'processing_error') as errors
        FROM email_processing
    """)
    return rows[0] if rows else {}


def get_skipped_emails() -> dict:
    """List all skipped/ignored emails with reasons — auto-replies, newsletters, spam."""
    rows = _db_rows("""
        SELECT ep.email_id, e.subject, e.from_name, e.from_email, ep.reasoning, e.body
        FROM email_processing ep
        LEFT JOIN emails e ON e.email_id = ep.email_id
        WHERE ep.decision = 'skip'
        ORDER BY ep.processed_at DESC
    """)
    return {"skipped_count": len(rows), "skipped_emails": rows}


def get_triage_tasks() -> dict:
    """List all tasks assigned to triage (u_triage) with reasoning/descriptions."""
    rows = _db_rows("""
        SELECT ep.email_id, ep.task_id, e.subject, e.from_name, ep.company_name,
               ep.confidence, ep.reasoning, ep.priority, e.body
        FROM email_processing ep
        LEFT JOIN emails e ON e.email_id = ep.email_id
        WHERE ep.assignee_id = 'u_triage'
          AND ep.decision IN ('create_task', 'update_task')
        ORDER BY ep.confidence ASC
    """)
    return {"triage_count": len(rows), "triage_tasks": rows}


def get_high_priority_low_confidence() -> dict:
    """List tasks that are high priority but have low confidence (< 0.6)."""
    rows = _db_rows("""
        SELECT ep.email_id, ep.task_id, e.subject, ep.assignee_id,
               ep.priority, ep.confidence, ep.company_name, ep.reasoning, e.body
        FROM email_processing ep
        LEFT JOIN emails e ON e.email_id = ep.email_id
        WHERE ep.priority = 'high'
          AND ep.confidence < 0.6
          AND ep.decision IN ('create_task', 'update_task')
        ORDER BY ep.confidence ASC
    """)
    return {"matches": rows, "count": len(rows)}


def get_total_deal_value() -> dict:
    """Sum deal_value_inr across all open RFP/enterprise tasks, noting how many had no stated value."""
    rows = _db_rows("""
        SELECT
            COALESCE(SUM(deal_value_inr), 0) as total_deal_value_inr,
            COUNT(*) FILTER (WHERE deal_value_inr IS NOT NULL) as with_value,
            COUNT(*) FILTER (WHERE deal_value_inr IS NULL) as rfps_with_no_stated_value
        FROM email_processing
        WHERE category = 'enterprise_rfp'
          AND decision IN ('create_task', 'update_task')
    """)
    return rows[0] if rows else {}


def get_threads_updated_multiple_times() -> dict:
    """Find threads that were updated more than once (multiple emails in the same thread)."""
    rows = _db_rows("""
        SELECT e.thread_id, COUNT(*) as email_count
        FROM email_processing ep
        JOIN emails e ON e.email_id = ep.email_id
        GROUP BY e.thread_id
        HAVING COUNT(*) > 1
        ORDER BY email_count DESC
    """)
    return {"threads_updated_multiple_times": [r["thread_id"] for r in rows], "count": len(rows)}


def get_spurious_rate() -> dict:
    """Compute spurious rate: (processing_errors / total_processed)."""
    rows = _db_rows("""
        SELECT
            COUNT(*) as total_processed,
            COUNT(*) FILTER (WHERE decision = 'processing_error') as spurious_count
        FROM email_processing
    """)
    if rows and rows[0]["total_processed"] > 0:
        rate = round(rows[0]["spurious_count"] / rows[0]["total_processed"], 4)
        return {**rows[0], "spurious_rate": rate}
    return {"total_processed": 0, "spurious_count": 0, "spurious_rate": 0}


def search_tasks_by_field(field: str, value: str) -> dict:
    """Search/filter tasks by a specific field. Supported fields: category, assignee_id, priority, company_name, decision."""
    SAFE_FIELDS = {"category", "assignee_id", "priority", "company_name", "decision"}
    if field not in SAFE_FIELDS:
        return {"error": f"Cannot filter by '{field}'. Supported: {', '.join(sorted(SAFE_FIELDS))}"}

    rows = _db_rows(f"""
        SELECT ep.email_id, ep.task_id, e.subject, ep.category,
               ep.assignee_id, ep.priority, ep.confidence, ep.company_name,
               ep.deal_value_inr, ep.reasoning, e.body
        FROM email_processing ep
        LEFT JOIN emails e ON e.email_id = ep.email_id
        WHERE LOWER(ep.{field}) = LOWER(:value)
          AND ep.decision IN ('create_task', 'update_task')
        ORDER BY ep.processed_at DESC
    """, {"value": value})
    return {"count": len(rows), "tasks": rows}


def count_emails_by_keyword_in_reasoning(keyword: str) -> dict:
    """Count emails whose reasoning/description mentions a specific keyword (case-insensitive)."""
    rows = _db_rows("""
        SELECT COUNT(*) as count
        FROM email_processing
        WHERE LOWER(reasoning) LIKE LOWER(:pattern)
    """, {"pattern": f"%{keyword}%"})
    return {"keyword": keyword, "count": rows[0]["count"] if rows else 0}


def get_marketing_vs_spam() -> dict:
    """Compare properly routed marketing emails vs skipped spam that used marketing-like keywords."""
    marketing = _db_rows("""
        SELECT COUNT(*) as count
        FROM email_processing
        WHERE category = 'marketing'
          AND decision IN ('create_task', 'update_task')
    """)
    spam = _db_rows("""
        SELECT COUNT(*) as count
        FROM email_processing
        WHERE decision = 'skip'
          AND (LOWER(reasoning) LIKE '%spam%'
               OR LOWER(reasoning) LIKE '%vendor%'
               OR LOWER(reasoning) LIKE '%unsolicited%'
               OR LOWER(reasoning) LIKE '%marketing%'
               OR LOWER(reasoning) LIKE '%seo%')
    """)
    return {
        "marketing": marketing[0]["count"] if marketing else 0,
        "skipped_marketing_lookalike_spam": spam[0]["count"] if spam else 0,
    }


# ──────────────────────────────────────────────
#  Function registry for Gemini
# ──────────────────────────────────────────────

FUNCTION_MAP = {
    "count_by_category": count_by_category,
    "count_by_priority": count_by_priority,
    "count_by_assignee": count_by_assignee,
    "count_by_decision": count_by_decision,
    "get_overall_stats": get_overall_stats,
    "get_skipped_emails": get_skipped_emails,
    "get_triage_tasks": get_triage_tasks,
    "get_high_priority_low_confidence": get_high_priority_low_confidence,
    "get_total_deal_value": get_total_deal_value,
    "get_threads_updated_multiple_times": get_threads_updated_multiple_times,
    "get_spurious_rate": get_spurious_rate,
    "search_tasks_by_field": search_tasks_by_field,
    "count_emails_by_keyword_in_reasoning": count_emails_by_keyword_in_reasoning,
    "get_marketing_vs_spam": get_marketing_vs_spam,
}


TOOL_DECLARATIONS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="count_by_category",
            description="Count processed emails grouped by routing category (enterprise_rfp, smb_enquiry, marketing, alliances, finance, triage).",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="count_by_priority",
            description="Count processed emails grouped by priority level (high, medium, low).",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="count_by_assignee",
            description="Count processed emails grouped by assignee (team member).",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="count_by_decision",
            description="Count all emails grouped by routing decision (create_task, update_task, skip, processing_error).",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_overall_stats",
            description="Get aggregate processing statistics: total processed, created, updated, skipped, errors.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_skipped_emails",
            description="List all skipped/ignored emails (auto-replies, newsletters, spam) with reasons.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_triage_tasks",
            description="List all tasks assigned to triage queue with reasoning and confidence scores.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_high_priority_low_confidence",
            description="List tasks that are high priority but have low confidence (< 0.6) — 'unassigned-feeling' tasks.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_total_deal_value",
            description="Sum deal_value_inr across all enterprise RFP tasks, noting how many had no stated value.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_threads_updated_multiple_times",
            description="Find threads that had more than one email processed (thread replies / updates).",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_spurious_rate",
            description="Compute spurious rate: processing errors divided by total processed emails.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="search_tasks_by_field",
            description="Search/filter tasks by a specific field. Use for questions about a specific category, assignee, priority, company, or decision.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "field": types.Schema(
                        type="STRING",
                        description="The field to filter by. One of: category, assignee_id, priority, company_name, decision.",
                    ),
                    "value": types.Schema(
                        type="STRING",
                        description="The value to match. For assignee_id use: u_aarti, u_rohit, u_meera, u_karan, u_divya, u_triage. For category use: enterprise_rfp, smb_enquiry, marketing, alliances, finance, triage. For priority use: high, medium, low.",
                    ),
                },
                required=["field", "value"],
            ),
        ),
        types.FunctionDeclaration(
            name="count_emails_by_keyword_in_reasoning",
            description="Count emails whose routing reasoning mentions a specific keyword (e.g. 'GST', 'refund', 'spam', 'newsletter').",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "keyword": types.Schema(
                        type="STRING",
                        description="The keyword to search for in the reasoning text.",
                    ),
                },
                required=["keyword"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_marketing_vs_spam",
            description="Compare properly routed marketing emails vs skipped spam that used marketing-like keywords.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
    ])
]

SYSTEM_INSTRUCTION = """You are a helpful assistant for a sales inbox routing system. You answer questions about processed email data.

CRITICAL RULES:
1. ONLY use data returned by the functions. NEVER invent numbers or records.
2. If a function returns 0 or empty results, say exactly that — "zero" or "none found". Do NOT fabricate data.
3. If the user asks about something you can't query (e.g., a sub-category breakdown you don't have), say honestly "I don't have that breakdown stored."
4. If the user asks you to take an ACTION (send email, create task, etc.), decline — you only answer questions about already-processed data.
5. Provide meaningful, user-friendly summaries of the data. Do NOT just spit out raw metrics or arrays. Explain what the numbers mean in context, highlight interesting trends, and format the response using clean text, natural language, and bullet points where helpful.
6. When listing items, include relevant details like subject, company, confidence, and reasoning in a natural sentence structure.
7. For categories: enterprise_rfp, smb_enquiry, marketing, alliances, finance, triage.
8. For assignees: u_aarti (Aarti Menon, Enterprise Sales), u_rohit (Rohit Sharma, SMB), u_meera (Meera Iyer, Marketing), u_karan (Karan Doshi, Alliances), u_divya (Divya Rao, Finance), u_triage (Triage Queue).
"""


class ChatService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def ask(self, question: str, scope: str = "db", batch_emails: list[dict] | None = None) -> dict:
        """
        Full pipeline: question → Gemini function calling → execute functions → Gemini answer.
        Returns dict with answer and supporting_data.
        """
        if scope == "batch" and batch_emails:
            try:
                # "Lighter quick-count pass" for un-ingested preview data
                # Strip down the emails to save tokens
                slim_emails = [
                    {
                        "email_id": e.get("email_id"),
                        "subject": e.get("subject"),
                        "from_name": e.get("from_name"),
                        "from_email": e.get("from_email"),
                        "body": str(e.get("body", ""))[:300]
                    }
                    for e in batch_emails
                ]
                
                batch_prompt = f"""You are answering a question about an un-ingested batch of emails. 
Question: {question}

Here is the JSON batch:
{json.dumps(slim_emails)}

Answer the question strictly based on the provided JSON. Count the emails matching the criteria and provide a short, clean text summary. Do not invent numbers."""
                
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=batch_prompt,
                )
                
                return {
                    "answer": response.text.strip() if response.text else "No answer generated.",
                    "supporting_data": {"batch_size": len(batch_emails), "note": "Analyzed via lightweight preview pass"},
                    "functions_called": [{"function": "analyze_json_batch", "args": {"count": len(batch_emails)}}],
                }
            except Exception as e:
                traceback.print_exc()
                return {
                    "answer": f"Sorry, I encountered an error analyzing the batch: {str(e)}",
                    "supporting_data": {},
                    "functions_called": [],
                    "error": str(e),
                }

        try:
            # Step 1: Send question to Gemini with function declarations
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=question,
                config=types.GenerateContentConfig(
                    tools=TOOL_DECLARATIONS,
                    system_instruction=SYSTEM_INSTRUCTION,
                ),
            )

            # Step 2: Check if Gemini wants to call functions
            all_supporting_data = {}
            function_calls_made = []

            # Iterate through response parts looking for function calls
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                function_call_parts = [p for p in parts if p.function_call]

                if function_call_parts:
                    # Execute each requested function
                    function_responses = []
                    for part in function_call_parts:
                        fc = part.function_call
                        fn_name = fc.name
                        fn_args = dict(fc.args) if fc.args else {}

                        function_calls_made.append({"function": fn_name, "args": fn_args})

                        if fn_name in FUNCTION_MAP:
                            try:
                                result = FUNCTION_MAP[fn_name](**fn_args)
                            except Exception as e:
                                result = {"error": str(e)}
                        else:
                            result = {"error": f"Unknown function: {fn_name}"}

                        # Merge into supporting data
                        if isinstance(result, dict):
                            all_supporting_data.update(result)

                        function_responses.append(
                            types.Part.from_function_response(
                                name=fn_name,
                                response=json.loads(json.dumps(result, default=str)),
                            )
                        )

                    # Step 3: Send function results back to Gemini for final answer
                    final_response = self.client.models.generate_content(
                        model=MODEL_NAME,
                        contents=[
                            types.Content(role="user", parts=[types.Part.from_text(text=question)]),
                            response.candidates[0].content,
                            types.Content(role="user", parts=function_responses),
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                        ),
                    )

                    answer = final_response.text.strip() if final_response.text else "No answer generated."

                else:
                    # No function call — Gemini answered directly (e.g. out-of-scope question)
                    answer = response.text.strip() if response.text else "I can only answer questions about processed email data."

            else:
                answer = "I couldn't process that question. Please try rephrasing."

            return {
                "answer": answer,
                "supporting_data": all_supporting_data,
                "functions_called": function_calls_made,
            }

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                answer = "Your daily Gemini API quota has expired. Please try again later or upgrade your plan."
            else:
                answer = f"Sorry, I encountered an error: {err_msg}"
                
            return {
                "answer": answer,
                "supporting_data": {},
                "functions_called": [],
                "error": err_msg,
            }
