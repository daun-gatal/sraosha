#!/usr/bin/env bash
# Build the Vite SPA and copy the output into sraosha/web/dist for packaging and sraosha serve.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
if command -v bun >/dev/null 2>&1; then
  bun install --frozen-lockfile
  bun run build
else
  npm install
  npm run build
fi
cd "$ROOT"
rm -rf sraosha/web/dist
mkdir -p sraosha/web/dist
cp -R frontend/dist/. sraosha/web/dist/
echo "Synced frontend build to sraosha/web/dist"
