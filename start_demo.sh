#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# ASSO — Adaptive Service Stability Orchestrator
# One-command demo launcher (no Docker required)
# ═══════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.asso_pids"
export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ⚡ ASSO — Adaptive Service Stability Orchestrator"
echo "  Starting all services..."
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Clean up any previous PIDs
if [ -f "$PID_FILE" ]; then
    echo "  Stopping previous instances..."
    bash "$SCRIPT_DIR/stop_demo.sh" 2>/dev/null || true
fi

> "$PID_FILE"

# Remove old database
rm -f "$SCRIPT_DIR/backend/asso.db"

# ── 1. Start Flask Demo App ──
echo "  [1/4] Starting Flask REST API on port 6001..."
cd "$SCRIPT_DIR/demo-apps/flask-api"
python3 app.py > /dev/null 2>&1 &
echo $! >> "$PID_FILE"
sleep 1

# ── 2. Start Node.js Demo App ──
echo "  [2/4] Starting Node.js Workload Service on port 6002..."
cd "$SCRIPT_DIR/demo-apps/node-workload"
node server.js > /dev/null 2>&1 &
echo $! >> "$PID_FILE"
sleep 1

# ── 3. Start ASSO Backend ──
echo "  [3/4] Starting ASSO Backend on port 8000..."
cd "$SCRIPT_DIR/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info > /dev/null 2>&1 &
echo $! >> "$PID_FILE"
sleep 2

# ── 4. Start Frontend Dev Server ──
echo "  [4/4] Starting Frontend Dashboard on port 3000..."
cd "$SCRIPT_DIR/frontend"
npx vite --host 0.0.0.0 --port 3000 > /dev/null 2>&1 &
echo $! >> "$PID_FILE"
sleep 2

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ All services running!"
echo ""
echo "  📊 Dashboard:    http://localhost:3000"
echo "  🔧 Backend API:  http://localhost:8000/docs"
echo "  🌐 Flask API:    http://localhost:6001/health"
echo "  📦 Node Service: http://localhost:6002/health"
echo ""
echo "  🚀 To generate load:"
echo "     python3 load-test/load_generator.py --pattern spike --max-rps 100"
echo ""
echo "  🛑 To stop:  ./stop_demo.sh"
echo "═══════════════════════════════════════════════════════════════"
echo ""
