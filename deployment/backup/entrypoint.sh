#!/bin/sh
set -e

printenv > /etc/backup.env
chmod 600 /etc/backup.env

echo "[pg_backup] crond started - расписание: четверг 11:00 (тест)"
exec crond -f -l 2
