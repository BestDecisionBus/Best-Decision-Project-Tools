#!/bin/bash
# BDPT Backup Morning Report — daily at 10:00 AM
# Sends a summary of all backup targets to ntfy
#
# Cron: 0 10 * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-morning-report.sh

set -uo pipefail

NVME1_DB="/media/joemack/AI-Backup/bdpt-backups/current/app/instance/bdb_tools.db"
NVME2_DB="/media/joemack/AI-Backup 2/bdpt-backups/current/app/instance/bdb_tools.db"
NVME2_SNAPS="/media/joemack/AI-Backup 2/bdpt-backups/snapshots"
NTFY_TOPIC="bdpt-backup-6uidbOprDudpqNE"

STATUS="OK"
REPORT=""

# --- NVMe 1 (quick backup) ---
if [ -f "$NVME1_DB" ]; then
    AGE_MIN=$(( ($(date +%s) - $(stat -c %Y "$NVME1_DB")) / 60 ))
    SIZE=$(du -sh "$NVME1_DB" 2>/dev/null | cut -f1)
    if [ "$AGE_MIN" -le 30 ]; then
        REPORT="NVMe 1 (quick): OK - ${AGE_MIN}m ago (${SIZE})"
    else
        REPORT="NVMe 1 (quick): STALE - ${AGE_MIN}m ago"
        STATUS="ISSUES"
    fi
else
    REPORT="NVMe 1 (quick): MISSING"
    STATUS="ISSUES"
fi

# --- NVMe 2 (nightly backup) ---
if [ -f "$NVME2_DB" ]; then
    AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$NVME2_DB")) / 3600 ))
    SIZE=$(du -sh "/media/joemack/AI-Backup 2/bdpt-backups/current/app/" 2>/dev/null | cut -f1)
    SNAP_COUNT=$(find "$NVME2_SNAPS" -name "bdb_tools_*.db" 2>/dev/null | wc -l)
    if [ "$AGE_HOURS" -le 26 ]; then
        REPORT="${REPORT}
NVMe 2 (nightly): OK - ${AGE_HOURS}h ago (${SIZE}, ${SNAP_COUNT} snapshots)"
    else
        REPORT="${REPORT}
NVMe 2 (nightly): STALE - ${AGE_HOURS}h ago"
        STATUS="ISSUES"
    fi
else
    REPORT="${REPORT}
NVMe 2 (nightly): MISSING"
    STATUS="ISSUES"
fi

# --- TrueNAS (check last nightly log) ---
LOG_FILE="/home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/logs/backup-$(date +%Y%m%d).log"
if [ -f "$LOG_FILE" ] && grep -q "TrueNAS sync complete" "$LOG_FILE"; then
    REPORT="${REPORT}
TrueNAS: OK (synced last night)"
elif [ -f "$LOG_FILE" ] && grep -q "TrueNAS" "$LOG_FILE"; then
    REPORT="${REPORT}
TrueNAS: FAILED (check backup log)"
    STATUS="ISSUES"
else
    REPORT="${REPORT}
TrueNAS: No log for today yet"
fi

# --- Send ---
if [ "$STATUS" = "OK" ]; then
    curl -s -H "Title: BDPT Backups - All Good" -H "Priority: 3" -H "Tags: white_check_mark" \
        -d "$REPORT" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1
else
    curl -s -H "Title: BDPT Backups - Issues Found" -H "Priority: 4" -H "Tags: warning" \
        -d "$REPORT" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1
fi
