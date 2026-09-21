#!/usr/bin/env bash
# Start or stop fakecloud for CI and local Molecule runs.
# Only scenarios listed in extensions/molecule/fakecloud_scenarios.txt need this.
set -euo pipefail

FAKECLOUD_PORT="${FAKECLOUD_PORT:-4566}"
FAKECLOUD_URL="http://127.0.0.1:${FAKECLOUD_PORT}"
# Pin the installer so CI does not query GitHub's unauthenticated
# /releases/latest API, which 403s under parallel Molecule jobs.
FAKECLOUD_VERSION="${FAKECLOUD_VERSION:-v0.44.10}"
RUNNER_DIR="${RUNNER_TEMP:-/tmp}"
PIDFILE="${RUNNER_DIR}/fakecloud.pid"
LOGFILE="${RUNNER_DIR}/fakecloud.log"

start_fakecloud() {
  if ! command -v fakecloud >/dev/null 2>&1; then
    curl -fsSL https://fakecloud.dev/install.sh | bash -s -- --version "${FAKECLOUD_VERSION}"
  fi

  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "fakecloud already running (pid $(cat "$PIDFILE"))"
    return 0
  fi

  : >"$LOGFILE"
  fakecloud >"$LOGFILE" 2>&1 &
  echo "$!" >"$PIDFILE"

  for _ in $(seq 1 60); do
    if curl -sf "${FAKECLOUD_URL}/_fakecloud/health" >/dev/null; then
      echo "fakecloud ready at ${FAKECLOUD_URL}"
      return 0
    fi
    sleep 0.5
  done

  echo "fakecloud failed to become healthy at ${FAKECLOUD_URL}" >&2
  cat "$LOGFILE" >&2 || true
  return 1
}

stop_fakecloud() {
  if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
}

scenario_needs_fakecloud() {
  local scenario="$1"
  local registry="${2:-extensions/molecule/fakecloud_scenarios.txt}"
  [[ -f "$registry" ]] || return 1
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="$(echo "$line" | xargs)"
    [[ -z "$line" ]] && continue
    [[ "$scenario" == "$line" ]] && return 0
  done <"$registry"
  return 1
}

case "${1:-}" in
  start)
    start_fakecloud
    ;;
  stop)
    stop_fakecloud
    ;;
  needs)
    scenario_needs_fakecloud "${2:?scenario name required}" "${3:-}"
    ;;
  *)
    echo "usage: $0 {start|stop|needs <scenario> [registry]}" >&2
    exit 1
    ;;
esac
