#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# run_local.sh — Run the Thoughts Dashboard locally
#
# The PostgreSQL service is a ClusterIP inside the cluster and is not
# reachable directly from outside. This script:
#   1. Port-forwards the cluster DB to localhost:5432
#   2. Installs Python deps into a venv (first run only)
#   3. Launches the Flask app on http://localhost:8080
#   4. Cleans up the port-forward on exit (Ctrl+C)
# ---------------------------------------------------------------------------

NAMESPACE="thoughts-app"
DB_SERVICE="postgresql"
LOCAL_PORT=5432
REMOTE_PORT=5432
FLASK_PORT=8080
VENV_DIR=".venv"

# --- colours ---------------------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# --- cleanup on exit -------------------------------------------------------
PF_PID=""
cleanup() {
  echo ""
  if [[ -n "$PF_PID" ]] && kill -0 "$PF_PID" 2>/dev/null; then
    info "Stopping port-forward (pid $PF_PID)..."
    kill "$PF_PID" 2>/dev/null || true
  fi
  info "Done."
}
trap cleanup EXIT INT TERM

# --- check prerequisites ---------------------------------------------------
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    error "'$1' not found. Please install it and try again."
    exit 1
  fi
}

check_cmd python3

# Ensure pip is available, bootstrap it if not
if ! python3 -m pip --version &>/dev/null; then
  warn "pip not found — bootstrapping via ensurepip..."
  python3 -m ensurepip --upgrade
fi

# Prefer kubectl, fall back to oc
if command -v kubectl &>/dev/null; then
  KUBE_CMD="kubectl"
elif command -v oc &>/dev/null; then
  KUBE_CMD="oc"
else
  error "Neither 'kubectl' nor 'oc' found. Please install one and try again."
  exit 1
fi
info "Using '$KUBE_CMD' for cluster access"

# --- verify cluster connectivity -------------------------------------------
info "Checking cluster access..."
if ! $KUBE_CMD get namespace "$NAMESPACE" &>/dev/null; then
  error "Cannot reach namespace '$NAMESPACE'. Are you logged in to the cluster?"
  exit 1
fi

# --- start port-forward ----------------------------------------------------
# Kill any existing port-forward on the same local port
if lsof -ti tcp:"$LOCAL_PORT" &>/dev/null; then
  warn "Port $LOCAL_PORT is already in use. Attempting to free it..."
  kill "$(lsof -ti tcp:"$LOCAL_PORT")" 2>/dev/null || true
  sleep 1
fi

info "Starting port-forward: localhost:$LOCAL_PORT -> $NAMESPACE/$DB_SERVICE:$REMOTE_PORT"
$KUBE_CMD port-forward \
  -n "$NAMESPACE" \
  "svc/$DB_SERVICE" \
  "${LOCAL_PORT}:${REMOTE_PORT}" \
  &>/tmp/pf_thoughts.log &
PF_PID=$!

# Wait for the tunnel to be ready
for i in $(seq 1 10); do
  if grep -q "Forwarding from" /tmp/pf_thoughts.log 2>/dev/null; then
    info "Port-forward established (pid $PF_PID)"
    break
  fi
  if ! kill -0 "$PF_PID" 2>/dev/null; then
    error "Port-forward process died. Log:"
    cat /tmp/pf_thoughts.log >&2
    exit 1
  fi
  sleep 0.5
done

# --- set up Python venv ----------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating Python virtual environment in $VENV_DIR ..."
  python3 -m venv "$VENV_DIR"
fi

info "Installing dependencies from requirements.txt ..."
python3 -m pip install --quiet --upgrade pip
"$VENV_DIR/bin/python" -m pip install --quiet -r requirements.txt

# --- launch Flask ----------------------------------------------------------
info "Starting Flask dashboard on http://localhost:$FLASK_PORT"
echo ""
echo -e "  ${GREEN}Open in browser:${NC} http://localhost:$FLASK_PORT"
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop."
echo ""

export DB_HOST=localhost
export DB_PORT=$LOCAL_PORT
export DB_NAME=thoughts
export DB_USER=thoughts
export DB_PASSWORD=thoughts123

"$VENV_DIR/bin/python" app.py
