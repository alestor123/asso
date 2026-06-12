import ServiceCard from './ServiceCard';
import MetricsChart from './MetricsChart';
import PredictionChart from './PredictionChart';
import RiskGauge from './RiskGauge';
import ActionLog from './ActionLog';

function Dashboard({ services, metrics, predictions, riskScores, actions, assoEnabled }) {
  // Get the highest-risk service
  const highestRisk = Object.entries(riskScores).reduce(
    (max, [id, data]) => (data.risk_score > (max?.risk_score || 0) ? data : max),
    null
  );

  return (
    <div className="dashboard">
      {/* Left: Service Cards */}
      <div className="services-panel">
        <div className="services-panel-title">Monitored Services</div>
        {services.length > 0 ? (
          services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              latestMetric={metrics[service.id]?.slice(-1)[0]}
              risk={riskScores[service.id]}
            />
          ))
        ) : (
          <div className="glass-card" style={{ padding: '20px' }}>
            <div className="empty-state">
              <div className="empty-state-icon">📡</div>
              <div className="empty-state-text">Waiting for services...</div>
              <div className="empty-state-hint">Start the demo apps to begin monitoring</div>
            </div>
          </div>
        )}
      </div>

      {/* Center: Charts */}
      <div className="charts-panel">
        <MetricsChart
          title="System Metrics"
          subtitle="CPU & Memory utilization across services"
          services={services}
          metrics={metrics}
          metricKeys={['cpu_percent', 'memory_percent']}
          colors={['#3b82f6', '#8b5cf6']}
          labels={['CPU %', 'Memory %']}
          yDomain={[0, 100]}
          unit="%"
        />
        <MetricsChart
          title="Application Performance"
          subtitle="Request rate & latency"
          services={services}
          metrics={metrics}
          metricKeys={['latency_ms', 'request_rate']}
          colors={['#f59e0b', '#10b981']}
          labels={['Latency (ms)', 'Request Rate (rps)']}
          unit=""
        />
        <PredictionChart
          services={services}
          metrics={metrics}
          predictions={predictions}
        />
      </div>

      {/* Right: Risk + Actions */}
      <div className="right-panel">
        <RiskGauge
          riskData={highestRisk}
          allRisks={riskScores}
        />
        <ActionLog
          actions={actions}
          assoEnabled={assoEnabled}
        />
      </div>
    </div>
  );
}

export default Dashboard;
