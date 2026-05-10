#!/usr/bin/env bash
set -euo pipefail

echo "Checking Fahim Local Agent development environment..."

echo "\nPython:"
python --version || true

echo "\nNode:"
node --version || true

echo "\npnpm:"
pnpm --version || true

echo "\nRust:"
rustc --version || true
cargo --version || true

echo "\nDocker:"
docker --version || true

echo "\nQdrant health:"
curl -fsS http://localhost:6333/healthz || echo "Qdrant not running yet. Run: pnpm qdrant:up"

echo "\nLM Studio models endpoint:"
curl -fsS http://localhost:1234/v1/models || echo "LM Studio server not running yet. Start it from LM Studio Local Server tab."
