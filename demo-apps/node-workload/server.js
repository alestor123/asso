/**
 * ASSO Demo App — Node.js Workload Service
 * A real Express.js application that ASSO monitors and controls.
 * Features CPU-intensive compute endpoints, metrics tracking, and dynamic rate limiting.
 */

const http = require('http');
const url = require('url');

// ──────────────── Metrics Tracker ────────────────

const metrics = {
  requestTimes: [],     // timestamps of recent requests
  latencies: [],        // recent latency measurements (ms)
  errors: [],           // recent error flags
  activeConnections: 0,
  totalRequests: 0,
  queueLength: 0,
  maxRps: parseInt(process.env.MAX_RPS || '1000'),
  startTime: Date.now(),
};

function recordRequest(latencyMs, isError = false) {
  const now = Date.now();
  metrics.requestTimes.push(now);
  metrics.latencies.push(latencyMs);
  metrics.errors.push(isError ? 1 : 0);
  metrics.totalRequests++;

  // Keep only last 5000 entries
  if (metrics.requestTimes.length > 5000) metrics.requestTimes = metrics.requestTimes.slice(-5000);
  if (metrics.latencies.length > 1000) metrics.latencies = metrics.latencies.slice(-1000);
  if (metrics.errors.length > 1000) metrics.errors = metrics.errors.slice(-1000);
}

function getRequestRate() {
  const now = Date.now();
  const cutoff = now - 5000; // last 5 seconds
  const count = metrics.requestTimes.filter(t => t > cutoff).length;
  return count / 5.0;
}

function getAvgLatency() {
  if (metrics.latencies.length === 0) return 0;
  const recent = metrics.latencies.slice(-50);
  return recent.reduce((a, b) => a + b, 0) / recent.length;
}

function getErrorRate() {
  if (metrics.errors.length === 0) return 0;
  const recent = metrics.errors.slice(-100);
  return recent.reduce((a, b) => a + b, 0) / recent.length;
}

function isRateLimited() {
  return getRequestRate() > metrics.maxRps;
}

// ──────────────── CPU-Intensive Work ────────────────

function fibonacci(n) {
  if (n <= 1) return n;
  let a = 0, b = 1;
  for (let i = 2; i <= n; i++) {
    [a, b] = [b, a + b];
  }
  return b;
}

function matrixMultiply(size) {
  const A = Array.from({ length: size }, () =>
    Array.from({ length: size }, () => Math.random())
  );
  const B = Array.from({ length: size }, () =>
    Array.from({ length: size }, () => Math.random())
  );
  const C = Array.from({ length: size }, () => new Array(size).fill(0));

  for (let i = 0; i < size; i++) {
    for (let j = 0; j < size; j++) {
      for (let k = 0; k < size; k++) {
        C[i][j] += A[i][k] * B[k][j];
      }
    }
  }
  return C[0][0]; // Return a single value
}

function heavyCompute(intensity, durationMs) {
  const start = Date.now();
  let result = 0;

  while (Date.now() - start < durationMs) {
    // Fibonacci computation
    result += fibonacci(intensity * 100);

    // Matrix multiplication for higher intensities
    if (intensity > 3) {
      result += matrixMultiply(Math.min(intensity * 5, 50));
    }

    // Hash-like computation
    for (let i = 0; i < intensity * 500; i++) {
      result += Math.sin(i * 0.001) * Math.cos(i * 0.002);
    }
  }

  return result;
}

// ──────────────── HTTP Server ────────────────

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        resolve(JSON.parse(body));
      } catch {
        resolve({});
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const startTime = Date.now();
  metrics.activeConnections++;

  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;
  const query = parsedUrl.query;

  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    metrics.activeConnections--;
    return;
  }

  let statusCode = 200;
  let responseBody;

  try {
    if (pathname === '/health') {
      responseBody = {
        status: 'healthy',
        service: 'node-workload',
        uptime: Math.round((Date.now() - metrics.startTime) / 1000),
        totalRequests: metrics.totalRequests,
        memoryUsage: process.memoryUsage(),
      };

    } else if (pathname === '/metrics') {
      const memUsage = process.memoryUsage();
      responseBody = {
        request_rate: Math.round(getRequestRate() * 100) / 100,
        latency_ms: Math.round(getAvgLatency() * 100) / 100,
        queue_length: metrics.queueLength,
        error_rate: Math.round(getErrorRate() * 10000) / 10000,
        active_connections: metrics.activeConnections,
        total_requests: metrics.totalRequests,
        max_rps: metrics.maxRps,
        memory_rss_mb: Math.round(memUsage.rss / 1024 / 1024 * 100) / 100,
        heap_used_mb: Math.round(memUsage.heapUsed / 1024 / 1024 * 100) / 100,
      };

    } else if (pathname === '/compute' && (req.method === 'POST' || req.method === 'GET')) {
      // Rate limiting
      if (isRateLimited()) {
        statusCode = 429;
        responseBody = { error: 'rate_limited', max_rps: metrics.maxRps };
      } else {
        const intensity = Math.min(10, Math.max(1, parseInt(query.intensity || '3')));
        const durationMs = Math.min(5000, Math.max(10, parseInt(query.duration_ms || '100')));

        metrics.queueLength++;
        const result = heavyCompute(intensity, durationMs);
        metrics.queueLength = Math.max(0, metrics.queueLength - 1);

        const actualDuration = Date.now() - startTime;
        responseBody = {
          status: 'completed',
          intensity,
          target_ms: durationMs,
          actual_ms: actualDuration,
          result: Math.round(result * 10000) / 10000,
        };
      }

    } else if (pathname === '/configure' && req.method === 'POST') {
      const body = await parseBody(req);
      if (body.max_rps !== undefined) {
        metrics.maxRps = parseInt(body.max_rps);
      }
      responseBody = {
        status: 'configured',
        action: body.action || 'unknown',
        max_rps: metrics.maxRps,
      };

    } else if (pathname === '/data') {
      const items = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        name: `Item ${i + 1}`,
        value: Math.round(Math.sin(i + 1) * 100 * 100) / 100,
        computed: fibonacci(i * 5),
      }));
      responseBody = { items, count: items.length };

    } else {
      statusCode = 404;
      responseBody = { error: 'not_found', path: pathname };
    }
  } catch (err) {
    statusCode = 500;
    responseBody = { error: 'internal_error', message: err.message };
  }

  const latencyMs = Date.now() - startTime;
  recordRequest(latencyMs, statusCode >= 400);
  metrics.activeConnections = Math.max(0, metrics.activeConnections - 1);

  res.writeHead(statusCode);
  res.end(JSON.stringify(responseBody));
});

const PORT = parseInt(process.env.PORT || '6002');
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Node.js Workload Service running on port ${PORT}`);
});
