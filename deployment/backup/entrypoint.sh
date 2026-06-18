#!/bin/sh
set -e

log() { printf '%s [%s] pg_backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"; }

printenv > /etc/backup.env
chmod 600 /etc/backup.env

log INFO "scheduler started (cron: $(cut -d' ' -f1-5 /etc/crontabs/root))"
exec crond -f -l 2
