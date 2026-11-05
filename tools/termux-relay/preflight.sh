#!/data/data/com.termux/files/usr/bin/bash
# ALVSIA Termux relay preflight. Read-only: does not install, stop, or modify services.
set -u
OUT="${HOME}/alvsia-relay-preflight.txt"
{
  echo "ALVSIA TERMUX RELAY PREFLIGHT"
  date -Iseconds 2>/dev/null || date
  echo "device_arch=$(uname -m 2>/dev/null || echo unknown)"
  echo "termux_home=$HOME"
  echo
  for bin in git gh curl python python3 opencode agent-zero agent_zero zro; do
    if command -v "$bin" >/dev/null 2>&1; then
      printf '%s=%s\n' "$bin" "$(command -v "$bin")"
    else
      printf '%s=NOT_FOUND\n' "$bin"
    fi
  done
  echo
  echo "process_presence:"
  for proc in sshd opencode agent-zero agent_zero zro; do
    if pgrep -x "$proc" >/dev/null 2>&1; then
      echo "$proc=RUNNING"
    else
      echo "$proc=not-detected"
    fi
  done
  echo
  echo "local_service_probe:"
  for port in 8022 8080 3000 50001; do
    if command -v curl >/dev/null 2>&1 && curl --silent --output /dev/null --max-time 2 "http://127.0.0.1:$port/"; then
      echo "$port=http-response"
    else
      echo "$port=no-http-root-response"
    fi
  done
  echo
  echo "agent_directories:"
  for dir in "$HOME/.config/opencode" "$HOME/.opencode" "$HOME/agent-zero" "/root/agent-zero" "$HOME/.zro"; do
    [ -d "$dir" ] && echo "$dir=PRESENT" || echo "$dir=not-found"
  done
  echo
  echo "NOTE: no environment variables, credentials, SSH keys, or process command lines were collected."
} > "$OUT"
chmod 600 "$OUT"
cat "$OUT"
echo
echo "Report saved to: $OUT"
