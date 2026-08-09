import { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../api';
import CellDetailModal from './CellDetailModal';

export default function ChatPanel({ previewData }) {
  const [scope, setScope] = useState('db');
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: 'Hi! I can answer questions about your processed emails. Try asking:\n\n• "How many emails were proposal or RFP related?"\n• "How many were marketing versus actual spam?"\n• "Show me everything sitting in triage and why."\n• "What\'s our spurious rate so far?"\n• "What\'s the total deal value of all open RFPs?"',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState({ open: false, title: '', content: '' });
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setLoading(true);

    try {
      const result = await sendChatMessage(question, scope, previewData);
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: result.answer,
          functionsCalled: result.functions_called,
          data: result.supporting_data,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: 'Sorry, something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderSupportingData = (data) => {
    if (!data || Object.keys(data).length === 0) return null;

    // Filter out complex nested arrays for compact display
    const simpleEntries = Object.entries(data).filter(
      ([, v]) => typeof v !== 'object' || v === null
    );
    const complexEntries = Object.entries(data).filter(
      ([, v]) => typeof v === 'object' && v !== null && !Array.isArray(v)
    );
    const arrayEntries = Object.entries(data).filter(
      ([, v]) => Array.isArray(v)
    );

    return (
      <div className="supporting-data">
        {simpleEntries.length > 0 && (
          <div className="data-grid">
            {simpleEntries.map(([k, v]) => (
              <div key={k} className="data-cell">
                <span className="data-key" style={{ textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</span>
                <span className="data-value">
                  {typeof v === 'number' && k.includes('rate')
                    ? `${(v * 100).toFixed(1)}%`
                    : typeof v === 'number' && k.includes('value')
                    ? `₹${v.toLocaleString('en-IN')}`
                    : String(v ?? '—')}
                </span>
              </div>
            ))}
          </div>
        )}
        {complexEntries.map(([k, v]) => (
          <div key={k} className="data-grid" style={{ marginTop: 6 }}>
            {Object.entries(v).map(([subK, subV]) => (
              <div key={subK} className="data-cell">
                <span className="data-key">{subK.replace(/_/g, ' ')}</span>
                <span className="data-value">{String(subV)}</span>
              </div>
            ))}
          </div>
        ))}
        {arrayEntries.map(([k, arr]) => (
          <div key={k} style={{ marginTop: 12 }}>
            <span className="data-key" style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 6, textTransform: 'capitalize', color: 'var(--text-secondary)' }}>
              {k.replace(/_/g, ' ')} ({arr.length} found)
            </span>
            {arr.length > 0 && (
              <div className="chat-data-list">
                {arr.slice(0, 20).map((item, idx) => (
                  <div key={idx} className="chat-data-item">
                    <div className="chat-data-item-header">
                      <strong>{item.email_id || `Item ${idx + 1}`}</strong>
                      {item.subject && <span title={item.subject}>{item.subject.length > 40 ? item.subject.substring(0, 40) + '...' : item.subject}</span>}
                    </div>
                    <button 
                      className="btn-view-details" 
                      onClick={() => {
                        const details = `Subject: ${item.subject || 'N/A'}\n` +
                          `From: ${item.from_name || ''} <${item.from_email || ''}>\n` +
                          `Category: ${item.category || 'N/A'}\n` +
                          `Priority: ${item.priority || 'N/A'}\n` +
                          `Confidence: ${item.confidence ? (item.confidence * 100).toFixed(0) + '%' : 'N/A'}\n` +
                          `Reasoning: ${item.reasoning || 'N/A'}\n\n` +
                          `Body:\n${item.body || 'N/A'}`;
                        
                        setModal({
                          open: true,
                          title: 'Email Details',
                          content: details
                        });
                      }}
                    >
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      View
                    </button>
                  </div>
                ))}
                {arr.length > 20 && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>
                    + {arr.length - 20} more items (not shown)
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-title">
          <div className="chat-icon">💬</div>
          <h2>Data Chat</h2>
        </div>
        <div className="chat-scope-toggle">
          <button 
            className={`scope-btn ${scope === 'db' ? 'active' : ''}`}
            onClick={() => setScope('db')}
          >
            Database
          </button>
          <button 
            className={`scope-btn ${scope === 'batch' ? 'active' : ''}`}
            onClick={() => setScope('batch')}
            disabled={!previewData || previewData.length === 0}
            title={!previewData ? 'Load a batch first' : ''}
          >
            Current Batch
          </button>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
            {(msg.functionsCalled?.length > 0 || msg.data) && (
              <details className="chat-debug-details">
                <summary className="chat-debug-summary">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                  Database Sources
                </summary>
                <div className="chat-debug-content">
                  {msg.functionsCalled && msg.functionsCalled.length > 0 && (
                    <div className="functions-block" style={{ marginBottom: msg.data ? 12 : 0, paddingBottom: msg.data ? 12 : 0, borderBottom: msg.data ? '1px solid var(--border-light)' : 'none' }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>Executed Functions</div>
                      {msg.functionsCalled.map((fc, j) => (
                        <span key={j} className="function-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--main-bg)', padding: '4px 8px', borderRadius: 4, border: '1px solid var(--border-light)', fontSize: 11, fontFamily: 'monospace' }}>
                          <span style={{ color: 'var(--accent-purple)' }}>{fc.function}</span>
                          {fc.args && Object.keys(fc.args).length > 0 && (
                            <span style={{ color: 'var(--text-muted)' }}>({Object.values(fc.args).join(', ')})</span>
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                  {msg.data && renderSupportingData(msg.data)}
                </div>
              </details>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-message bot">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="spinner" style={{ width: 14, height: 14 }}></span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          className="chat-input"
          placeholder="Ask about your email data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <CellDetailModal
        isOpen={modal.open}
        onClose={() => setModal({ open: false, title: '', content: '' })}
        title={modal.title}
        content={modal.content}
      />
    </div>
  );
}
