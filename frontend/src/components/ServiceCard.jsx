function ServiceCard({ service, latestMetric, risk }) {
  const statusClass = service.status === 'healthy' ? 'healthy' :
                      service.status === 'unhealthy' ? 'unhealthy' : 'unknown';

  const riskLevel = risk?.risk_level || 'low';

  const formatValue = (val, unit = '') => {
    if (val === undefined || val === null) return '—';
    return `${typeof val === 'number' ? val.toFixed(1) : val}${unit}`;
  };

  return (
    <div className="service-card glass-card">
      <div className="service-card-header">
        <div className="service-card-name">
          <span className={`status-dot ${statusClass}`}></span>
          {service.name}
        </div>
        <span className="service-card-type">{service.service_type}</span>
      </div>

      {risk && (
        <div style={{ marginBottom: '10px' }}>
          <span className={`risk-badge ${riskLevel}`}>
            {riskLevel === 'critical' ? '🔴' : riskLevel === 'high' ? '🟠' :
             riskLevel === 'moderate' ? '🟡' : '🟢'}
            {' '}{riskLevel} · {risk.risk_score?.toFixed(0)}
          </span>
        </div>
      )}

      <div className="service-metrics-grid">
        <div className="service-metric">
          <span className="metric-label">CPU</span>
          <span className="metric-value" style={{
            color: (latestMetric?.cpu_percent || 0) > 70 ? 'var(--accent-rose)' :
                   (latestMetric?.cpu_percent || 0) > 40 ? 'var(--accent-amber)' : 'var(--accent-emerald)'
          }}>
            {formatValue(latestMetric?.cpu_percent, '%')}
          </span>
        </div>
        <div className="service-metric">
          <span className="metric-label">Memory</span>
          <span className="metric-value" style={{
            color: (latestMetric?.memory_mb || 0) > 500 ? 'var(--accent-amber)' : 'var(--text-primary)'
          }}>
            {latestMetric?.memory_mb ? `${latestMetric.memory_mb.toFixed(0)}MB` : '—'}
          </span>
        </div>
        <div className="service-metric">
          <span className="metric-label">Latency</span>
          <span className="metric-value" style={{
            color: (latestMetric?.latency_ms || 0) > 500 ? 'var(--accent-rose)' :
                   (latestMetric?.latency_ms || 0) > 100 ? 'var(--accent-amber)' : 'var(--text-primary)'
          }}>
            {formatValue(latestMetric?.latency_ms, 'ms')}
          </span>
        </div>
        <div className="service-metric">
          <span className="metric-label">Req/s</span>
          <span className="metric-value">
            {formatValue(latestMetric?.request_rate)}
          </span>
        </div>
      </div>

      <div style={{ marginTop: '8px', fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        {service.host}:{service.port}
      </div>
    </div>
  );
}

export default ServiceCard;
