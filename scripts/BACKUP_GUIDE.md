# BDPT Backup System Guide

Reusable backup setup for Flask/SQLite apps with NVMe drives and TrueNAS.

---

## Architecture

```
Every 15 min          Nightly 4:00 AM          Hourly :30           Daily 10:00 AM
    |                      |                      |                      |
Quick Backup          Full Backup           Health Check          Morning Report
    |                   /     \                   |                      |
  NVMe 1           NVMe 2   TrueNAS         Check freshness      Summary of all
(incremental)     (mirror)  (SMB mount)      Alert if stale       3 targets
```

## What Gets Backed Up

- Entire app directory (code, venv, templates, static files)
- SQLite database (safe atomic copy via `sqlite3 .backup`)
- User uploads (receipts, job photos, logos, estimates)
- Config and secrets (`.env`, `config.py`, etc.)
- Excludes: `.git/`, `scripts/logs/`

## Scripts

| Script | Purpose | Schedule |
|--------|---------|----------|
| `bdpt-backup-quick.sh` | Incremental sync to NVMe 1 | Every 15 min |
| `bdpt-backup-full.sh` | Full mirror to NVMe 2 + TrueNAS | Nightly 4:00 AM |
| `bdpt-backup-healthcheck.sh` | Alert if backups are stale | Hourly at :30 |
| `bdpt-backup-morning-report.sh` | Daily status summary | 10:00 AM |
| `setup-backup.sh` | One-time setup (run with sudo) | Manual |

## Notifications (ntfy.sh)

Push notifications to phone via [ntfy.sh](https://ntfy.sh). No account needed.

- **Topic**: `bdpt-backup-6uidbOprDudpqNE` (subscribe in ntfy app)
- **Failure alerts**: Immediate on backup failure
- **Stale alerts**: Hourly if quick backup >30 min old or nightly >26 hours old
- **Morning report**: Daily 10 AM summary of all targets

## Backup Targets

| Target | Mount Point | Protocol | Frequency |
|--------|------------|----------|-----------|
| NVMe 1 (AI-Backup) | `/media/joemack/AI-Backup` | Local ext4 | Every 15 min |
| NVMe 2 (AI-Backup 2) | `/media/joemack/AI-Backup 2` | Local ext4 | Nightly |
| TrueNAS | `/mnt/truenas-bdpt` | SMB/CIFS | Nightly |

### TrueNAS Details

- **IP**: 10.48.0.11
- **SMB Share**: `//10.48.0.11/Backups`
- **Dataset**: `tank/Backups/BDBus_Apps`
- **Credentials**: `/home/joemack/.smbcredentials-truenas` (mode 600)
- **Mount point**: `/mnt/truenas-bdpt`

## Directory Structure on Backup Targets

```
bdpt-backups/
  current/
    app/                     # Full mirror of project directory
      app.py
      database.py
      routes/
      templates/
      static/
      venv/                  # Python virtual environment (4.7GB)
      instance/
        bdb_tools.db         # Safe atomic DB copy
      receipts/
      job_photos/
      estimates/
      .env
      config.py
      ...
  snapshots/                 # Nightly targets only, 7-day retention
    bdb_tools_20260318_040000.db
    bdb_tools_20260319_040000.db
```

## Cron Entries

```bash
# BDPT quick backup every 15 minutes to NVMe 1
*/15 * * * * /usr/bin/flock -n /tmp/bdpt-quick.lock /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-quick.sh

# BDPT full nightly backup at 4:00 AM to NVMe 2 + TrueNAS
0 4 * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-full.sh

# BDPT backup health check every hour at :30
30 * * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-healthcheck.sh

# BDPT backup morning report at 10:00 AM
0 10 * * * /home/joemack/best-decision-business-apps/best-decision-project-tools/scripts/bdpt-backup-morning-report.sh
```

## Setup for a New App

### 1. Prerequisites

```bash
# Required packages
sudo apt install -y cifs-utils smbclient rsync sqlite3

# ntfy app on phone (iOS App Store / Google Play)
```

### 2. Copy and Adapt Scripts

Copy the `scripts/` directory to your new app. Update these variables in each script:

**All scripts:**
- `APP_DIR` — path to your app
- `NTFY_TOPIC` — generate a new topic: `head -c 12 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 16`

**Quick backup:**
- `DB_PATH` — path to your SQLite database
- `TARGET` / `MOUNT_POINT` — NVMe drive paths

**Full backup:**
- `DB_PATH` — path to your SQLite database
- `NVME2` / `NVME2_MOUNT` — second NVMe drive paths
- `TRUENAS_SHARE` — SMB share path
- `TRUENAS_MOUNT` — local mount point
- `TRUENAS_CREDS` — credentials file path

**Health check + Morning report:**
- `NVME1_DB` / `NVME2_DB` — paths to backed-up DB on each drive

### 3. Run Setup

```bash
sudo bash scripts/setup-backup.sh
```

This creates:
- Backup directories on NVMe drives (owned by your user)
- TrueNAS mount point
- SMB credentials template

### 4. Configure TrueNAS Credentials

```bash
nano ~/.smbcredentials-truenas
```

Format:
```
username=YOUR_TRUENAS_USER
password=YOUR_TRUENAS_PASSWORD
```

### 5. Sudoers for Passwordless Mount

```bash
sudo visudo -f /etc/sudoers.d/your-app-backup
```

Add:
```
joemack ALL=(ALL) NOPASSWD: /usr/bin/mount -t cifs //10.48.0.11/* /mnt/truenas-your-app *
joemack ALL=(ALL) NOPASSWD: /usr/bin/umount /mnt/truenas-your-app
```

### 6. Test Manually

```bash
bash scripts/your-backup-quick.sh
bash scripts/your-backup-full.sh
```

Check logs in `scripts/logs/`.

### 7. Install Cron

```bash
crontab -e
```

Add entries (adjust paths and avoid time conflicts with existing jobs).

### 8. Subscribe to ntfy

Open ntfy app on phone, tap +, enter your topic name.

## Key Design Decisions

- **SQLite .backup command** — safe atomic copy that works with WAL mode while app is running. Never `cp` a live SQLite DB.
- **rsync incremental** — only transfers changed bytes. Scales well as data grows.
- **No --delete on quick backup** — prevents accidental data loss. Nightly handles cleanup.
- **flock on quick backup** — prevents overlapping runs if a sync takes >15 min.
- **Exclude .git** — recoverable from remote, saves space and time.
- **TrueNAS mount/unmount per run** — no persistent mount that could go stale.

## Monitoring Logs

```bash
# Quick backup log (last few entries)
tail -20 scripts/logs/quick-backup.log

# Nightly backup log (today)
cat scripts/logs/backup-$(date +%Y%m%d).log

# Test ntfy notification
curl -d "Test message" ntfy.sh/YOUR_TOPIC
```

## Restore Procedure

### From NVMe (fastest)

```bash
# Stop the app
sudo systemctl stop bdpt

# Copy everything back
rsync -a /media/joemack/AI-Backup/bdpt-backups/current/app/ /path/to/restore/

# Or restore just the DB from a specific snapshot
cp "/media/joemack/AI-Backup 2/bdpt-backups/snapshots/bdb_tools_20260318_040000.db" \
   /path/to/restore/instance/bdb_tools.db

# Start the app
sudo systemctl start bdpt
```

### From TrueNAS

```bash
# Mount TrueNAS
sudo mount -t cifs //10.48.0.11/Backups /mnt/truenas-bdpt \
    -o credentials=/home/joemack/.smbcredentials-truenas,uid=$(id -u),gid=$(id -g),vers=3.0

# Copy
rsync -a /mnt/truenas-bdpt/BDBus_Apps/bdpt-backups/current/app/ /path/to/restore/

# Unmount
sudo umount /mnt/truenas-bdpt
```
