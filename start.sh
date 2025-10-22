#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/logs /var/lib/logrotate

# Start processes
python -u /app/log_generator.py & APP_PID=$!
/usr/local/bin/logrotate-loop.sh & ROT_PID=$!
/otelcol-contrib --config /etc/otelcol/config.yaml & COL_PID=$!

echo "Started: app=$APP_PID, logrotate=$ROT_PID, collector=$COL_PID"

# Forward TERM/INT to children
term() {
  echo "Shutting down..."
  kill -TERM "$APP_PID" "$ROT_PID" "$COL_PID" 2>/dev/null || true
  wait || true
}
trap term TERM INT

# If any process exits, exit non-zero so the container restarts
wait -n "$APP_PID" "$ROT_PID" "$COL_PID"
echo "A child process exited; stopping others..."
term
exit 1
