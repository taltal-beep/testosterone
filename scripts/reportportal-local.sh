#!/usr/bin/env bash
# ReportPortal local stack helpers for testo validation.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose-rp.yml"
COMPOSE=(docker compose -f "${COMPOSE_FILE}" --profile core)
TOKEN="testo-local-validation_ERERERERQRGBEREREREREV2jef5txhXfGyP3Fw17h7wSbX5dgz7RhFB1P7mNawIW"
ENDPOINT="http://localhost:8080"
PROJECT="superadmin_personal"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  up       Start ReportPortal core stack (detached)
  down     Stop stack (keeps Postgres bind mount data)
  ps       Show service status
  logs     Tail logs (optional: service name)
  verify   Wait for health + validate API token
  reset    Stop, remove volumes, delete Postgres bind mount data

Pre-seeded API token: ${TOKEN}
Dashboard login:      superadmin / erebus
EOF
}

cmd_up() {
  mkdir -p "${ROOT}/data/reportportal/postgres"
  "${COMPOSE[@]}" up -d
  echo "ReportPortal starting on ${ENDPOINT} (allow 1-2 minutes for first boot)."
  echo "Run: $(basename "$0") verify"
}

cmd_down() {
  "${COMPOSE[@]}" down
}

cmd_ps() {
  "${COMPOSE[@]}" ps -a
}

cmd_logs() {
  if [[ $# -gt 0 ]]; then
    "${COMPOSE[@]}" logs -f "$@"
  else
    "${COMPOSE[@]}" logs -f
  fi
}

wait_healthy() {
  local deadline=$((SECONDS + 180))
  echo "Waiting for core services to become healthy (up to 180s)..."
  while (( SECONDS < deadline )); do
    local unhealthy
    unhealthy="$("${COMPOSE[@]}" ps --format json 2>/dev/null | python3 -c "
import json, sys
rows = [json.loads(line) for line in sys.stdin if line.strip()]
core = {'gateway', 'postgresql', 'rabbitmq', 'service-api', 'service-uaa', 'service-ui', 'jobs', 'index'}
bad = []
for r in rows:
    name = r.get('Service', '')
    if name not in core:
        continue
    state = (r.get('Health') or r.get('State') or '').lower()
    if 'unhealthy' in state or r.get('State') == 'exited':
        bad.append(name)
print(','.join(bad))
" 2>/dev/null || echo "pending")"
    if [[ -z "${unhealthy}" || "${unhealthy}" == "pending" ]]; then
      if curl -sf "${ENDPOINT}/health" >/dev/null 2>&1; then
        echo "Gateway health OK."
        return 0
      fi
    fi
    sleep 5
  done
  echo "Timed out waiting for healthy services. Check: $(basename "$0") ps" >&2
  return 1
}

cmd_verify() {
  wait_healthy
  echo "Checking ${ENDPOINT}/health ..."
  curl -sf "${ENDPOINT}/health" | head -c 200 || true
  echo ""
  echo "Checking API token against project ${PROJECT} ..."
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${ENDPOINT}/api/v1/${PROJECT}/launch?page.size=1")"
  if [[ "${code}" == "200" ]]; then
    echo "OK: API token accepted (HTTP ${code})."
    echo ""
    echo "Run tests:"
    echo "  export REPORTPORTAL_TOKEN=${TOKEN}"
    echo "  testo run --cycle sample-pytests"
    return 0
  fi
  echo "FAIL: expected HTTP 200, got ${code}. Logs: $(basename "$0") logs token-seed service-api service-uaa" >&2
  return 1
}

cmd_reset() {
  "${COMPOSE[@]}" down -v 2>/dev/null || true
  rm -rf "${ROOT}/data/reportportal/postgres"
  echo "Reset complete. Run: $(basename "$0") up"
}

main() {
  local cmd="${1:-}"
  shift || true
  case "${cmd}" in
    up) cmd_up "$@" ;;
    down) cmd_down "$@" ;;
    ps) cmd_ps "$@" ;;
    logs) cmd_logs "$@" ;;
    verify) cmd_verify "$@" ;;
    reset) cmd_reset "$@" ;;
    -h|--help|help|"") usage ;;
    *)
      echo "Unknown command: ${cmd}" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
