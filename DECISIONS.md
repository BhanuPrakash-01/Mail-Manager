# DECISIONS.md

This document outlines the five major engineering tradeoffs made while building the Sales Inbox Task Router.

## 1. Handling Gemini Rate Limits and Retries
**Decision**: Implementing bounded exponential backoff with a specific jittered pause for quota exhaustion.
**Tradeoff**: The Gemini free tier has strict RPM limits. If we hit a `429 RESOURCE_EXHAUSTED` error, failing immediately drops the task, which violates the core outcome. Instead, the ingest worker uses an exponential backoff specifically catching 429s. If the quota is completely exhausted (e.g., daily limit), it raises a clean exception that marks the task as failed in the database rather than crashing the pipeline. 
**If I had two more weeks**: I would decouple extraction into an asynchronous background queue (like Celery or Redis Queue) instead of processing synchronously in the `/ingest` request, which risks HTTP timeouts for large batches.

## 2. Enforcing Idempotency and Thread Reconciliation
**Decision**: UPSERT (`merge`) operations based on `email_id` and `thread_id`.
**Tradeoff**: The `/tasks` API does not deduplicate. We track all processed tasks in a local `email_processing` table using `email_id` as the primary key. When the `/ingest` endpoint processes an email, it first checks if the `email_id` exists (idempotency) and skips if so. It also checks if the `thread_id` exists; if it does, it updates the existing task via a `PATCH` request rather than creating a new duplicate. This ensures the dashboard always reflects the true state without bloated duplicate tickets.
**If I had two more weeks**: I would implement vector embeddings for thread matching in case thread headers are stripped by forwarding or weird clients.

## 3. Backend Data Model Design
**Decision**: A structured relational table `email_processing` acting as the absolute ground truth.
**Tradeoff**: We could have just relied on the external `/tasks` API, but it doesn't track "skipped" emails or granular metadata like "reasoning" or "confidence" in a structured way. By saving everything locally (Decision, Category, Assignee, Deal Value, Confidence, Body, and Reasoning), the dashboard and chat interface can query SQLite/Postgres instantly. We never re-hit Gemini for facts we already know.
**If I had two more weeks**: I would add full-text search indexing (like PostgreSQL TSVector) to `reasoning` and `body` columns for much faster and richer text filtering on the dashboard.

## 4. Chat Grounding and Hallucination Prevention
**Decision**: Gemini Function Calling strictly tied to predefined SQL queries.
**Tradeoff**: Chat interfaces are prone to hallucinating numbers if you just feed them raw text. To solve this, the `/api/chat` endpoint does *not* read raw emails. Instead, it uses Gemini Function Calling to translate natural language into one of 14 strictly defined python functions (e.g., `search_tasks_by_field()`, `get_stats()`). Gemini merely orchestrates the functions, and the backend runs safe SQL against our structured ground truth. If the result is 0, Gemini is explicitly prompted to say "zero" rather than inventing a plausible sounding dataset. 
**If I had two more weeks**: I would use a more dynamic Text-to-SQL layer with schema introspection, allowing operations executives to ask ad-hoc complex queries ("group by assignee where confidence < 0.5") without needing me to write a hardcoded function for every possibility.

## 5. Known Imperfection Shipped Anyway
**Decision**: Not re-parsing deeply nested, inline-quoted text during a thread reply.
**Tradeoff**: When an email comes in as a thread reply (Example 10), it often quotes the entire history below. The extraction prompt explicitly tries to ignore the quoted history, but if a sender replies *inline* (breaking the quotes), the LLM might struggle to isolate the "new" information and could hallucinate a new deal value. I shipped it anyway because catching 95% of standard top-replies correctly updates the priority/due_date effectively, and writing a perfect deterministic regex for inline replies is notoriously brittle.
