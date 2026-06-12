import { useRef, useEffect } from 'react';

function ActionLog({ actions, assoEnabled }) {
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [actions.length]);

  const formatTime = (ts) => {
    const d = ts instanceof Date ? ts : new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const icons = { rate_limit: '🟡', high_throttle: '🟠', critical_throttle: '🔴', relax: '🟢', prediction_only: '🔵' };
  const labels = { rate_limit: 'Rate Limited', high_throttle: 'Throttled', critical_throttle: 'Emergency', relax: 'Relaxed', prediction_only: 'Predicted' };
  const colors = { rate_limit: 'var(--accent-amber)', high_throttle: 'var(--risk-high)', critical_throttle: 'var(--accent-rose)', relax: 'var(--accent-emerald)', prediction_only: 'var(--accent-blue)' };

  return (
    <div className="action-log glass-card">
      <div className="action-log-title">
        <span>🎬 Action Log</span>
        <span className="action-log-count">{actions.length}</span>
      </div>
      {!assoEnabled && (
        <div style={{ padding: '6px 10px', marginBottom: '8px', borderRadius: '6px', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', fontSize: '0.7rem', color: 'var(--accent-amber)', textAlign: 'center' }}>
          ⚠️ ASSO Disabled — Prediction Only
        </div>
      )}
      <div className="action-log-list" ref={listRef}>
        {actions.length > 0 ? actions.slice(-50).map((a, i) => (
          <div key={a.id || i} className={`action-entry ${a.action_type}`}>
            <div className="action-entry-header">
              <span className="action-entry-type" style={{ color: colors[a.action_type] || 'var(--text-secondary)' }}>
                {icons[a.action_type] || '⚪'} {labels[a.action_type] || a.action_type}
              </span>
              <span className="action-entry-time">{formatTime(a.timestamp)}</span>
            </div>
            <div className="action-entry-reason">
              <span className="action-entry-service">{a.service_name || a.service_id}</span> — {a.reason}
            </div>
          </div>
        )) : (
          <div className="empty-state">
            <div className="empty-state-icon">🎬</div>
            <div className="empty-state-text">No actions yet</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ActionLog;
