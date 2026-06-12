import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

function ComparisonView({ apiUrl }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchRuns();
    const iv = setInterval(fetchRuns, 10000);
    return () => clearInterval(iv);
  }, []);

  const fetchRuns = async () => {
    try {
      const resp = await fetch(`${apiUrl}/api/comparison/results`);
      if (resp.ok) setRuns(await resp.json());
    } catch {}
  };

  const startRun = async (assoEnabled) => {
    setLoading(true);
    try {
      const resp = await fetch(`${apiUrl}/api/comparison/start?asso_enabled=${assoEnabled}`, { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        setTimeout(async () => {
          await fetch(`${apiUrl}/api/comparison/end?run_id=${data.run_id}`, { method: 'POST' });
          fetchRuns();
          setLoading(false);
        }, 60000);
      }
    } catch { setLoading(false); }
  };

  const assoOn = runs.find(r => r.asso_enabled && r.end_time);
  const assoOff = runs.find(r => !r.asso_enabled && r.end_time);

  return (
    <div className="comparison-view">
      <div className="comparison-controls glass-card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>⚖️ Before/After Comparison</h3>
        <div style={{ flex: 1 }} />
        <button className="btn btn-danger" onClick={() => startRun(false)} disabled={loading}>
          {loading ? '⏳' : '🔴'} Run WITHOUT ASSO
        </button>
        <button className="btn btn-success" onClick={() => startRun(true)} disabled={loading}>
          {loading ? '⏳' : '🟢'} Run WITH ASSO
        </button>
        <button className="btn btn-ghost" onClick={fetchRuns}>🔄 Refresh</button>
      </div>

      {(assoOn || assoOff) ? (
        <div className="comparison-grid">
          {[{ run: assoOff, label: 'WITHOUT ASSO', color: '#ef4444', icon: '🔴' },
            { run: assoOn, label: 'WITH ASSO', color: '#10b981', icon: '🟢' }].map(({ run, label, color, icon }) => (
            <div key={label} className="comparison-panel glass-card">
              <div className="comparison-panel-header">
                <div className="comparison-panel-title">{icon} {label}</div>
                {run && <span className="risk-badge low" style={{ background: `${color}22`, color, borderColor: `${color}44` }}>
                  Completed
                </span>}
              </div>
              {run ? (
                <div className="comparison-stats">
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.peak_cpu?.toFixed(1)}%</div>
                    <div className="comparison-stat-label">Peak CPU</div>
                  </div>
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.peak_latency?.toFixed(0)}ms</div>
                    <div className="comparison-stat-label">Peak Latency</div>
                  </div>
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.error_count}</div>
                    <div className="comparison-stat-label">Errors</div>
                  </div>
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.avg_latency?.toFixed(0)}ms</div>
                    <div className="comparison-stat-label">Avg Latency</div>
                  </div>
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.breach_count}</div>
                    <div className="comparison-stat-label">Breaches</div>
                  </div>
                  <div className={`comparison-stat ${label.includes('WITH') ? 'better' : 'worse'}`}>
                    <div className="comparison-stat-value">{run.total_requests}</div>
                    <div className="comparison-stat-label">Requests</div>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">📊</div>
                  <div className="empty-state-text">No run data yet</div>
                  <div className="empty-state-hint">Click the button above to start a test run</div>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-card" style={{ padding: '40px' }}>
          <div className="empty-state">
            <div className="empty-state-icon">⚖️</div>
            <div className="empty-state-text">Run comparison tests to see before/after results</div>
            <div className="empty-state-hint">
              1. Start load generator  2. Click "Run WITHOUT ASSO"  3. Wait 60s  4. Click "Run WITH ASSO"
            </div>
          </div>
        </div>
      )}

      {/* All runs history */}
      {runs.length > 0 && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <h4 style={{ fontSize: '0.85rem', marginBottom: '10px' }}>📋 Run History</h4>
          <table style={{ width: '100%', fontSize: '0.75rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ color: 'var(--text-tertiary)', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px' }}>ASSO</th>
                <th style={{ padding: '6px 8px' }}>Start</th>
                <th style={{ padding: '6px 8px' }}>Peak CPU</th>
                <th style={{ padding: '6px 8px' }}>Peak Lat</th>
                <th style={{ padding: '6px 8px' }}>Errors</th>
                <th style={{ padding: '6px 8px' }}>Breaches</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 10).map((r, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '6px 8px' }}>
                    <span className={`risk-badge ${r.asso_enabled ? 'low' : 'high'}`}>
                      {r.asso_enabled ? 'ON' : 'OFF'}
                    </span>
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                    {new Date(r.start_time).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{r.peak_cpu?.toFixed(1)}%</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{r.peak_latency?.toFixed(0)}ms</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{r.error_count}</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{r.breach_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ComparisonView;
