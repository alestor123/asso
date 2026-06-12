#!/usr/bin/env bash
# ASSO — Stop all demo services
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.asso_pids"

echo ""
echo "  🛑 Stopping ASSO services..."

if [ -f "$PID_FILE" ]; then
    while read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo "  Stopped PID $pid"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Also kill by port as fallback
for port in 6001 6002 8000 3000; do
    pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null
        echo "  Killed process on port $port (PID $pid)"
    fi
done

echo "  ✅ All services stopped."
echo ""
