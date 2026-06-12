import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';

function MetricsChart({ title, subtitle, services, metrics, metricKeys, colors, labels, yDomain, unit }) {
  // Merge metrics from all services into a time-series
  const chartData = useMemo(() => {
    const allPoints = [];

    for (const service of services) {
      const serviceMetrics = metrics[service.id] || [];
      for (const m of serviceMetrics) {
        const point = {
          time: m.timestamp instanceof Date ? m.timestamp : new Date(m.timestamp),
        };
        metricKeys.forEach((key, i) => {
          point[`${service.id}_${key}`] = m[key];
        });
        point._serviceId = service.id;
        allPoints.push(point);
      }
    }

    // Sort by time and deduplicate
    allPoints.sort((a, b) => a.time - b.time);

    // Group by approximate timestamp (within 500ms)
    const grouped = [];
    for (const point of allPoints) {
      const last = grouped[grouped.length - 1];
      if (last && Math.abs(point.time - last.time) < 500) {
        Object.assign(last, point);
      } else {
        grouped.push({ ...point });
      }
    }

    // Keep last 120 points
    return grouped.slice(-120);
  }, [services, metrics, metricKeys]);

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
        {payload.map((entry, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: entry.color }}></div>
            <span style={{ color: '#94a3b8' }}>{entry.name}:</span>
            <span style={{ color: '#f1f5f9', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
              {unit}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="chart-card glass-card">
      <div className="chart-card-header">
        <div>
          <div className="chart-card-title">📈 {title}</div>
          <div className="chart-card-subtitle">{subtitle}</div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {labels.map((label, i) => (
            <div key={i} className="legend-item">
              <div className="legend-color" style={{ background: colors[i] }}></div>
              {label}
            </div>
          ))}
        </div>
      </div>
      <div className="chart-container">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="time"
                tickFormatter={formatTime}
                stroke="#475569"
                tick={{ fontSize: 10, fill: '#64748b' }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={yDomain || ['auto', 'auto']}
                stroke="#475569"
                tick={{ fontSize: 10, fill: '#64748b' }}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* Warning/Critical reference lines for CPU/Memory */}
              {metricKeys.includes('cpu_percent') && (
                <>
                  <ReferenceLine y={70} stroke="#f59e0b" strokeDasharray="5 5" strokeOpacity={0.5} />
                  <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="5 5" strokeOpacity={0.5} />
                </>
              )}
              {services.map((service) =>
                metricKeys.map((key, i) => (
                  <Line
                    key={`${service.id}_${key}`}
                    type="monotone"
                    dataKey={`${service.id}_${key}`}
                    stroke={colors[i]}
                    strokeWidth={2}
                    dot={false}
                    name={`${service.name} · ${labels[i]}`}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))
              )}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <div className="empty-state-text">Waiting for metric data...</div>
            <div className="empty-state-hint">Metrics will appear once services are running</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default MetricsChart;
