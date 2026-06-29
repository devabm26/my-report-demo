#!/usr/bin/env bash
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
NAMESPACE="thoughts-app"
DB_SERVICE="postgresql"
DB_PORT=5432
LOCAL_PORT=5433          # local port forwarded to the cluster DB
FLASK_PORT=8080
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PF_PID_FILE="/tmp/pf-thoughts-db.pid"

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

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

# ── Detect CLI (oc preferred, kubectl fallback) ────────────────────────────────
if command -v oc &>/dev/null; then
  KUBE_CLI="oc"
elif command -v kubectl &>/dev/null; then
  KUBE_CLI="kubectl"
else
  die "Neither 'oc' nor 'kubectl' found in PATH."
fi
info "Using CLI: $KUBE_CLI"

# ── Verify cluster access ──────────────────────────────────────────────────────
$KUBE_CLI get svc "$DB_SERVICE" -n "$NAMESPACE" &>/dev/null \
  || die "Cannot reach service '$DB_SERVICE' in namespace '$NAMESPACE'. Are you logged in?"

# ── Port-forward DB ────────────────────────────────────────────────────────────
info "Port-forwarding $DB_SERVICE:$DB_PORT -> localhost:$LOCAL_PORT ..."
$KUBE_CLI port-forward "svc/$DB_SERVICE" "${LOCAL_PORT}:${DB_PORT}" \
  -n "$NAMESPACE" &>/tmp/pf-thoughts-db.log &
echo $! > "$PF_PID_FILE"

# Wait until the local port is actually open (max 15 s)
for i in $(seq 1 15); do
  if bash -c "echo > /dev/tcp/127.0.0.1/$LOCAL_PORT" 2>/dev/null; then
    info "Port-forward ready."
    break
  fi
  sleep 1
  [[ $i -eq 15 ]] && { cat /tmp/pf-thoughts-db.log; die "Port-forward timed out."; }
done

# ── Python venv + deps ────────────────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

info "Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

# ── Override DB connection to use the local port-forward ──────────────────────
export DB_HOST=127.0.0.1
export DB_PORT=$LOCAL_PORT
export DB_NAME=thoughts
export DB_USER=thoughts
export DB_PASSWORD=thoughts123

# ── Launch Flask ───────────────────────────────────────────────────────────────
info "Starting Flask on http://localhost:$FLASK_PORT ..."
info "Press Ctrl+C to stop."
"$VENV_DIR/bin/python" "$SCRIPT_DIR/app.py"
