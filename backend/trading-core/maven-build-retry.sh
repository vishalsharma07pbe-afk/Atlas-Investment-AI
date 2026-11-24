#!/bin/sh
# Retry only Maven artifact transfer rate limiting. Compilation/test errors
# and all other errors propagate immediately. Never change dependency versions.
set -eu
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
attempt=1
delay=20
while :; do
  if mvn -B -ntp -U "$@" >"$log" 2>&1; then
    cat "$log"
    exit 0
  else
    status=$?
  fi
  cat "$log"
  if [ "$attempt" -ge 4 ] || ! grep -Eiq 'Could not transfer artifact.*(429|Too Many Requests)|status code: 429' "$log"; then
    exit "$status"
  fi
  echo "Maven artifact transfer rate-limited; retry $attempt of 3 in ${delay}s" >&2
  sleep "$delay"
  attempt=$((attempt+1))
  delay=$((delay*2))
done
