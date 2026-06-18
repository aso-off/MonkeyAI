#!/bin/sh
set -eu

log()  { printf '%s [%s] pg_backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"; }
fail() { log ERROR "$1"; exit 1; }

val() { grep -E "^$1=" /etc/backup.env 2>/dev/null | head -1 | cut -d= -f2-; }

PGHOST="$(val POSTGRES_HOST)"; PGHOST="${PGHOST:-postgres}"
PGUSER="$(val POSTGRES_USER)"
PGPASSWORD="$(val POSTGRES_PASSWORD)"; export PGPASSWORD
R2_BUCKET="$(val R2_BUCKET)"
R2_ENDPOINT="$(val R2_ENDPOINT)"
R2_KEY="$(val R2_ACCESS_KEY_ID)"
R2_SECRET="$(val R2_SECRET_ACCESS_KEY)"

[ -n "$PGUSER" ]     || fail "POSTGRES_USER not set"
[ -n "$PGPASSWORD" ] || fail "POSTGRES_PASSWORD not set"

START="$(date +%s)"
NAME="monkey-$(date +%Y-%m-%d_%H%M)"
DEST="/backups/${NAME}.sql.gz"
mkdir -p /backups

log INFO "dump started"
pg_dumpall -h "$PGHOST" -U "$PGUSER" > "/tmp/${NAME}.sql" || fail "pg_dumpall failed"
gzip -9 "/tmp/${NAME}.sql" || fail "gzip failed"

rm -f /backups/monkey-*.sql.gz
mv "/tmp/${NAME}.sql.gz" "$DEST"
log INFO "local snapshot saved: $DEST ($(du -h "$DEST" | cut -f1))"

if [ -n "$R2_KEY" ] && [ -n "$R2_SECRET" ]; then
  AWS_ACCESS_KEY_ID="$R2_KEY" \
  AWS_SECRET_ACCESS_KEY="$R2_SECRET" \
  AWS_DEFAULT_REGION=auto \
  AWS_REQUEST_CHECKSUM_CALCULATION=when_required \
  AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
  aws s3 cp "$DEST" "s3://${R2_BUCKET}/${NAME}.sql.gz" \
    --endpoint-url "$R2_ENDPOINT" --only-show-errors || fail "R2 upload failed"
  log INFO "uploaded to R2: ${R2_BUCKET}/${NAME}.sql.gz"
else
  log WARN "R2 credentials missing - offsite upload skipped"
fi

log INFO "completed in $(( $(date +%s) - START ))s"
