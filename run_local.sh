#!/usr/bin/env bash
set -e

# ── Configuration ────────────────────────────────────────────────────────────
DB_NAMESPACE="thoughts-app"
DB_SERVICE="postgresql"
DB_PORT=5432
LOCAL_PORT=5432
FLASK_PORT=8080
# ─────────────────────────────────────────────────────────────────────────────

cleanup() {
  echo ""
  echo "Stopping port-forward (PID $PF_PID)..."
  kill "$PF_PID" 2>/dev/null || true
  echo "Done."
}

# Check required tools
for cmd in kubectl python3; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: '$cmd' not found. Please install it and try again."
    exit 1
  fi
done

echo "==> Installing Python dependencies..."
pip install -q -r requirements.txt

echo "==> Starting port-forward: localhost:${LOCAL_PORT} -> ${DB_SERVICE}.${DB_NAMESPACE}:${DB_PORT}"
kubectl port-forward \
  -n "$DB_NAMESPACE" \
  "svc/${DB_SERVICE}" \
  "${LOCAL_PORT}:${DB_PORT}" &
PF_PID=$!
trap cleanup EXIT INT TERM

# Wait for the tunnel to be ready
sleep 2
if ! kill -0 "$PF_PID" 2>/dev/null; then
  echo "ERROR: port-forward failed to start. Check your kubectl context and namespace."
  exit 1
fi
echo "    Port-forward running (PID ${PF_PID})"

echo "==> Starting Flask on http://localhost:${FLASK_PORT}"
DB_HOST=localhost \
  python3 app.py
