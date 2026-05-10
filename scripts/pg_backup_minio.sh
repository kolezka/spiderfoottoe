#!/bin/sh
# =============================================================================
# PostgreSQL Backup to MinIO — SpiderFoot sidecar script
# =============================================================================
# Runs pg_dump on a schedule and uploads compressed backups to MinIO.
# Also cleans up backups older than BACKUP_RETENTION_DAYS.
#
# Environment variables (set by docker-compose):
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
#   MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
#   BACKUP_BUCKET          (default: sf-pg-backups)
#   BACKUP_SCHEDULE_HOURS  (default: 6)
#   BACKUP_RETENTION_DAYS  (default: 30)
# =============================================================================

set -e

SCHEDULE_HOURS="${BACKUP_SCHEDULE_HOURS:-6}"
SCHEDULE_SECS=$((SCHEDULE_HOURS * 3600))
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BUCKET="${BACKUP_BUCKET:-sf-pg-backups}"

echo "=== SpiderFoot PG Backup Sidecar ==="
echo "  Database: ${PGDATABASE}@${PGHOST}:${PGPORT}"
echo "  MinIO:    ${MINIO_ENDPOINT}"
echo "  Bucket:   ${BUCKET}"
echo "  Schedule: every ${SCHEDULE_HOURS}h"
echo "  Retention: ${RETENTION_DAYS} days"
echo "======================================"

# Locate MinIO client. The container rootfs is read-only so we cannot
# write into /usr/local/bin. Prefer the shared binary published to the
# mc-bin volume by sf-minio-init, otherwise download into /tmp (tmpfs).
if [ -x /opt/mc-share/mc ]; then
    export PATH="/opt/mc-share:$PATH"
elif ! command -v mc >/dev/null 2>&1; then
    echo "Installing MinIO client to /tmp/mc..."
    if command -v wget >/dev/null 2>&1; then
        wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc
    elif command -v curl >/dev/null 2>&1; then
        curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /tmp/mc
    else
        echo "ERROR: Cannot install mc — no shared binary and no download tool"
        exit 1
    fi
    chmod +x /tmp/mc
    export PATH="/tmp:$PATH"
fi

# Configure MinIO alias
mc alias set sfminio "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" 2>/dev/null

# Ensure bucket exists
mc mb --ignore-existing "sfminio/${BUCKET}" 2>/dev/null || true

do_backup() {
    DATE_STR=$(date -u +"%Y-%m-%d")
    TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
    FILENAME="spiderfoot_${TIMESTAMP}.sql.gz"
    TMPFILE="/tmp/${FILENAME}"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting backup..."

    # pg_dump with compression
    if pg_dump -Fc --no-owner --no-privileges | gzip > "${TMPFILE}" 2>/dev/null; then
        SIZE=$(stat -f%z "${TMPFILE}" 2>/dev/null || stat -c%s "${TMPFILE}" 2>/dev/null || echo "unknown")
        echo "  Backup created: ${FILENAME} (${SIZE} bytes)"

        # Upload to MinIO
        if mc cp "${TMPFILE}" "sfminio/${BUCKET}/daily/${DATE_STR}/${FILENAME}" 2>/dev/null; then
            echo "  Uploaded to MinIO: ${BUCKET}/daily/${DATE_STR}/${FILENAME}"
        else
            echo "  ERROR: Failed to upload to MinIO"
        fi
    else
        echo "  ERROR: pg_dump failed"
    fi

    # Cleanup temp file
    rm -f "${TMPFILE}"
}

cleanup_old_backups() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Cleaning up backups older than ${RETENTION_DAYS} days..."
    CUTOFF_DATE=$(date -u -d "-${RETENTION_DAYS} days" +"%Y-%m-%d" 2>/dev/null || \
                  date -u -v-${RETENTION_DAYS}d +"%Y-%m-%d" 2>/dev/null || \
                  echo "")

    if [ -z "${CUTOFF_DATE}" ]; then
        echo "  Skipping cleanup: date calculation not supported"
        return
    fi

    # List and remove old backup directories
    mc ls "sfminio/${BUCKET}/daily/" 2>/dev/null | while read -r line; do
        DIR_DATE=$(echo "$line" | awk '{print $NF}' | tr -d '/')
        if [ "${DIR_DATE}" \< "${CUTOFF_DATE}" ] 2>/dev/null; then
            echo "  Removing old backup: ${DIR_DATE}"
            mc rm --recursive --force "sfminio/${BUCKET}/daily/${DIR_DATE}/" 2>/dev/null || true
        fi
    done
}

# Run first backup immediately
echo "Running initial backup..."
do_backup

# Main loop: backup on schedule
while true; do
    echo "Next backup in ${SCHEDULE_HOURS} hours..."
    sleep "${SCHEDULE_SECS}"
    do_backup
    cleanup_old_backups
done
