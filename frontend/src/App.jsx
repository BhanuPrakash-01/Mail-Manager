import { useState, useEffect, useCallback, useRef } from 'react';
import StatsBar from './components/StatsBar';
import UploadPanel from './components/UploadPanel';
import TasksTable from './components/TasksTable';
import ChatPanel from './components/ChatPanel';
import { fetchStats, fetchTasks, submitIngest, pollRunStatus } from './api';

const CANDIDATE_ID = 'bhanuprakashaleti06@gmail.com';

export default function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [previewData, setPreviewData] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState(null);
  const pollRef = useRef(null);

  // Load initial data
  const loadData = useCallback(async () => {
    try {
      const [statsRes, tasksRes] = await Promise.all([
        fetchStats(),
        fetchTasks(),
      ]);
      setStats(statsRes);
      setTasks(tasksRes.tasks || []);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh while processing
  useEffect(() => {
    if (isProcessing) {
      const interval = setInterval(loadData, 3000);
      return () => clearInterval(interval);
    }
  }, [isProcessing, loadData]);

  const handleFileLoaded = (data) => {
    setPreviewData(data);
  };

  const handleSubmit = async () => {
    if (!previewData || previewData.length === 0) return;

    setIsProcessing(true);
    setActiveTab('tasks');

    try {
      const result = await submitIngest(CANDIDATE_ID, previewData);
      const runId = result.run_id;
      setProcessingStatus({ runId, ...result });

      // Poll for completion
      pollRef.current = setInterval(async () => {
        try {
          const status = await pollRunStatus(runId);
          setProcessingStatus({ runId, ...status });

          // Refresh tasks list
          const tasksRes = await fetchTasks();
          setTasks(tasksRes.tasks || []);

          // Refresh stats
          const statsRes = await fetchStats();
          setStats(statsRes);

          if (status.status === 'completed') {
            clearInterval(pollRef.current);
            setIsProcessing(false);
          }
        } catch (err) {
          console.error('Poll error:', err);
        }
      }, 2000);
    } catch (err) {
      console.error('Submit error:', err);
      setIsProcessing(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>📬 Mail Manager</h1>
        <span className="header-badge">
          {isProcessing ? '⏳ Processing...' : '● Online'}
        </span>
      </header>

      <StatsBar stats={stats} />

      <div className="main-content">
        <div className="left-panel">
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              📤 Upload & Preview
            </button>
            <button
              className={`panel-tab ${activeTab === 'tasks' ? 'active' : ''}`}
              onClick={() => setActiveTab('tasks')}
            >
              📋 Processed Tasks
              {tasks.length > 0 && (
                <span style={{
                  marginLeft: 6,
                  fontSize: 10,
                  padding: '1px 6px',
                  borderRadius: 10,
                  background: 'var(--accent-blue-glow)',
                  color: 'var(--accent-blue)',
                }}>
                  {tasks.length}
                </span>
              )}
            </button>
          </div>

          <div className="tab-content">
            {isProcessing && processingStatus && (
              <div className="processing-bar">
                <div className="spinner"></div>
                <span>
                  Processing: {processingStatus.processed_count} / {previewData?.length || '?'}
                  {' '}| Created: {processingStatus.created_count}
                  {' '}| Skipped: {processingStatus.skipped_count}
                  {' '}| Errors: {processingStatus.error_count}
                </span>
              </div>
            )}

            {activeTab === 'upload' && (
              <UploadPanel
                onFileLoaded={handleFileLoaded}
                onSubmit={handleSubmit}
                isProcessing={isProcessing}
                previewData={previewData}
              />
            )}

            {activeTab === 'tasks' && (
              <TasksTable tasks={tasks} />
            )}
          </div>
        </div>

        <ChatPanel previewData={previewData} />
      </div>
    </div>
  );
}
