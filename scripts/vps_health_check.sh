#!/usr/bin/env bash
# VPS infrastructure health check — automates docs/vps/OPERATOR_RUNBOOK.md §1
# "Daily startup checks" into a single command with PASS/WARN/FAIL verdicts.
#
# Scope: host/service-level health for auto-trade-vps (systemd units, disk,
# PostgreSQL, dashboard reachability, runner tick freshness). This is
# distinct from scripts/health_check.py (app-level: broker/risk/portfolio)
# and scripts/system_health_check.py (SVOS dev-host deps/lint) — see
# docs/vps/OPERATOR_RUNBOOK.md for the full manual procedure this wraps.
#
# Exit codes: 0 HEALTHY | 2 DEGRADED (warnings only) | 1 UNHEALTHY (any FAIL)
#
# Usage: scripts/vps_health_check.sh [--json]

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="$ROOT/logs/vps_health_state.json"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8090}"
DISK_WARN_PCT="${DISK_WARN_PCT:-85}"       # per docs/vps/LOG_RETENTION_POLICY.md
HEALTH_SCORE_WARN="${HEALTH_SCORE_WARN:-85}"  # per OPERATOR_RUNBOOK §2
STALE_TICK_S="${STALE_TICK_S:-180}"
AS_JSON=0
[[ "${1:-}" == "--json" ]] && AS_JSON=1

declare -a NAMES STATUSES DETAILS
add_check() { NAMES+=("$1"); STATUSES+=("$2"); DETAILS+=("$3"); }

# 1. Services active, restarts not climbing since last run
prev_restarts_runner=0
prev_restarts_dash=0
if [[ -f "$STATE_FILE" ]]; then
  prev_restarts_runner=$(python3 -c "import json;print(json.load(open('$STATE_FILE')).get('runner_restarts',0))" 2>/dev/null || echo 0)
  prev_restarts_dash=$(python3 -c "import json;print(json.load(open('$STATE_FILE')).get('dashboard_restarts',0))" 2>/dev/null || echo 0)
fi

for unit in smc-demo-runner.service live-dashboard.service; do
  info=$(systemctl show "$unit" -p NRestarts,ActiveState,SubState 2>/dev/null)
  restarts=$(echo "$info" | sed -n 's/NRestarts=//p')
  active=$(echo "$info" | sed -n 's/ActiveState=//p')
  substate=$(echo "$info" | sed -n 's/SubState=//p')
  restarts=${restarts:-unknown}
  if [[ "$active" != "active" || "$substate" != "running" ]]; then
    add_check "service:$unit" "FAIL" "ActiveState=$active SubState=$substate"
    continue
  fi
  prev=$prev_restarts_runner
  [[ "$unit" == "live-dashboard.service" ]] && prev=$prev_restarts_dash
  if [[ "$restarts" =~ ^[0-9]+$ && "$prev" =~ ^[0-9]+$ && "$restarts" -gt "$prev" ]]; then
    add_check "service:$unit" "WARN" "NRestarts=$restarts climbing (was $prev last run)"
  else
    add_check "service:$unit" "PASS" "active/running, NRestarts=$restarts"
  fi
done

# 2. Zero failed units platform-wide
failed=$(systemctl --failed --no-legend --no-pager 2>/dev/null | wc -l)
if [[ "$failed" -gt 0 ]]; then
  add_check "systemd:failed_units" "FAIL" "$failed failed unit(s)"
else
  add_check "systemd:failed_units" "PASS" "0 failed units"
fi

# 3. PostgreSQL healthy
pg_active=$(systemctl is-active postgresql@16-main.service 2>/dev/null)
if [[ "$pg_active" != "active" ]]; then
  add_check "postgres:service" "FAIL" "postgresql@16-main.service is $pg_active"
elif sudo -u postgres psql -c "SELECT 1" >/dev/null 2>&1; then
  add_check "postgres:service" "PASS" "active, SELECT 1 ok"
else
  add_check "postgres:service" "FAIL" "active but SELECT 1 failed"
fi

# 4. Dashboard responds + operations health score
http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$DASHBOARD_URL/" 2>/dev/null)
if [[ "$http_code" != "200" && "$http_code" != "307" ]]; then
  add_check "dashboard:http" "FAIL" "HTTP $http_code from $DASHBOARD_URL/"
else
  add_check "dashboard:http" "PASS" "HTTP $http_code"
fi

health_json=$(curl -s --max-time 5 "$DASHBOARD_URL/api/operations/health" 2>/dev/null)
health_score=$(echo "$health_json" | python3 -c "import json,sys
try:
    print(json.load(sys.stdin)['data']['health_score'])
except Exception:
    print('')" 2>/dev/null)
if [[ -z "$health_score" ]]; then
  add_check "dashboard:health_score" "FAIL" "could not read /api/operations/health"
elif [[ "$health_score" -lt "$HEALTH_SCORE_WARN" ]]; then
  add_check "dashboard:health_score" "WARN" "health_score=$health_score (< $HEALTH_SCORE_WARN)"
else
  add_check "dashboard:health_score" "PASS" "health_score=$health_score"
fi

# 5. Runner ticking (not stale), broker connected
state_file="$ROOT/logs/strategy_demo_state.json"
if [[ -f "$state_file" ]]; then
  read -r last_tick broker_status strategy <<<"$(python3 - "$state_file" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    d = json.load(handle)
print(d.get("last_tick_at", ""), d.get("broker_status", ""), d.get("strategy", ""))
PY
  )"
  if [[ -z "$last_tick" ]]; then
    add_check "runner:tick" "FAIL" "could not parse $state_file"
  else
    age_s=$(python3 - "$last_tick" <<'PY'
import datetime
import sys
try:
    t = datetime.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00'))
    now = datetime.datetime.now(datetime.timezone.utc)
    print(int((now - t).total_seconds()))
except Exception:
    print(-1)
PY
    )
    if [[ "$age_s" -lt 0 ]]; then
      add_check "runner:tick" "FAIL" "unparseable last_tick_at=$last_tick"
    elif [[ "$age_s" -gt "$STALE_TICK_S" ]]; then
      add_check "runner:tick" "WARN" "last tick ${age_s}s ago (> ${STALE_TICK_S}s), strategy=$strategy"
    else
      add_check "runner:tick" "PASS" "last tick ${age_s}s ago, strategy=$strategy"
    fi
  fi
  if [[ "$broker_status" != "connected" ]]; then
    add_check "runner:broker" "FAIL" "broker_status=$broker_status"
  else
    add_check "runner:broker" "PASS" "broker_status=connected"
  fi
else
  add_check "runner:tick" "WARN" "$state_file not found"
fi

# 6. Disk headroom
disk_pct=$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')
if [[ "$disk_pct" -ge "$DISK_WARN_PCT" ]]; then
  add_check "disk:root" "WARN" "${disk_pct}% used (>= ${DISK_WARN_PCT}% alert threshold)"
else
  add_check "disk:root" "PASS" "${disk_pct}% used"
fi

# ── Verdict ──────────────────────────────────────────────────────────────────
overall="HEALTHY"
for s in "${STATUSES[@]}"; do
  [[ "$s" == "FAIL" ]] && overall="UNHEALTHY" && break
  [[ "$s" == "WARN" && "$overall" == "HEALTHY" ]] && overall="DEGRADED"
done

# Persist restart counts for next run's "climbing" comparison
runner_restarts=$(systemctl show smc-demo-runner.service -p NRestarts --value 2>/dev/null)
dash_restarts=$(systemctl show live-dashboard.service -p NRestarts --value 2>/dev/null)
mkdir -p "$(dirname "$STATE_FILE")"
python3 -c "
import json
json.dump({'runner_restarts': int('$runner_restarts' or 0), 'dashboard_restarts': int('$dash_restarts' or 0)}, open('$STATE_FILE', 'w'))
" 2>/dev/null

if [[ "$AS_JSON" -eq 1 ]]; then
  python3 -c "
import json, sys
names = json.loads(sys.argv[1])
statuses = json.loads(sys.argv[2])
details = json.loads(sys.argv[3])
print(json.dumps({
    'overall': sys.argv[4],
    'checks': [{'name': n, 'status': s, 'detail': d} for n, s, d in zip(names, statuses, details)],
}, indent=2))
" "$(python3 -c "import json,sys;print(json.dumps(sys.argv[1:]))" "${NAMES[@]}")" \
  "$(python3 -c "import json,sys;print(json.dumps(sys.argv[1:]))" "${STATUSES[@]}")" \
  "$(python3 -c "import json,sys;print(json.dumps(sys.argv[1:]))" "${DETAILS[@]}")" \
  "$overall"
else
  echo
  echo "VPS HEALTH CHECK — $(date -u +'%Y-%m-%d %H:%M UTC')"
  echo "================================================================"
  for i in "${!NAMES[@]}"; do
    icon="✓"
    [[ "${STATUSES[$i]}" == "WARN" ]] && icon="~"
    [[ "${STATUSES[$i]}" == "FAIL" ]] && icon="✗"
    printf "  %-28s %s %-6s %s\n" "${NAMES[$i]}" "$icon" "${STATUSES[$i]}" "${DETAILS[$i]}"
  done
  echo "================================================================"
  echo "  Overall: $overall"
  echo
fi

case "$overall" in
  HEALTHY) exit 0 ;;
  DEGRADED) exit 2 ;;
  *) exit 1 ;;
esac
