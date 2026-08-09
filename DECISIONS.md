# DECISIONS.md

This document outlines the 5 major design choices made while building the Sales Inbox Task Router, explained simply.

## 1. Handling API Limits
**The Problem**: The Gemini AI only allows us to process a certain number of emails per minute on the free tier. If we go too fast, Google blocks the request.
**The Decision**: Instead of letting the app crash when it gets blocked, we added a "pause and retry" feature. If Google says "slow down," the app automatically pauses for a few seconds and tries again, ensuring no emails are ever lost.
**If I had two more weeks**: I would move the email processing into a dedicated background queue (like Celery or Redis). This would allow the system to handle a massive upload of 10,000 emails smoothly without the web server ever timing out.

## 2. Preventing Duplicate Tickets
**The Problem**: We don't want the dashboard to get cluttered if the same email is uploaded twice, or if someone replies to an existing email thread.
**The Decision**: We check our database before creating any new tickets. If the exact email already exists, we skip it. If it's a reply to an ongoing conversation, we just *update* the original ticket instead of creating a brand new one.
**If I had two more weeks**: I would use AI vector embeddings to match email threads together. This way, even if an email client deletes the standard "Thread ID" hidden headers, the AI could still recognize that two emails are part of the same conversation.

## 3. Using a Postgres Cloud Database
**The Problem**: The external Task API provided for the hackathon doesn't save all the rich details we need (like the AI's reasoning or the deal value).
**The Decision**: We created our own PostgreSQL cloud database (Neon) to save everything the AI extracts. Because we save this rich data in our own database, our dashboard loads instantly and we never have to waste time (or money) asking the AI to read the same email twice.
**If I had two more weeks**: I would add full-text search indexing (like PostgreSQL TSVector) to the database. This would allow the dashboard to instantly and intelligently search through thousands of massive email bodies for any random keyword.

## 4. Stopping Chatbot Lies (Hallucinations)
**The Problem**: If you ask an AI chatbot "How many deals are over $5000?", it will often get confused by the text and invent a fake number.
**The Decision**: Our Chatbot is not allowed to read raw emails. When you ask it a question, it is forced to write a strict Database Query (SQL) to count the exact rows in our local database. This guarantees the chat gives you 100% mathematically accurate answers based on hard facts.
**If I had two more weeks**: I would build a more advanced Text-to-SQL engine that automatically reads the database structure. This would allow operations executives to ask the chatbot wildly complex, ad-hoc questions without me having to hardcode a specific Python function for every possible scenario.

## 5. Accepting Messy Email Replies
**The Problem**: When people reply to long email chains, they sometimes type in the middle of the old text, making it hard to tell what is "new" and what is "old history."
**The Decision**: We built rules to try and ignore the old history, but we accept that it won't be perfect 100% of the time. Trying to write a perfect rule for every messy email format (Outlook, Gmail, Apple Mail) usually ends up breaking normal emails, so we chose to keep it simple and stable.
**If I had two more weeks**: I would gather a massive dataset of broken, messy email threads and train a smaller, dedicated AI model just to perfectly isolate the "newest" message from the history block.
