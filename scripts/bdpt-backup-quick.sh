#!/bin/bash
# BDPT Quick Backup — runs every 15 minutes via cron
# Incremental sync of DB + user files to NVMe 1
# Max data loss: 15 minutes
#
# Cron: */15 * * * * /usr/bin/flock -n /tmp/bdpt-quick.lock /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-quick.sh

set -euo pipefail

APP_DIR="/home/joemack/best-decision-business-apps/best-decision-project-tools"
DB_PATH="$APP_DIR/instance/bdb_tools.db"
LOG_FILE="$APP_DIR/scripts/logs/quick-backup.log"
TARGET="/media/joemack/AI-Backup/bdpt-backups"
MOUNT_POINT="/media/joemack/AI-Backup"
NTFY_TOPIC="bdpt-backup-6uidbOprDudpqNE"

notify_failure() {
    curl -s -H "Title: BDPT Quick Backup FAILED" -H "Priority: 4" -H "Tags: warning" \
        -d "$1" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
}

# --- Pre-flight checks ---

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Check if NVMe 1 is mounted — skip silently if not (avoid cron mail spam)
if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: $MOUNT_POINT not mounted" >> "$LOG_FILE"
    exit 0
fi

# Check target directory exists
if [ ! -d "$TARGET" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: $TARGET missing (run setup-backup.sh)" >> "$LOG_FILE"
    exit 0
fi

# --- Rsync entire app (code + venv + data, excluding .git, backup logs, and DB) ---
mkdir -p "$TARGET/current/app/instance"
rsync -a --exclude='.git' --exclude='scripts/logs' --exclude='instance/bdb_tools.db' --exclude='instance/bdb_tools.db-wal' --exclude='instance/bdb_tools.db-shm' \
    "$APP_DIR/" "$TARGET/current/app/" 2>/dev/null || true

# --- SQLite safe backup (AFTER rsync so it's not overwritten) ---
sqlite3 "$DB_PATH" ".backup '$TARGET/current/app/instance/bdb_tools.db'"
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: sqlite3 .backup failed" >> "$LOG_FILE"
    notify_failure "SQLite .backup failed at $(date '+%Y-%m-%d %H:%M:%S'). Check quick-backup.log"
    exit 1
fi

# --- Log success (one line per run) ---
DB_SIZE=$(du -sh "$TARGET/current/app/instance/bdb_tools.db" 2>/dev/null | cut -f1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: quick backup complete (DB: ${DB_SIZE:-unknown})" >> "$LOG_FILE"

# --- Rotate log weekly (keep last 7 days of entries) ---
if [ -f "$LOG_FILE" ]; then
    LINES=$(wc -l < "$LOG_FILE")
    if [ "$LINES" -gt 700 ]; then
        tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi
