const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchStats(runId) {
  const url = runId ? `${API_BASE}/api/stats?run_id=${runId}` : `${API_BASE}/api/stats`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchTasks(runId) {
  const url = runId ? `${API_BASE}/api/tasks?run_id=${runId}` : `${API_BASE}/api/tasks`;
  const res = await fetch(url);
  return res.json();
}

export async function submitIngest(candidateId, emails) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_id: candidateId, emails }),
  });
  return res.json();
}

export async function pollRunStatus(runId) {
  const res = await fetch(`${API_BASE}/ingest/${runId}`);
  return res.json();
}

export async function sendChatMessage(question, scope = 'db', batch_emails = null) {
  const payload = { question, scope };
  if (scope === 'batch' && batch_emails) {
    payload.batch_emails = batch_emails;
  }
  
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.json();
}
