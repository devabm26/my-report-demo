#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing dependencies..."
pip install -q -r requirements.txt

echo "==> Starting Flask dashboard on http://localhost:8080 ..."
python app.py
