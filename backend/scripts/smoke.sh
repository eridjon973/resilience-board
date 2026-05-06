#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

check() {
  local path="$1"
  echo "Checking ${BASE_URL}${path}"
  curl -fsS "${BASE_URL}${path}" >/dev/null
}

check "/health"
check "/health/score"
check "/metrics/summary"
check "/db/incidents"
check "/timeline"
check "/"

echo "Smoke tests passed"
