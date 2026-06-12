function Header({ connected, assoEnabled, assoStatus, onToggleAsso, view, onViewChange }) {
  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          <div className="logo-icon">⚡</div>
          <div>
            <div className="logo-text text-gradient">ASSO</div>
            <div className="logo-subtitle">Adaptive Stability Orchestrator</div>
          </div>
        </div>

        <div className="header-nav">
          <button
            className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`}
            onClick={() => onViewChange('dashboard')}
          >
            📊 Dashboard
          </button>
          <button
            className={`nav-btn ${view === 'comparison' ? 'active' : ''}`}
            onClick={() => onViewChange('comparison')}
          >
            ⚖️ Compare
          </button>
        </div>
      </div>

      <div className="header-right">
        {assoStatus && (
          <div className="header-stats">
            <div className="header-stat">
              <span className="header-stat-value">{assoStatus.services_monitored}</span>
              <span className="header-stat-label">Services</span>
            </div>
            <div className="header-stat">
              <span className="header-stat-value">{assoStatus.total_predictions?.toLocaleString()}</span>
              <span className="header-stat-label">Predictions</span>
            </div>
            <div className="header-stat">
              <span className="header-stat-value">{assoStatus.total_actions}</span>
              <span className="header-stat-label">Actions</span>
            </div>
            <div className="header-stat">
              <span className="header-stat-value">{assoStatus.accuracy}%</span>
              <span className="header-stat-label">Accuracy</span>
            </div>
            <div className="header-stat">
              <span className="header-stat-value">{formatUptime(assoStatus.uptime_seconds)}</span>
              <span className="header-stat-label">Uptime</span>
            </div>
          </div>
        )}

        <div className="connection-status">
          <span className={`connection-dot ${connected ? 'connected' : 'disconnected'}`}></span>
          <span>{connected ? 'Live' : 'Offline'}</span>
        </div>

        <div className="asso-toggle">
          <span className="asso-toggle-label">ASSO</span>
          <button
            className={`toggle-switch ${assoEnabled ? 'on' : 'off'}`}
            onClick={onToggleAsso}
            title={assoEnabled ? 'Disable ASSO orchestration' : 'Enable ASSO orchestration'}
          />
        </div>
      </div>
    </header>
  );
}

export default Header;
