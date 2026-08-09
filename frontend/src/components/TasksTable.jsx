import { useState, useMemo } from 'react';
import CellDetailModal from './CellDetailModal';

const ASSIGNEE_META = {
  u_aarti: { name: 'Aarti Menon', dept: 'Sales — Enterprise', emoji: '🏢' },
  u_rohit: { name: 'Rohit Sharma', dept: 'Sales — SMB', emoji: '🛒' },
  u_meera: { name: 'Meera Iyer', dept: 'Marketing', emoji: '📢' },
  u_karan: { name: 'Karan Doshi', dept: 'Alliances', emoji: '🤝' },
  u_divya: { name: 'Divya Rao', dept: 'Finance', emoji: '💰' },
  u_triage: { name: 'Triage Queue', dept: 'Operations', emoji: '⚠️' },
};

export default function TasksTable({ tasks }) {
  const [expandedGroups, setExpandedGroups] = useState(new Set(Object.keys(ASSIGNEE_META).concat(['_skipped', '_errors'])));
  const [modal, setModal] = useState({ open: false, title: '', content: '' });

  const grouped = useMemo(() => {
    if (!tasks || tasks.length === 0) return {};

    const groups = {};

    for (const task of tasks) {
      // Separate skipped and error tasks
      if (task.decision === 'skip') {
        if (!groups['_skipped']) groups['_skipped'] = [];
        groups['_skipped'].push(task);
      } else if (task.decision === 'processing_error') {
        if (!groups['_errors']) groups['_errors'] = [];
        groups['_errors'].push(task);
      } else {
        const key = task.assignee_id || '_unassigned';
        if (!groups[key]) groups[key] = [];
        groups[key].push(task);
      }
    }

    return groups;
  }, [tasks]);

  const toggleGroup = (key) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const openModal = (title, content) => {
    setModal({ open: true, title, content: content || '—' });
  };

  const getDecisionBadge = (decision) => {
    const map = {
      create_task: 'badge-create',
      update_task: 'badge-update',
      skip: 'badge-skip',
      processing_error: 'badge-error',
    };
    return map[decision] || '';
  };

  const getPriorityBadge = (priority) => {
    if (!priority) return '';
    return `badge-${priority}`;
  };

  if (!tasks || tasks.length === 0) {
    return (
      <div className="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <h3>No tasks yet</h3>
        <p>Process emails to see routing decisions here</p>
      </div>
    );
  }

  // Render order: assignees first, then skipped, then errors
  const assigneeKeys = Object.keys(ASSIGNEE_META).filter((k) => grouped[k]);
  const renderOrder = [...assigneeKeys];
  if (grouped['_skipped']) renderOrder.push('_skipped');
  if (grouped['_errors']) renderOrder.push('_errors');

  const getGroupMeta = (key) => {
    if (key === '_skipped') return { name: 'Skipped / Ignored', dept: 'Auto-replies, newsletters, spam', emoji: '🚫' };
    if (key === '_errors') return { name: 'Processing Errors', dept: 'Failed to process', emoji: '❌' };
    if (key === '_unassigned') return { name: 'Unassigned', dept: '', emoji: '❓' };
    return ASSIGNEE_META[key] || { name: key, dept: '', emoji: '👤' };
  };

  return (
    <div className="assignee-groups">
      {renderOrder.map((key) => {
        const meta = getGroupMeta(key);
        const isExpanded = expandedGroups.has(key);
        const isSkipped = key === '_skipped';
        const isError = key === '_errors';
        
        const priorityOrder = { high: 1, medium: 2, low: 3 };
        const items = [...grouped[key]].sort((a, b) => {
          const pA = priorityOrder[a.priority?.toLowerCase()] || 99;
          const pB = priorityOrder[b.priority?.toLowerCase()] || 99;
          return pA - pB;
        });

        return (
          <div key={key} className={`assignee-group ${isSkipped ? 'group-skipped' : ''} ${isError ? 'group-error' : ''}`}>
            <button className="group-header" onClick={() => toggleGroup(key)}>
              <div className="group-header-left">
                <span className="group-chevron">{isExpanded ? '▾' : '▸'}</span>
                <span className="group-emoji">{meta.emoji}</span>
                <span className="group-name">{meta.name}</span>
                {meta.dept && <span className="group-dept">— {meta.dept}</span>}
              </div>
              <span className="group-count">{items.length}</span>
            </button>

            {isExpanded && (
              <div className="group-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Email ID</th>
                      <th>Subject</th>
                      <th>Body</th>
                      <th>From</th>
                      <th>Decision</th>
                      {!isSkipped && !isError && <th>Category</th>}
                      {!isSkipped && !isError && <th>Priority</th>}
                      {!isSkipped && !isError && <th>Company</th>}
                      {!isSkipped && !isError && <th>Confidence</th>}
                      {!isSkipped && !isError && <th>Deal Value</th>}
                      {!isSkipped && !isError && <th>Due Date</th>}
                      {isSkipped && <th>Reason</th>}
                      {isError && <th>Error</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((task) => (
                      <tr key={task.email_id}>
                        <td
                          className="cell-clickable"
                          style={{ color: 'var(--accent-blue)', fontWeight: 500, fontFamily: 'monospace', fontSize: 11 }}
                          onClick={() => openModal('Email ID', task.email_id)}
                        >
                          {task.email_id}
                        </td>
                        <td
                          className="cell-clickable"
                          title={task.subject}
                          style={{ maxWidth: 200 }}
                          onClick={() => openModal('Subject', task.subject)}
                        >
                          {task.subject || '—'}
                        </td>
                        <td
                          className="cell-clickable"
                          title={task.body}
                          style={{ maxWidth: 160, fontSize: 11, color: 'var(--text-muted)' }}
                          onClick={() => openModal('Email Body', task.body)}
                        >
                          {task.body ? (task.body.length > 60 ? task.body.slice(0, 60) + '…' : task.body) : '—'}
                        </td>
                        <td
                          className="cell-clickable"
                          onClick={() => openModal('From', `${task.from_name || ''}\n${task.from_email || ''}`)}
                        >
                          {task.from_name || task.from_email || '—'}
                        </td>
                        <td>
                          <span className={`badge ${getDecisionBadge(task.decision)}`}>
                            {task.decision?.replace('_', ' ')}
                          </span>
                        </td>

                        {!isSkipped && !isError && (
                          <>
                            <td>
                              {task.category ? (
                                <span className={`badge badge-${task.category}`}>
                                  {task.category?.replace('_', ' ')}
                                </span>
                              ) : '—'}
                            </td>
                            <td>
                              {task.priority ? (
                                <span className={`badge ${getPriorityBadge(task.priority)}`}>
                                  {task.priority}
                                </span>
                              ) : '—'}
                            </td>
                            <td
                              className="cell-clickable"
                              title={task.company_name}
                              onClick={() => openModal('Company', task.company_name)}
                            >
                              {task.company_name || '—'}
                            </td>
                            <td>
                              {task.confidence != null ? (
                                <span style={{
                                  color: task.confidence >= 0.8 ? 'var(--accent-green)' :
                                         task.confidence >= 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)',
                                  fontWeight: 600,
                                }}>
                                  {(task.confidence * 100).toFixed(0)}%
                                </span>
                              ) : '—'}
                            </td>
                            <td>
                              {task.deal_value_inr ? `₹${task.deal_value_inr.toLocaleString('en-IN')}` : '—'}
                            </td>
                            <td>{task.due_date || '—'}</td>
                          </>
                        )}

                        {isSkipped && (
                          <td
                            className="cell-clickable"
                            onClick={() => openModal('Skip Reason', task.reasoning)}
                          >
                            {task.reasoning ? (task.reasoning.length > 50 ? task.reasoning.slice(0, 50) + '…' : task.reasoning) : '—'}
                          </td>
                        )}

                        {isError && (
                          <td
                            className="cell-clickable cell-error"
                            onClick={() => openModal('Error Details', `Stage: ${task.error_stage || 'unknown'}\n\n${task.error_message || 'No details'}`)}
                          >
                            {task.error_stage || 'unknown'}: {task.error_message ? (task.error_message.length > 40 ? task.error_message.slice(0, 40) + '…' : task.error_message) : '—'}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      <CellDetailModal
        isOpen={modal.open}
        onClose={() => setModal({ open: false, title: '', content: '' })}
        title={modal.title}
        content={modal.content}
      />
    </div>
  );
}
