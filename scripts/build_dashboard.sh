#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
STATIC_DIR="$PROJECT_ROOT/sraosha/static/dashboard"

echo "Building dashboard..."
cd "$DASHBOARD_DIR"
bun install
bun run build

echo "Copying build output to $STATIC_DIR..."
rm -rf "$STATIC_DIR"
cp -r "$DASHBOARD_DIR/dist" "$STATIC_DIR"

echo "Dashboard built successfully."
