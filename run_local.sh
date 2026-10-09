#!/usr/bin/env bash
set -e

FLASK_PORT=8080

echo "==> Installing Python dependencies..."
pip install -q -r requirements.txt

echo "==> Starting Flask on http://localhost:${FLASK_PORT}"
python app.py
