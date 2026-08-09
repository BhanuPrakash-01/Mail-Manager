import { useState, useRef } from 'react';
import CellDetailModal from './CellDetailModal';

export default function UploadPanel({ onFileLoaded, onSubmit, isProcessing, previewData }) {
  const [dragOver, setDragOver] = useState(false);
  const [modal, setModal] = useState({ open: false, title: '', content: '' });
  const fileInputRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        onFileLoaded(Array.isArray(data) ? data : [data]);
      } catch (err) {
        alert('Invalid JSON file: ' + err.message);
      }
    };
    reader.readAsText(file);
  };

  const handleLoadSample = async () => {
    try {
      const response = await fetch('/inbox_test_250.json');
      const data = await response.json();
      onFileLoaded(Array.isArray(data) ? data : [data]);
    } catch (err) {
      alert('Failed to load sample data: ' + err.message);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const openModal = (title, content) => {
    setModal({ open: true, title, content: content || '—' });
  };

  return (
    <div>
      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInputRef.current?.click()}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 16V4m0 0L8 8m4-4l4 4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <h3>Upload inbox JSON</h3>
        <p>Drag & drop or click to browse</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={(e) => handleFile(e.target.files[0])}
        />
        <div style={{ marginTop: '1rem' }}>
          <button 
            className="btn btn-secondary" 
            onClick={(e) => {
              e.stopPropagation();
              handleLoadSample();
            }}
          >
            Load Sample Data
          </button>
        </div>
      </div>

      {previewData && previewData.length > 0 && (
        <>
          <div className="preview-info">
            <span>Loaded <span className="preview-count">{previewData.length}</span> emails</span>
            <div className="upload-actions">
              <button
                className="btn btn-primary"
                onClick={onSubmit}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <>
                    <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2, borderColor: 'transparent', borderTopColor: 'white' }}></span>
                    Processing...
                  </>
                ) : (
                  '🚀 Ingest Emails'
                )}
              </button>
            </div>
          </div>

          <div className="table-wrapper" style={{ maxHeight: '400px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Email ID</th>
                  <th>From</th>
                  <th>Subject</th>
                  <th>Received</th>
                  <th>Thread</th>
                  <th>Reply</th>
                </tr>
              </thead>
              <tbody>
                {previewData.slice(0, 250).map((email) => (
                  <tr key={email.email_id}>
                    <td
                      className="cell-clickable"
                      style={{ color: 'var(--accent-blue)', fontWeight: 500, fontFamily: 'monospace', fontSize: 11 }}
                      onClick={() => openModal('Email ID', email.email_id)}
                    >
                      {email.email_id}
                    </td>
                    <td
                      className="cell-clickable"
                      onClick={() => openModal('From', `${email.from_name || ''}\n${email.from_email || ''}`)}
                    >
                      {email.from_name || email.from_email}
                    </td>
                    <td
                      className="cell-clickable"
                      title={email.subject}
                      style={{ maxWidth: 220 }}
                      onClick={() => openModal('Subject', email.subject)}
                    >
                      {email.subject}
                    </td>
                    <td>{email.received_at ? new Date(email.received_at).toLocaleDateString() : '—'}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{email.thread_id}</td>
                    <td>{email.is_reply ? '✓' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {previewData.length > 250 && (
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
              Showing first 250 of {previewData.length} emails
            </p>
          )}
        </>
      )}

      {(!previewData || previewData.length === 0) && (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h3>No emails loaded</h3>
          <p>Upload an inbox JSON file to preview and process emails</p>
        </div>
      )}

      <CellDetailModal
        isOpen={modal.open}
        onClose={() => setModal({ open: false, title: '', content: '' })}
        title={modal.title}
        content={modal.content}
      />
    </div>
  );
}
