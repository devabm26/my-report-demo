#!/usr/bin/env bash
set -e

# ── Config ────────────────────────────────────────────────────────────────────
DB_HOST="postgresql.thoughts-app.svc.cluster.local"
DB_PORT=5432
LOCAL_PORT=5432
FLASK_PORT=8080
VENV_DIR=".venv"
PF_PID_FILE=".port-forward.pid"

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
error() { echo "[ERROR] $*" >&2; }

cleanup() {
  if [[ -f "$PF_PID_FILE" ]]; then
    PF_PID=$(cat "$PF_PID_FILE")
    if kill -0 "$PF_PID" 2>/dev/null; then
      info "Stopping port-forward (pid $PF_PID)..."
      kill "$PF_PID" 2>/dev/null || true
    fi
    rm -f "$PF_PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

# ── 1. Check kubectl / oc ─────────────────────────────────────────────────────
if command -v oc &>/dev/null; then
  KUBE_CMD="oc"
elif command -v kubectl &>/dev/null; then
  KUBE_CMD="kubectl"
else
  error "Neither 'oc' nor 'kubectl' found. Make sure you are logged in to the cluster."
  exit 1
fi
info "Using '$KUBE_CMD' for cluster access."

# ── 2. Verify cluster access ───────────────────────────────────────────────────
if ! $KUBE_CMD get svc postgresql -n thoughts-app &>/dev/null; then
  warn "Cannot find service 'postgresql' in namespace 'thoughts-app'."
  warn "Continuing anyway — the DB host may already be resolvable in this environment."
else
  info "Found postgresql service in thoughts-app namespace."
fi

# ── 3. Port-forward if DB hostname is not directly reachable ──────────────────
if ! getent hosts "$DB_HOST" &>/dev/null 2>&1; then
  info "DB host '$DB_HOST' is not directly resolvable — starting port-forward..."

  # Check if local port is already in use
  if lsof -i ":$LOCAL_PORT" &>/dev/null 2>&1; then
    warn "Port $LOCAL_PORT already in use — assuming a port-forward is already running."
  else
    $KUBE_CMD port-forward svc/postgresql "$LOCAL_PORT:$DB_PORT" -n thoughts-app &
    PF_PID=$!
    echo "$PF_PID" > "$PF_PID_FILE"
    info "Port-forward started (pid $PF_PID). Waiting for it to be ready..."
    sleep 2

    if ! kill -0 "$PF_PID" 2>/dev/null; then
      error "Port-forward process died immediately. Check your cluster login and namespace."
      exit 1
    fi
  fi

  # Patch DB host so Flask connects via localhost
  export PGHOST_OVERRIDE="127.0.0.1"
else
  info "DB host '$DB_HOST' is directly reachable (in-cluster environment)."
fi

# ── 4. Python virtual environment ─────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

info "Activating virtual environment..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

info "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── 5. Apply host override if port-forwarding ─────────────────────────────────
if [[ -n "${PGHOST_OVERRIDE:-}" ]]; then
  info "Patching app to use 127.0.0.1 instead of cluster hostname for this run..."
  export FLASK_DB_HOST="127.0.0.1"
fi

# ── 6. Start Flask ────────────────────────────────────────────────────────────
info "Starting Flask on port $FLASK_PORT..."
info "Open: http://localhost:$FLASK_PORT"
echo ""

FLASK_DB_HOST="${FLASK_DB_HOST:-$DB_HOST}" \
FLASK_RUN_HOST="0.0.0.0" \
FLASK_RUN_PORT="$FLASK_PORT" \
python3 -c "
import os, app as a
a.DB_CONFIG['host'] = os.environ.get('FLASK_DB_HOST', a.DB_CONFIG['host'])
a.app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_RUN_PORT', 8080)), debug=False)
"
