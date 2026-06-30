import { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import ComparisonView from './components/ComparisonView';
import './App.css';
const WS_URI = 'wss://feisty-recluse-quickness.ngrok-free.dev/ws';
const API_URL = 'https://feisty-recluse-quickness.ngrok-free.dev';

function App() {
  const [view, setView] = useState('dashboard'); // dashboard | comparison
  const [services, setServices] = useState([]);
  const [metrics, setMetrics] = useState({});      // { serviceId: [metric, ...] }
  const [predictions, setPredictions] = useState({}); // { serviceId: [pred, ...] }
  const [riskScores, setRiskScores] = useState({});  // { serviceId: riskData }
  const [actions, setActions] = useState([]);
  const [assoEnabled, setAssoEnabled] = useState(true);
  const [assoStatus, setAssoStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);

  // Max data points to keep in memory per service
  const MAX_POINTS = 200;

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('[ASSO] WebSocket connected');
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('[ASSO] WebSocket disconnected, reconnecting...');
      reconnectTimeout.current = setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        // ignore parse errors
      }
    };
  }, []);

  const handleMessage = useCallback((msg) => {
    const { type, data } = msg;

    switch (type) {
      case 'init':
        setServices(data.services || []);
        setAssoEnabled(data.asso_enabled);
        break;

      case 'metric':
        setMetrics(prev => {
          const serviceId = data.service_id;
          const existing = prev[serviceId] || [];
          const updated = [...existing, { ...data, timestamp: new Date(data.timestamp) }];
          return { ...prev, [serviceId]: updated.slice(-MAX_POINTS) };
        });
        break;

      case 'prediction':
        setPredictions(prev => {
          const serviceId = data.service_id;
          const existing = prev[serviceId] || [];
          const updated = [...existing, { ...data, timestamp: new Date() }];
          return { ...prev, [serviceId]: updated.slice(-MAX_POINTS) };
        });
        break;

      case 'risk':
        setRiskScores(prev => ({
          ...prev,
          [data.service_id]: data,
        }));
        break;

      case 'action':
        setActions(prev => [...prev, { ...data, timestamp: new Date(data.timestamp) }].slice(-100));
        break;

      case 'status':
        setAssoEnabled(data.asso_enabled);
        break;

      case 'ping':
        break;

      default:
        break;
    }
  }, []);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    };
  }, [connectWebSocket]);

  // Fetch ASSO status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const resp = await fetch(`${API_URL}/api/asso/status`);
        if (resp.ok) {
          const data = await resp.json();
          setAssoStatus(data);
        }
      } catch { /* ignore */ }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch initial actions
  useEffect(() => {
    const fetchActions = async () => {
      try {
        const resp = await fetch(`${API_URL}/api/actions?limit=50`);
        if (resp.ok) {
          const data = await resp.json();
          setActions(data.map(a => ({ ...a, timestamp: new Date(a.timestamp) })));
        }
      } catch { /* ignore */ }
    };
    fetchActions();
  }, []);

  const toggleAsso = async () => {
    const newState = !assoEnabled;
    try {
      await fetch(`${API_URL}/api/asso/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newState }),
      });
      setAssoEnabled(newState);
    } catch (e) {
      console.error('Failed to toggle ASSO:', e);
    }
  };

  return (
    <div className="app">
      <Header
        connected={connected}
        assoEnabled={assoEnabled}
        assoStatus={assoStatus}
        onToggleAsso={toggleAsso}
        view={view}
        onViewChange={setView}
      />
      <main className="main-content">
        {view === 'dashboard' ? (
          <Dashboard
            services={services}
            metrics={metrics}
            predictions={predictions}
            riskScores={riskScores}
            actions={actions}
            assoEnabled={assoEnabled}
          />
        ) : (
          <ComparisonView apiUrl={API_URL} />
        )}
      </main>
    </div>
  );
}

export default App;
