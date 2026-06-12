import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Area, ComposedChart,
} from 'recharts';

function PredictionChart({ services, metrics, predictions }) {
  // Build combined actual vs predicted chart data
  const chartData = useMemo(() => {
    const data = [];
    const serviceId = services[0]?.id;
    if (!serviceId) return [];

    const serviceMetrics = metrics[serviceId] || [];
    const servicePreds = (predictions[serviceId] || []).filter(
      p => p.metric_type === 'cpu_percent'
    );

    // Build timeline from metrics
    for (const m of serviceMetrics.slice(-120)) {
      const time = m.timestamp instanceof Date ? m.timestamp : new Date(m.timestamp);
      data.push({
        time,
        actual_cpu: m.cpu_percent,
        actual_latency: m.latency_ms,
      });
    }

    // Overlay predictions
    for (const p of servicePreds.slice(-60)) {
      const time = p.timestamp instanceof Date ? p.timestamp : new Date(p.timestamp);
      // Find closest data point
      let closest = null;
      let minDiff = Infinity;
      for (const d of data) {
        const diff = Math.abs(d.time - time);
        if (diff < minDiff) {
          minDiff = diff;
          closest = d;
        }
      }
      if (closest && minDiff < 5000) {
        closest.predicted_cpu = p.predicted_value;
        closest.risk_score = p.risk_score;
        closest.confidence = p.confidence;
      }
    }

    return data;
  }, [services, metrics, predictions]);

  const formatTime = (time) => {
    if (!time) return '';
    const d = time instanceof Date ? time : new Date(time);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(59, 130, 246, 0.2)',
        borderRadius: '8px',
        padding: '10px 14px',
        backdropFilter: 'blur(8px)',
        fontSize: '0.75rem',
      }}>
        <div style={{ color: '#94a3b8', marginBottom: '6px', fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>
          {formatTime(label)}
        </div>
        {payload.map((entry, i) => {
          if (entry.value === undefined || entry.value === null) return null;
          const label = entry.dataKey === 'actual_cpu' ? '📊 Actual CPU' :
                       entry.dataKey === 'predicted_cpu' ? '🔮 Predicted CPU' :
                       entry.dataKey === 'risk_score' ? '⚠️ Risk Score' :
                       entry.name;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: entry.color }}></div>
              <span style={{ color: '#94a3b8' }}>{label}:</span>
              <span style={{ color: '#f1f5f9', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="chart-card glass-card">
      <div className="chart-card-header">
        <div>
          <div className="chart-card-title">🔮 Prediction vs Actual</div>
          <div className="chart-card-subtitle">ML forecast overlay — solid = actual, dashed = predicted</div>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#3b82f6' }}></div>
            Actual CPU
          </div>
          <div className="legend-item">
            <div className="legend-color dashed" style={{ color: '#f59e0b' }}></div>
            Predicted CPU
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: 'rgba(239, 68, 68, 0.3)' }}></div>
            Risk Score
          </div>
        </div>
      </div>
      <div className="chart-container">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="time"
                tickFormatter={formatTime}
                stroke="#475569"
                tick={{ fontSize: 10, fill: '#64748b' }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                stroke="#475569"
                tick={{ fontSize: 10, fill: '#64748b' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={70} stroke="#f59e0b" strokeDasharray="5 5" strokeOpacity={0.4} label="" />
              <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="5 5" strokeOpacity={0.4} label="" />

              {/* Risk score as area */}
              <Area
                type="monotone"
                dataKey="risk_score"
                fill="rgba(239, 68, 68, 0.08)"
                stroke="rgba(239, 68, 68, 0.3)"
                strokeWidth={1}
                isAnimationActive={false}
              />

              {/* Actual CPU - solid line */}
              <Line
                type="monotone"
                dataKey="actual_cpu"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />

              {/* Predicted CPU - dashed line */}
              <Line
                type="monotone"
                dataKey="predicted_cpu"
                stroke="#f59e0b"
                strokeWidth={2}
                strokeDasharray="6 3"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">🔮</div>
            <div className="empty-state-text">Predictions will appear shortly...</div>
            <div className="empty-state-hint">Need ~15 seconds of data for initial forecast</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default PredictionChart;
