# Mail Manager

**Candidate ID**: `bhanuprakashaleti06@gmail.com`
**Backend URL**: `https://mail-manager-production-b1a7.up.railway.app`
**Dashboard URL**: `https://mail-manager-nine.vercel.app`

This project automates the routing of sales emails into structured tasks using Gemini 3.1 Flash. It includes a resilient extraction pipeline, an idempotent ingest layer, a React dashboard, and a natural language chat interface grounded purely in the structured database.

## Setup & Running Locally

Ensure you have Python 3.10+ and Node.js 18+ installed.

1. **Environment Setup**
   Copy the example environment file and add your Gemini API key.
   ```bash
   cp .env.example .env
   ```

2. **Backend Setup**
   Install dependencies and start the FastAPI server.
   ```bash
   cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
   ```

3. **Frontend Setup**
   In a new terminal window, install dependencies and start the React app.
   ```bash
   cd frontend && npm install && npm run dev
   ```

You can now open `http://localhost:5173` to view the dashboard!

## Deployment

The repository is deployment-ready for platforms like Render, Railway, or Vercel.

**Backend**:
- Exposes standard FastAPI endpoints (`/ingest`, `/api/tasks`, `/api/stats`, `/api/chat`).
- Can be deployed directly via `Dockerfile` or using standard Python buildpacks (via `requirements.txt`).
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Frontend**:
- A standard Vite + React application.
- Can be deployed on Vercel or Netlify.
- Build command: `npm run build`
- Output directory: `dist`

## Documentation

- `DECISIONS.md` - Key engineering tradeoffs and architecture.
- `EVALS.md` - Precision/recall metrics and known failure cases.
