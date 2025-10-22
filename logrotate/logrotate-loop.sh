#!/bin/sh
set -eu

CONF="/etc/logrotate.d/app.conf"
STATE="/var/lib/logrotate/status"

mkdir -p /var/lib/logrotate
[ -f "$STATE" ] || touch "$STATE"

echo "Starting logrotate loop for $CONF"
while true; do
  /usr/sbin/logrotate -f -v "$CONF" || true
  sleep 20
done
