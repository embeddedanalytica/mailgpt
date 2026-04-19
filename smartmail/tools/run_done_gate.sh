#!/usr/bin/env bash
# Keep in sync with AGENTS.md#merge-bar
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=sam-app/action_link_handler python3 -m unittest discover -v -s sam-app/tests/action_link_handler -p "test_*.py"
PYTHONPATH=sam-app/email_service python3 -m unittest discover -v -s sam-app/tests/email_service -p "test_*.py"
python3 -m unittest -v sam-app/tests/e2e/test_live_endpoints.py
