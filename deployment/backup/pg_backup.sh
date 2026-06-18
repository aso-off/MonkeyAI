#!/bin/sh
set -eu

ENVFILE=/etc/backup.env
val() { grep -E "^$1=" "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2-; }

PGHOST="$(val POSTGRES_HOST)"; PGHOST="${PGHOST:-postgres}"
PGUSER="$(val POSTGRES_USER)"
PGPASSWORD="$(val POSTGRES_PASSWORD)"
export PGPASSWORD

R2_BUCKET="$(val R2_BUCKET)"
R2_ENDPOINT="$(val R2_ENDPOINT)"
R2_KEY="$(val R2_ACCESS_KEY_ID)"
R2_SECRET="$(val R2_SECRET_ACCESS_KEY)"

DATE="$(date +%Y-%m-%d_%H%M)"
FILE="monkey-${DATE}.sql.gz"
DEST="/backups/${FILE}"

mkdir -p /backups
echo "[pg_backup] dump start $(date -Iseconds)"

# весь кластер сразу: monkey_db + umami + роли
pg_dumpall -h "$PGHOST" -U "$PGUSER" | gzip -9 > "/tmp/${FILE}"

# локально храним одну копию
rm -f /backups/monkey-*.sql.gz
mv "/tmp/${FILE}" "$DEST"
echo "[pg_backup] local: $DEST ($(du -h "$DEST" | cut -f1))"

if [ -n "$R2_KEY" ] && [ -n "$R2_SECRET" ]; then
  # checksum-флаги — aws-cli v2 иначе ломает загрузку в R2
  AWS_ACCESS_KEY_ID="$R2_KEY" \
  AWS_SECRET_ACCESS_KEY="$R2_SECRET" \
  AWS_DEFAULT_REGION=auto \
  AWS_REQUEST_CHECKSUM_CALCULATION=when_required \
  AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
  aws s3 cp "$DEST" "s3://${R2_BUCKET}/${FILE}" --endpoint-url "$R2_ENDPOINT"
  echo "[pg_backup] uploaded to R2: ${R2_BUCKET}/${FILE}"
else
  echo "[pg_backup] R2 creds missing — offsite upload skipped"
fi

echo "[pg_backup] done $(date -Iseconds)"
