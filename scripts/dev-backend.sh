#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
  echo "Backend virtual environment not found. Creating .venv..."
  python -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

uvicorn main:app --host 127.0.0.1 --port 8787 --reload
