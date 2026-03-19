#!/bin/bash
# BDPT Backup Setup — run once with: sudo bash scripts/setup-backup.sh
# Creates directories, sets permissions, and prints next steps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
USER="joemack"
GROUP="joemack"

NVME1="/media/$USER/AI-Backup"
NVME2="/media/$USER/AI-Backup 2"
TRUENAS_MOUNT="/mnt/truenas-bdpt"
CREDS_FILE="/home/$USER/.smbcredentials-truenas"

echo "===== BDPT Backup Setup ====="
echo ""

# --- NVMe 1 ---
if mountpoint -q "$NVME1" 2>/dev/null; then
    echo "[OK] NVMe 1 mounted at $NVME1"
    mkdir -p "$NVME1/bdpt-backups/current" "$NVME1/bdpt-backups/snapshots"
    chown -R "$USER:$GROUP" "$NVME1/bdpt-backups"
    echo "     Created $NVME1/bdpt-backups/ (owned by $USER)"
else
    echo "[WARN] NVMe 1 not mounted at $NVME1 — skipping. Mount it and re-run."
fi

echo ""

# --- NVMe 2 ---
if mountpoint -q "$NVME2" 2>/dev/null; then
    echo "[OK] NVMe 2 mounted at $NVME2"
    mkdir -p "$NVME2/bdpt-backups/current" "$NVME2/bdpt-backups/snapshots"
    chown -R "$USER:$GROUP" "$NVME2/bdpt-backups"
    echo "     Created $NVME2/bdpt-backups/ (owned by $USER)"
else
    echo "[WARN] NVMe 2 not mounted at $NVME2 — skipping. Mount it and re-run."
fi

echo ""

# --- TrueNAS mount point ---
if [ ! -d "$TRUENAS_MOUNT" ]; then
    mkdir -p "$TRUENAS_MOUNT"
    echo "[OK] Created TrueNAS mount point at $TRUENAS_MOUNT"
else
    echo "[OK] TrueNAS mount point already exists at $TRUENAS_MOUNT"
fi

echo ""

# --- SMB credentials file ---
if [ ! -f "$CREDS_FILE" ]; then
    cat > "$CREDS_FILE" <<'CRED'
username=YOUR_TRUENAS_USERNAME
password=YOUR_TRUENAS_PASSWORD
CRED
    chown "$USER:$GROUP" "$CREDS_FILE"
    chmod 600 "$CREDS_FILE"
    echo "[OK] Created SMB credentials template at $CREDS_FILE"
    echo "     >>> EDIT THIS FILE with your TrueNAS username and password <<<"
else
    echo "[OK] SMB credentials file already exists at $CREDS_FILE"
fi

echo ""

# --- Log directory ---
mkdir -p "$APP_DIR/scripts/logs"
chown -R "$USER:$GROUP" "$APP_DIR/scripts/logs"
echo "[OK] Log directory ready at $APP_DIR/scripts/logs/"

echo ""

# --- Make scripts executable ---
chmod +x "$APP_DIR/scripts/bdpt-backup-quick.sh"
chmod +x "$APP_DIR/scripts/bdpt-backup-full.sh"
echo "[OK] Backup scripts made executable"

echo ""
echo "===== Setup Complete ====="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit TrueNAS credentials:"
echo "   nano $CREDS_FILE"
echo ""
echo "2. Add sudoers entries for passwordless TrueNAS mount (run visudo):"
echo "   $USER ALL=(ALL) NOPASSWD: /usr/bin/mount -t cifs //10.48.0.11/* $TRUENAS_MOUNT *"
echo "   $USER ALL=(ALL) NOPASSWD: /usr/bin/umount $TRUENAS_MOUNT"
echo ""
echo "3. Test the SMB share name (you may need to adjust the share path):"
echo "   smbclient -L //10.48.0.11 -U YOUR_TRUENAS_USERNAME"
echo ""
echo "4. Test backup scripts manually:"
echo "   bash $APP_DIR/scripts/bdpt-backup-quick.sh"
echo "   bash $APP_DIR/scripts/bdpt-backup-full.sh"
echo ""
echo "5. Install cron entries (run: crontab -e):"
echo "   # BDPT quick backup every 15 minutes to NVMe 1"
echo "   */15 * * * * /usr/bin/flock -n /tmp/bdpt-quick.lock $APP_DIR/scripts/bdpt-backup-quick.sh"
echo "   # BDPT full nightly backup at 4:00 AM to NVMe 2 + TrueNAS"
echo "   0 4 * * * $APP_DIR/scripts/bdpt-backup-full.sh"
echo ""
