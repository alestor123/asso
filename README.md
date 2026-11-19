# ⚡ ASSO — Adaptive Service Stability Orchestrator

A **real-time infrastructure monitoring and predictive auto-scaling system** that uses ML to forecast resource exhaustion 30–90 seconds before it happens, then automatically takes corrective action.

![Dashboard](https://img.shields.io/badge/Dashboard-React-61DAFB?style=flat&logo=react) ![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi) ![ML](https://img.shields.io/badge/ML-NumPy-013243?style=flat&logo=numpy) ![DB](https://img.shields.io/badge/DB-SQLite%2FMySQL-4479A1?style=flat&logo=mysql)

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  ASSO Dashboard (React + Recharts)          Port 3000           │
│  Live graphs · Risk gauge · Action log · Before/After compare   │
└───────────────────────┬─────────────────────────────────────────┘
                        │ WebSocket + REST
┌───────────────────────┴─────────────────────────────────────────┐
│  ASSO Backend (FastAPI)                     Port 8000           │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐            │
│  │Collector │  │ ML Forecaster│  │ Orchestrator   │            │
│  │ (psutil  │→ │ (LinReg+EWMA │→ │ (Rate Limit,  │            │
│  │  +HTTP)  │  │  +Z-Score)   │  │  Throttle,    │            │
│  └──────────┘  └──────────────┘  │  Load Shed)   │            │
│       ↓                          └───────┬────────┘            │
│  ┌──────────┐                            │                     │
│  │ SQLite / │←───────────────────────────┘                     │
│  │ MySQL DB │                                                  │
│  └──────────┘                                                  │
└─────────────────────────────────────────────────────────────────┘
        ↕ collect metrics              ↕ configure rate limits
┌───────────────┐              ┌───────────────────┐
│ Flask REST API│              │ Node.js Workload  │
│   Port 6001   │              │   Port 6002       │
└───────────────┘              └───────────────────┘
```

## 🚀 Quick Start (No Docker Required)

### Prerequisites
- Python 3.10+ with pip
- Node.js 18+

### 1. Install Dependencies

```bash
# Backend dependencies
pip install fastapi uvicorn sqlalchemy aiosqlite pydantic httpx websockets flask psutil

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Start Everything

```bash
./start_demo.sh
```

This launches:
- ✅ Flask REST API on `http://localhost:6001`
- ✅ Node.js Workload Service on `http://localhost:6002`
- ✅ ASSO Backend on `http://localhost:8000`
- ✅ ASSO Dashboard on `http://localhost:3000`

### 3. Stop Everything

```bash
./stop_demo.sh
```

## 🐳 Docker Deployment

```bash
docker-compose up --build
```

## Render Deployment

The repository includes a root `Dockerfile` and `render.yaml` that package the frontend, FastAPI backend, Flask demo app, and Node workload into one Render web service.

1. Push the project to GitHub.
2. In Render, choose **New → Blueprint** and select the repository.
3. Deploy `render.yaml`.
4. Render will build the Docker image and expose the application on the generated HTTPS URL.

To deploy manually, create a Render **Web Service** using the Docker runtime and keep the Docker build context as the repository root. The health check path is `/health`.

---

## 🎬 5-Minute Live Demo Script

### Step 1: Start ASSO (30 seconds)
```bash
./start_demo.sh
```
Open dashboard at `http://localhost:3000`. Show the live metrics graphs updating in real-time with baseline data.

### Step 2: Generate Normal Traffic (30 seconds)
```bash
python3 load-test/load_generator.py --target http://localhost:6001/work --pattern steady --max-rps 20 --duration 30
```
Point out: metrics are stable, risk score is LOW (green), no actions taken.

### Step 3: Spike Attack — ASSO ON (90 seconds)
```bash
python3 load-test/load_generator.py --target http://localhost:6001/work --pattern spike --max-rps 150 --duration 90 --intensity 7
```
**Watch the dashboard:**
- CPU and latency start climbing
- ASSO's prediction line (dashed orange) projects ahead of actual
- Risk gauge turns yellow → orange → red
- Action log shows: "ASSO throttled Flask REST API — predicted CPU breach in 42s"
- After throttling: metrics stabilize, risk drops back to green

### Step 4: Toggle ASSO OFF — Same Spike (90 seconds)
Click the **ASSO toggle** in the header to disable orchestration.
```bash
python3 load-test/load_generator.py --target http://localhost:6001/work --pattern spike --max-rps 150 --duration 90 --intensity 7
```
**Watch the dashboard:**
- Metrics climb unchecked — CPU hits 90%+, latency spikes to 1000ms+
- Risk gauge goes critical (red), but no actions are taken
- Action log shows "Prediction Only" entries (no intervention)

### Step 5: Compare (30 seconds)
Click **⚖️ Compare** tab. Review side-by-side:
- ASSO ON: lower peak CPU, lower latency, fewer errors, zero breaches
- ASSO OFF: higher everything, breaches detected

### Key Talking Points
- "ASSO predicted the CPU breach 45 seconds before it happened"
- "It automatically rate-limited the service before users experienced degradation"
- "The ML model uses explainable linear regression + EWMA — no black box"
- "Every prediction is validated against actual outcomes — see the accuracy stat"

---

## 📁 Project Structure

```
asso/
├── backend/               # FastAPI backend
│   ├── main.py           # App entry point + API endpoints
│   ├── collector.py      # Real-time telemetry collector (psutil + HTTP)
│   ├── forecaster.py     # ML prediction engine
│   ├── orchestrator.py   # Automated corrective actions
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schemas.py        # Pydantic API schemas
│   ├── database.py       # Async database setup
│   ├── config.py         # Configuration
│   └── websocket_manager.py  # WebSocket broadcasting
├── frontend/              # React + Recharts dashboard
│   └── src/components/   # Dashboard, Charts, Risk Gauge, Action Log, Comparison
├── demo-apps/
│   ├── flask-api/        # Flask REST API (monitored target)
│   └── node-workload/    # Node.js workload service (monitored target)
├── load-test/
│   ├── load_generator.py # Configurable traffic generator
│   └── scenarios.json    # Pre-defined test scenarios
├── docker-compose.yml    # Full containerized deployment
├── start_demo.sh         # One-command native launcher
├── stop_demo.sh          # Clean shutdown
├── DOCUMENTATION.md      # Full technical documentation
└── README.md             # This file
```

## 📜 License

MIT
