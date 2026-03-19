#!/bin/bash
# BDPT Backup Health Check — runs hourly via cron
# Alerts if the quick backup hasn't run in 30+ minutes
# or if the nightly backup is missing/stale
#
# Cron: 30 * * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-healthcheck.sh

set -uo pipefail

NVME1_DB="/media/joemack/AI-Backup/bdpt-backups/current/app/instance/bdb_tools.db"
NVME2_DB="/media/joemack/AI-Backup 2/bdpt-backups/current/app/instance/bdb_tools.db"
NTFY_TOPIC="bdpt-backup-6uidbOprDudpqNE"
QUICK_MAX_AGE_MIN=30
NIGHTLY_MAX_AGE_HOURS=26

notify() {
    curl -s -H "Title: $1" -H "Priority: ${3:-4}" -H "Tags: ${4:-warning}" \
        -d "$2" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
}

# --- Check quick backup (NVMe 1) freshness ---
if [ -f "$NVME1_DB" ]; then
    AGE_SEC=$(( $(date +%s) - $(stat -c %Y "$NVME1_DB") ))
    AGE_MIN=$(( AGE_SEC / 60 ))
    if [ "$AGE_MIN" -gt "$QUICK_MAX_AGE_MIN" ]; then
        notify "BDPT Quick Backup Stale" \
            "Last quick backup was ${AGE_MIN} minutes ago (threshold: ${QUICK_MAX_AGE_MIN}m). Check NVMe 1 and cron." \
            "4" "clock"
    fi
else
    # Only alert if the mount point exists (drive connected but no backup)
    if mountpoint -q "/media/joemack/AI-Backup" 2>/dev/null; then
        notify "BDPT Quick Backup Missing" \
            "NVMe 1 is mounted but no backup DB found. Run setup-backup.sh or check quick backup script." \
            "4" "warning"
    fi
fi

# --- Check nightly backup (NVMe 2) freshness ---
if [ -f "$NVME2_DB" ]; then
    AGE_SEC=$(( $(date +%s) - $(stat -c %Y "$NVME2_DB") ))
    AGE_HOURS=$(( AGE_SEC / 3600 ))
    if [ "$AGE_HOURS" -gt "$NIGHTLY_MAX_AGE_HOURS" ]; then
        notify "BDPT Nightly Backup Stale" \
            "Last nightly backup was ${AGE_HOURS} hours ago (threshold: ${NIGHTLY_MAX_AGE_HOURS}h). Check NVMe 2, TrueNAS, and cron." \
            "5" "rotating_light"
    fi
fi
