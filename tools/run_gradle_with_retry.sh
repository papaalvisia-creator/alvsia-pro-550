#!/usr/bin/env bash
set -uo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: run_gradle_with_retry.sh <gradle-command> [args...]" >&2
  exit 2
fi
max_attempts=4
cache="${GRADLE_USER_HOME:-$HOME/.gradle}/wrapper/dists"
for attempt in $(seq 1 "$max_attempts"); do
  log="$(mktemp)"
  if "$@" >"$log" 2>&1; then
    cat "$log"
    rm -f "$log"
    exit 0
  fi
  cat "$log"
  if [[ "$attempt" -lt "$max_attempts" ]] && grep -Eiq 'HTTP response code: (429|500|502|503|504)|Connection reset|timed out|UnknownHostException|Temporary failure in name resolution' "$log"; then
    echo "Transient Gradle/network failure; retry $((attempt + 1))/$max_attempts."
    rm -f "$log"
    if [[ -d "$cache" ]]; then
      find "$cache" -type f \( -name '*.part' -o -name '*.lck' \) -delete 2>/dev/null || true
    fi
    sleep "$((attempt * 10))"
    continue
  fi
  rm -f "$log"
  exit 1
done
exit 1
