import { useMemo } from 'react';

function RiskGauge({ riskData, allRisks }) {
  const riskScore = riskData?.risk_score || 0;
  const riskLevel = riskData?.risk_level || 'low';
  const breachTime = riskData?.predicted_breach_time;
  const metricType = riskData?.metric_type || '';

  const riskColor = useMemo(() => {
    if (riskScore >= 90) return '#ef4444';
    if (riskScore >= 70) return '#f97316';
    if (riskScore >= 50) return '#f59e0b';
    if (riskScore >= 25) return '#22c55e';
    return '#10b981';
  }, [riskScore]);

  // SVG arc for gauge
  const radius = 60;
  const cx = 80;
  const cy = 85;
  const startAngle = Math.PI;
  const endAngle = 0;
  const sweepAngle = (startAngle - endAngle) * (riskScore / 100);
  const currentAngle = startAngle - sweepAngle;

  const arcPath = (startA, endA, r) => {
    const x1 = cx + r * Math.cos(startA);
    const y1 = cy - r * Math.sin(startA);
    const x2 = cx + r * Math.cos(endA);
    const y2 = cy - r * Math.sin(endA);
    const largeArc = Math.abs(startA - endA) > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  const metricLabels = {
    cpu_percent: 'CPU',
    memory_percent: 'Memory',
    latency_ms: 'Latency',
    queue_length: 'Queue',
  };

  return (
    <div className="risk-gauge-card glass-card">
      <div className="risk-gauge-title">Overall Risk Level</div>

      <div className="risk-gauge-container">
        <svg className="risk-gauge-svg" viewBox="0 0 160 100">
          {/* Background arc */}
          <path
            d={arcPath(Math.PI, 0, radius)}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Filled arc */}
          {riskScore > 0 && (
            <path
              d={arcPath(Math.PI, currentAngle, radius)}
              fill="none"
              stroke={riskColor}
              strokeWidth="10"
              strokeLinecap="round"
              style={{
                filter: riskScore > 70 ? `drop-shadow(0 0 6px ${riskColor})` : 'none',
                transition: 'all 0.5s ease',
              }}
            />
          )}
          {/* Tick marks */}
          {[0, 25, 50, 70, 85, 100].map((tick) => {
            const angle = Math.PI - (Math.PI * tick / 100);
            const x1 = cx + (radius - 16) * Math.cos(angle);
            const y1 = cy - (radius - 16) * Math.sin(angle);
            const x2 = cx + (radius - 12) * Math.cos(angle);
            const y2 = cy - (radius - 12) * Math.sin(angle);
            return (
              <line key={tick} x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
            );
          })}
        </svg>
        <div className="risk-gauge-value" style={{ color: riskColor }}>
          {riskScore.toFixed(0)}
        </div>
      </div>

      <div className="risk-gauge-label">
        <span className={`risk-badge ${riskLevel}`}>
          {riskLevel.toUpperCase()}
        </span>
      </div>

      {metricType && (
        <div style={{ marginTop: '6px', fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
          Highest risk: {metricLabels[metricType] || metricType}
        </div>
      )}

      {breachTime !== null && breachTime !== undefined && breachTime <= 90 && (
        <div className="breach-countdown">
          ⚠️ Predicted breach in <strong>{breachTime}s</strong>
        </div>
      )}

      {/* Per-service risk list */}
      <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
        {Object.entries(allRisks).map(([serviceId, data]) => (
          <div key={serviceId} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '4px 0', fontSize: '0.75rem',
          }}>
            <span style={{ color: 'var(--text-secondary)' }}>
              {data.service_name}
            </span>
            <span className={`risk-badge ${data.risk_level}`} style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
              {data.risk_score?.toFixed(0)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default RiskGauge;
