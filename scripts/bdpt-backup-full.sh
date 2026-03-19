#!/bin/bash
# BDPT Full Backup — runs nightly at 4:00 AM via cron
# Full sync to NVMe 2 + TrueNAS with DB snapshot retention
#
# Cron: 0 4 * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-full.sh

set -uo pipefail

APP_DIR="/home/joemack/best-decision-business-apps/best-decision-project-tools"
DB_PATH="$APP_DIR/instance/bdb_tools.db"
LOG_DIR="$APP_DIR/scripts/logs"
LOG_FILE="$LOG_DIR/backup-$(date +%Y%m%d).log"

NVME2="/media/joemack/AI-Backup 2/bdpt-backups"
NVME2_MOUNT="/media/joemack/AI-Backup 2"

TRUENAS_IP="10.48.0.11"
TRUENAS_SHARE="//10.48.0.11/Backups"
TRUENAS_MOUNT="/mnt/truenas-bdpt"
TRUENAS_CREDS="/home/joemack/.smbcredentials-truenas"

SNAPSHOT_RETAIN_DAYS=7
DELETED_RETAIN_DAYS=30
LOG_RETAIN_DAYS=30

SNAP_DATE=$(date +%Y%m%d_%H%M%S)
DB_SNAPSHOT="$APP_DIR/instance/bdb_tools_snapshot_${SNAP_DATE}.db"
ERRORS=0
TRUENAS_MOUNTED_BY_US=0
NTFY_TOPIC="bdpt-backup-6uidbOprDudpqNE"

# --- Logging ---
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

notify() {
    local TITLE="$1"
    local MSG="$2"
    local PRIORITY="${3:-4}"
    local TAGS="${4:-warning}"
    curl -s -H "Title: $TITLE" -H "Priority: $PRIORITY" -H "Tags: $TAGS" \
        -d "$MSG" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
}

log "===== BDPT FULL BACKUP STARTED ====="

# --- Step 1: SQLite safe backup ---
log "Step 1: Creating SQLite snapshot..."

sqlite3 "$DB_PATH" ".backup '$DB_SNAPSHOT'"
if [ $? -ne 0 ]; then
    log "ERROR: sqlite3 .backup failed!"
    ERRORS=$((ERRORS + 1))
else
    DB_SIZE=$(du -sh "$DB_SNAPSHOT" 2>/dev/null | cut -f1)
    log "OK: DB snapshot created ($DB_SIZE)"
fi

# --- Sync function ---
sync_to_target() {
    local TARGET="$1"
    local LABEL="$2"
    local EXTRA_RSYNC_OPTS="${3:-}"

    if [ ! -d "$TARGET" ]; then
        log "ERROR: $LABEL - $TARGET directory missing (run setup-backup.sh)"
        return 1
    fi

    log "Syncing to $LABEL..."

    # Create directory structure
    local TODAY=$(date +%Y-%m-%d)
    mkdir -p "$TARGET/current/app/instance"
    mkdir -p "$TARGET/snapshots"
    mkdir -p "$TARGET/deleted/$TODAY"

    # Rsync entire app — deleted files moved to dated trash folder (30-day retention)
    rsync -a --delete --backup --backup-dir="$TARGET/deleted/$TODAY" \
        --exclude='.git' --exclude='scripts/logs' $EXTRA_RSYNC_OPTS \
        "$APP_DIR/" "$TARGET/current/app/" >> "$LOG_FILE" 2>&1

    # Prune deleted files older than retention period
    find "$TARGET/deleted/" -mindepth 1 -maxdepth 1 -type d -mtime +$DELETED_RETAIN_DAYS \
        -exec rm -rf {} \; 2>> "$LOG_FILE"

    # Copy safe DB snapshot over the rsync'd copy (atomic, no WAL corruption)
    if [ -f "$DB_SNAPSHOT" ]; then
        cp -f "$DB_SNAPSHOT" "$TARGET/current/app/instance/bdb_tools.db" 2>> "$LOG_FILE"
        cp -f "$DB_SNAPSHOT" "$TARGET/snapshots/bdb_tools_${SNAP_DATE}.db" 2>> "$LOG_FILE"
    fi

    # Prune old DB snapshots
    find "$TARGET/snapshots/" -name "bdb_tools_*.db" -mtime +$SNAPSHOT_RETAIN_DAYS -delete 2>> "$LOG_FILE"

    # Log sizes
    local TOTAL_SIZE
    TOTAL_SIZE=$(du -sh "$TARGET/current/" 2>/dev/null | cut -f1)
    local SNAP_COUNT
    SNAP_COUNT=$(find "$TARGET/snapshots/" -name "bdb_tools_*.db" 2>/dev/null | wc -l)
    local DELETED_SIZE
    DELETED_SIZE=$(du -sh "$TARGET/deleted/" 2>/dev/null | cut -f1)
    log "OK: $LABEL sync complete (current: $TOTAL_SIZE, snapshots: $SNAP_COUNT, deleted: ${DELETED_SIZE:-0})"

    return 0
}

# --- Step 2: Sync to NVMe 2 ---
log "Step 2: NVMe 2 backup..."
if mountpoint -q "$NVME2_MOUNT" 2>/dev/null; then
    sync_to_target "$NVME2" "NVMe-2 (AI Backup 2)" || ERRORS=$((ERRORS + 1))
else
    log "ERROR: NVMe 2 not mounted at $NVME2_MOUNT"
    ERRORS=$((ERRORS + 1))
fi

# --- Step 3: Sync to TrueNAS ---
log "Step 3: TrueNAS backup..."

sync_to_truenas() {
    # Connectivity check
    if ! ping -c 1 -W 3 "$TRUENAS_IP" > /dev/null 2>&1; then
        log "ERROR: TrueNAS unreachable (ping failed)"
        return 1
    fi

    # Check credentials
    if [ ! -f "$TRUENAS_CREDS" ]; then
        log "SKIP: TrueNAS credentials not found at $TRUENAS_CREDS"
        return 1
    fi

    # Mount if not already mounted
    if ! mountpoint -q "$TRUENAS_MOUNT" 2>/dev/null; then
        log "Mounting TrueNAS SMB share..."
        sudo mount -t cifs "$TRUENAS_SHARE" "$TRUENAS_MOUNT" \
            -o credentials="$TRUENAS_CREDS",uid=$(id -u),gid=$(id -g),vers=3.0,iocharset=utf8 \
            2>> "$LOG_FILE"
        if [ $? -ne 0 ]; then
            log "ERROR: TrueNAS SMB mount failed"
            return 1
        fi
        TRUENAS_MOUNTED_BY_US=1
    fi

    local TRUENAS_TARGET="$TRUENAS_MOUNT/BDBus_Apps/bdpt-backups"
    mkdir -p "$TRUENAS_TARGET" 2>> "$LOG_FILE"

    sync_to_target "$TRUENAS_TARGET" "TrueNAS" "--copy-links"
    local RESULT=$?

    # Unmount if we mounted it
    if [ "$TRUENAS_MOUNTED_BY_US" -eq 1 ]; then
        sudo umount "$TRUENAS_MOUNT" 2>> "$LOG_FILE"
        log "TrueNAS unmounted"
    fi

    return $RESULT
}

sync_to_truenas || ERRORS=$((ERRORS + 1))

# --- Step 4: Cleanup ---
log "Step 4: Cleanup..."

# Remove local temp snapshot
if [ -f "$DB_SNAPSHOT" ]; then
    rm -f "$DB_SNAPSHOT"
    log "Cleaned up local DB snapshot"
fi

# Prune old log files
find "$LOG_DIR" -name "backup-*.log" -mtime +$LOG_RETAIN_DAYS -delete 2>/dev/null

# --- Final status ---
if [ "$ERRORS" -eq 0 ]; then
    log "===== BDPT FULL BACKUP COMPLETED SUCCESSFULLY ====="
    exit 0
else
    log "===== BDPT FULL BACKUP COMPLETED WITH $ERRORS ERROR(S) ====="
    notify "BDPT Full Backup FAILED" "$ERRORS error(s) during nightly backup. Check backup-$(date +%Y%m%d).log" "5" "rotating_light"
    exit 1
fi
