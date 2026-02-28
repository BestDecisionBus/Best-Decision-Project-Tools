import sqlite3
import secrets
import string
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

import config


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tokens (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            token        TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            logo_file    TEXT DEFAULT '',
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL CHECK (role IN ('admin', 'viewer', 'scheduler')),
            token         TEXT,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_users_token ON users(token);

        CREATE TABLE IF NOT EXISTS user_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (token)   REFERENCES tokens(token),
            UNIQUE (user_id, token)
        );
        CREATE INDEX IF NOT EXISTS idx_user_tokens_user  ON user_tokens(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_tokens_token ON user_tokens(token);

        CREATE TABLE IF NOT EXISTS employees (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            employee_id   TEXT NOT NULL,
            token         TEXT NOT NULL,
            username      TEXT,
            password_hash TEXT,
            is_active     INTEGER DEFAULT 1,
            created_at    TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_employees_token ON employees(token);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_username_token
            ON employees(username, token) WHERE username IS NOT NULL;

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name    TEXT NOT NULL,
            job_address TEXT NOT NULL,
            latitude    REAL,
            longitude   REAL,
            token       TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_token ON jobs(token);

        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            token      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_categories_token ON categories(token);

        CREATE TABLE IF NOT EXISTS time_entries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id      INTEGER NOT NULL,
            job_id           INTEGER NOT NULL,
            token            TEXT NOT NULL,
            clock_in_time    TEXT NOT NULL,
            clock_in_lat     REAL,
            clock_in_lng     REAL,
            clock_in_method  TEXT DEFAULT 'mobile',
            clock_out_time   TEXT,
            clock_out_lat    REAL,
            clock_out_lng    REAL,
            clock_out_method TEXT,
            manual_time_in   TEXT,
            manual_time_out  TEXT,
            admin_notes      TEXT DEFAULT '',
            total_hours      REAL,
            status           TEXT DEFAULT 'active',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_time_entries_token ON time_entries(token);
        CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_entries(employee_id);
        CREATE INDEX IF NOT EXISTS idx_time_entries_job ON time_entries(job_id);
        CREATE INDEX IF NOT EXISTS idx_time_entries_status ON time_entries(status);
        CREATE INDEX IF NOT EXISTS idx_time_entries_clock_in ON time_entries(clock_in_time);

        CREATE TABLE IF NOT EXISTS submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            token         TEXT NOT NULL,
            company_name  TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            month_folder  TEXT NOT NULL,
            image_file    TEXT NOT NULL,
            audio_file    TEXT NOT NULL,
            pdf_file      TEXT DEFAULT '',
            transcription TEXT DEFAULT '',
            job_id        INTEGER,
            category_1_id INTEGER,
            category_2_id INTEGER,
            submitted_ip  TEXT DEFAULT '',
            status        TEXT DEFAULT 'processing',
            processed     INTEGER DEFAULT 0,
            FOREIGN KEY (token) REFERENCES tokens(token),
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (category_1_id) REFERENCES categories(id),
            FOREIGN KEY (category_2_id) REFERENCES categories(id)
        );
        CREATE INDEX IF NOT EXISTS idx_submissions_token ON submissions(token);
        CREATE INDEX IF NOT EXISTS idx_submissions_month ON submissions(month_folder);
        CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);

        CREATE TABLE IF NOT EXISTS schedules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            job_id      INTEGER NOT NULL,
            token       TEXT NOT NULL,
            date        TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            shift_type  TEXT DEFAULT 'custom',
            notes       TEXT DEFAULT '',
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_schedules_token ON schedules(token);
        CREATE INDEX IF NOT EXISTS idx_schedules_employee ON schedules(employee_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);

        CREATE TABLE IF NOT EXISTS job_photos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      INTEGER NOT NULL,
            token       TEXT NOT NULL,
            week_folder TEXT NOT NULL,
            image_file  TEXT NOT NULL,
            thumb_file  TEXT DEFAULT '',
            caption     TEXT DEFAULT '',
            taken_by    TEXT DEFAULT '',
            latitude    REAL,
            longitude   REAL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_job_photos_token ON job_photos(token);
        CREATE INDEX IF NOT EXISTS idx_job_photos_job ON job_photos(job_id);
        CREATE INDEX IF NOT EXISTS idx_job_photos_week ON job_photos(week_folder);

        CREATE TABLE IF NOT EXISTS common_tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            token      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_common_tasks_token ON common_tasks(token);

        CREATE TABLE IF NOT EXISTS shift_types (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            start_time TEXT NOT NULL DEFAULT '07:00',
            end_time   TEXT NOT NULL DEFAULT '17:00',
            token      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_shift_types_token ON shift_types(token);

        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            time_entry_id INTEGER,
            token         TEXT NOT NULL,
            action        TEXT NOT NULL,
            field_changed TEXT,
            old_value     TEXT,
            new_value     TEXT,
            changed_by    TEXT NOT NULL,
            reason        TEXT DEFAULT '',
            timestamp     TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_audit_log_token ON audit_log(token);
        CREATE INDEX IF NOT EXISTS idx_audit_log_entry ON audit_log(time_entry_id);

        CREATE TABLE IF NOT EXISTS estimates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL,
            token           TEXT NOT NULL,
            title           TEXT DEFAULT '',
            audio_file      TEXT DEFAULT '',
            transcription   TEXT DEFAULT '',
            status          TEXT DEFAULT 'processing',
            approval_status TEXT DEFAULT 'pending',
            estimate_value  REAL DEFAULT 0,
            created_by      INTEGER,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_estimates_token ON estimates(token);
        CREATE INDEX IF NOT EXISTS idx_estimates_job ON estimates(job_id);
        CREATE INDEX IF NOT EXISTS idx_estimates_status ON estimates(status);

        CREATE TABLE IF NOT EXISTS estimate_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            estimate_id INTEGER NOT NULL,
            token       TEXT NOT NULL,
            description TEXT NOT NULL,
            quantity    REAL DEFAULT 1,
            unit        TEXT DEFAULT '',
            unit_price  REAL DEFAULT 0,
            total       REAL DEFAULT 0,
            sort_order  INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (estimate_id) REFERENCES estimates(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_estimate_items_estimate ON estimate_items(estimate_id);

        CREATE TABLE IF NOT EXISTS products_services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            unit_price REAL DEFAULT 0,
            token      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_products_services_token ON products_services(token);

        CREATE TABLE IF NOT EXISTS message_snippets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            token      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_message_snippets_token ON message_snippets(token);

        CREATE TABLE IF NOT EXISTS job_tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id     INTEGER NOT NULL,
            token      TEXT NOT NULL,
            name       TEXT NOT NULL,
            source     TEXT DEFAULT 'manual',
            sort_order INTEGER DEFAULT 0,
            is_active  INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (token) REFERENCES tokens(token)
        );
        CREATE INDEX IF NOT EXISTS idx_job_tasks_job ON job_tasks(job_id);
        CREATE INDEX IF NOT EXISTS idx_job_tasks_token ON job_tasks(token);

        CREATE TABLE IF NOT EXISTS submission_categories (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            category_id   INTEGER NOT NULL,
            amount        REAL DEFAULT 0,
            created_at    TEXT NOT NULL,
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sub_cats_submission ON submission_categories(submission_id);
        CREATE INDEX IF NOT EXISTS idx_sub_cats_category ON submission_categories(category_id);
    """)
    conn.commit()

    # Migrations — add columns to existing tables
    _add_column_if_missing(conn, "job_photos", "latitude", "REAL")
    _add_column_if_missing(conn, "job_photos", "longitude", "REAL")
    _add_column_if_missing(conn, "employees", "hourly_wage", "REAL DEFAULT NULL")
    _add_column_if_missing(conn, "employees", "receipt_access", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "employees", "timekeeper_access", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "employees", "job_photos_access", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "employees", "schedule_access", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "employees", "estimate_access", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "tokens", "labor_burden_pct", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "tokens", "income_target_pct", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "tokens", "overhead_pct", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "tokens", "monthly_overhead", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "tokens", "cash_on_hand", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "schedules", "common_task_id", "INTEGER")
    _add_column_if_missing(conn, "schedules", "job_task_id", "INTEGER")
    _add_column_if_missing(conn, "schedules", "custom_note", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "notes", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "approval_status", "TEXT DEFAULT 'pending'")
    _add_column_if_missing(conn, "estimates", "estimate_value", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "est_materials_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "est_labor_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "actual_materials_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "actual_labor_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "actual_collected", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "est_labor_hours", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "actual_labor_hours", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "customer_name", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "customer_phone", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "customer_email", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "estimate_number", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "date_accepted", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "expected_completion", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "audit_log", "reason", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimate_items", "taxable", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "sales_tax_rate", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "customer_message", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "estimates", "completion_pct", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "client_budget", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "append_audio_file", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "submissions", "vendor", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "products_services", "unit_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "products_services", "item_type", "TEXT DEFAULT 'product'")
    _add_column_if_missing(conn, "estimate_items", "item_type", "TEXT DEFAULT 'product'")
    _add_column_if_missing(conn, "estimate_items", "unit_cost", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "jobs", "is_archived", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "estimates", "completed_at", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "categories", "account_code", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "products_services", "taxable", "INTEGER DEFAULT 0")
    conn.commit()

    # Migrate legacy category_1_id / category_2_id into junction table
    _migrate_submission_categories(conn)

    # Back-fill user_tokens for all existing single-token users
    _migrate_user_tokens(conn)

    # Seed default users
    _ensure_user(conn, config.ADMIN_USERNAME, config.ADMIN_PASSWORD, "admin")
    _ensure_user(conn, config.VIEWER_USERNAME, config.VIEWER_PASSWORD, "viewer")
    conn.commit()
    conn.close()

    # Seed default shift types for all existing companies
    _seed_shift_types_all()


def _add_column_if_missing(conn, table, column, col_type):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _ensure_user(conn, username, password, role):
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )


def _seed_shift_types_all():
    """Seed default shift types for every existing token that has none."""
    conn = get_db()
    tokens = conn.execute("SELECT token FROM tokens").fetchall()
    conn.close()
    for t in tokens:
        seed_default_shift_types(t["token"])


def _migrate_user_tokens(conn):
    """Back-fill user_tokens for every existing single-token user (idempotent)."""
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO user_tokens (user_id, token, created_at)
        SELECT id, token, ? FROM users WHERE token IS NOT NULL
    """, (now,))
    conn.commit()


def _migrate_submission_categories(conn):
    """Copy legacy category_1_id / category_2_id into the junction table (idempotent)."""
    now = datetime.now().isoformat()
    for col in ("category_1_id", "category_2_id"):
        conn.execute(f"""
            INSERT INTO submission_categories (submission_id, category_id, amount, created_at)
            SELECT s.id, s.{col}, 0, ?
            FROM submissions s
            WHERE s.{col} IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM submission_categories sc
                  WHERE sc.submission_id = s.id AND sc.category_id = s.{col}
              )
        """, (now,))
    conn.commit()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def is_username_taken(username):
    """Check if a username is taken across both admin users and employees."""
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if not row:
        row = conn.execute("SELECT id FROM employees WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    conn.close()
    return row is not None


def verify_user(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def create_company_user(username, password, role, token_str):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, token) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, token_str),
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_tokens (user_id, token, created_at) VALUES (?, ?, ?)",
        (cur.lastrowid, token_str, now),
    )
    conn.commit()
    conn.close()


def get_users_by_token(token_str):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, role, token FROM users WHERE token = ? ORDER BY username ASC",
        (token_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_company_user_password(user_id, new_password):
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id),
    )
    conn.commit()
    conn.close()


def delete_company_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ? AND token IS NOT NULL", (user_id,))
    conn.commit()
    conn.close()


def get_bdb_users():
    """Return all BDB admin/viewer users (token IS NULL)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, role FROM users WHERE token IS NULL ORDER BY username ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tokens_for_user(user_id):
    """Return list of token dicts the user has access to (via user_tokens junction table)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*
        FROM tokens t
        JOIN user_tokens ut ON ut.token = t.token
        WHERE ut.user_id = ?
        ORDER BY t.company_name ASC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_extra_tokens_for_user(user_id):
    """Return tokens assigned beyond the user's primary token (for admin UI display)."""
    conn = get_db()
    user = conn.execute("SELECT token FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or not user["token"]:
        conn.close()
        return []
    rows = conn.execute("""
        SELECT t.*
        FROM tokens t
        JOIN user_tokens ut ON ut.token = t.token
        WHERE ut.user_id = ? AND t.token != ?
        ORDER BY t.company_name ASC
    """, (user_id, user["token"])).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_user_token(user_id, token_str):
    """Grant a company user access to an additional token. Idempotent."""
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO user_tokens (user_id, token, created_at) VALUES (?, ?, ?)",
        (user_id, token_str, now),
    )
    conn.commit()
    conn.close()


def remove_user_token(user_id, token_str):
    """Remove an extra token from a company user. Refuses to remove the primary token."""
    conn = get_db()
    user = conn.execute("SELECT token FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["token"] == token_str:
        conn.close()
        return False
    conn.execute(
        "DELETE FROM user_tokens WHERE user_id = ? AND token = ?",
        (user_id, token_str),
    )
    conn.commit()
    conn.close()
    return True


def get_all_users_for_token(token_str):
    """Return all users who have access to token_str (primary or extra)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT u.id, u.username, u.role, u.token,
               CASE WHEN u.token = ? THEN 0 ELSE 1 END AS is_extra
        FROM users u
        JOIN user_tokens ut ON ut.user_id = u.id
        WHERE ut.token = ?
        ORDER BY u.username ASC
    """, (token_str, token_str)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_bdb_user(username, password, role="admin"):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), role),
    )
    conn.commit()
    conn.close()


def update_user_password(user_id, new_password):
    """Update password for any user (BDB or company)."""
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id),
    )
    conn.commit()
    conn.close()


def delete_bdb_user(user_id):
    """Delete a BDB user (token IS NULL). Refuses to delete the last admin."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ? AND token IS NULL", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False
    # Don't allow deleting the last admin
    admin_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE token IS NULL AND role = 'admin'"
    ).fetchone()["cnt"]
    if user["role"] == "admin" and admin_count <= 1:
        conn.close()
        return False
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def generate_token_string():
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(12))


def get_token(token_str):
    conn = get_db()
    row = conn.execute("SELECT * FROM tokens WHERE token = ?", (token_str,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_token_by_id(token_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM tokens WHERE id = ?", (token_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_tokens():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tokens ORDER BY company_name ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_token(company_name, logo_file="", custom_token=None, labor_burden_pct=0):
    conn = get_db()
    token_str = custom_token if custom_token else generate_token_string()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO tokens (token, company_name, logo_file, labor_burden_pct, created_at) VALUES (?, ?, ?, ?, ?)",
        (token_str, company_name, logo_file, labor_burden_pct, now),
    )
    conn.commit()
    conn.close()
    seed_default_shift_types(token_str)
    return token_str


def update_token(token_id, company_name, logo_file=None):
    conn = get_db()
    if company_name is not None:
        conn.execute(
            "UPDATE tokens SET company_name = ? WHERE id = ?",
            (company_name, token_id),
        )
        # Cascade company_name to submissions
        row = conn.execute("SELECT token FROM tokens WHERE id = ?", (token_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE submissions SET company_name = ? WHERE token = ?",
                (company_name, row["token"]),
            )
    if logo_file is not None:
        conn.execute(
            "UPDATE tokens SET logo_file = ? WHERE id = ?",
            (logo_file, token_id),
        )
    conn.commit()
    conn.close()


def toggle_token(token_id):
    conn = get_db()
    conn.execute(
        "UPDATE tokens SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (token_id,),
    )
    conn.commit()
    t = conn.execute("SELECT is_active FROM tokens WHERE id = ?", (token_id,)).fetchone()
    conn.close()
    return t["is_active"] if t else None


def regenerate_token(token_id):
    conn = get_db()
    row = conn.execute("SELECT token, logo_file FROM tokens WHERE id = ?", (token_id,)).fetchone()
    if not row:
        conn.close()
        return None
    old_token = row["token"]
    new_token = generate_token_string()
    conn.execute("PRAGMA defer_foreign_keys = ON")
    for table in ("employees", "jobs", "categories", "time_entries", "submissions",
                   "schedules", "job_photos", "audit_log", "users",
                   "estimates", "estimate_items", "job_tasks", "message_snippets",
                   "products_services", "user_tokens"):
        conn.execute(f"UPDATE {table} SET token = ? WHERE token = ?", (new_token, old_token))
    conn.execute("UPDATE tokens SET token = ? WHERE id = ?", (new_token, token_id))
    conn.commit()
    conn.close()
    return new_token, old_token, row["logo_file"]


def delete_token(token_id):
    conn = get_db()
    row = conn.execute("SELECT token FROM tokens WHERE id = ?", (token_id,)).fetchone()
    if not row:
        conn.close()
        return None
    token_str = row["token"]
    # Delete submission_categories via submission_id (no token column)
    conn.execute("""
        DELETE FROM submission_categories
        WHERE submission_id IN (SELECT id FROM submissions WHERE token = ?)
    """, (token_str,))
    for table in ("audit_log", "time_entries", "submissions", "schedules", "job_photos",
                   "estimate_items", "estimates", "job_tasks", "message_snippets",
                   "products_services", "categories", "employees", "jobs", "users",
                   "user_tokens"):
        conn.execute(f"DELETE FROM {table} WHERE token = ?", (token_str,))
    conn.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
    conn.commit()
    conn.close()
    return token_str


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

def get_employees_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM employees WHERE token = ? AND is_active = 1 ORDER BY name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM employees WHERE token = ? ORDER BY name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_employee(employee_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_employee(name, employee_id_str, token_str, username=None, password=None,
                     hourly_wage=None, receipt_access=0, timekeeper_access=1,
                     job_photos_access=1, schedule_access=1, estimate_access=0):
    conn = get_db()
    now = datetime.now().isoformat()
    pw_hash = generate_password_hash(password) if password else None
    conn.execute(
        """INSERT INTO employees (name, employee_id, token, username, password_hash,
           hourly_wage, receipt_access, timekeeper_access, job_photos_access,
           schedule_access, estimate_access, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, employee_id_str, token_str, username or None, pw_hash, hourly_wage,
         receipt_access, timekeeper_access, job_photos_access, schedule_access,
         estimate_access, now),
    )
    conn.commit()
    conn.close()


_SENTINEL = object()


def update_employee(emp_id, name, employee_id_str, hourly_wage=_SENTINEL,
                    receipt_access=_SENTINEL, timekeeper_access=_SENTINEL,
                    job_photos_access=_SENTINEL, schedule_access=_SENTINEL,
                    estimate_access=_SENTINEL):
    conn = get_db()
    fields = ["name = ?", "employee_id = ?"]
    params = [name, employee_id_str]
    if hourly_wage is not _SENTINEL:
        fields.append("hourly_wage = ?")
        params.append(hourly_wage)
    if receipt_access is not _SENTINEL:
        fields.append("receipt_access = ?")
        params.append(receipt_access)
    if timekeeper_access is not _SENTINEL:
        fields.append("timekeeper_access = ?")
        params.append(timekeeper_access)
    if job_photos_access is not _SENTINEL:
        fields.append("job_photos_access = ?")
        params.append(job_photos_access)
    if schedule_access is not _SENTINEL:
        fields.append("schedule_access = ?")
        params.append(schedule_access)
    if estimate_access is not _SENTINEL:
        fields.append("estimate_access = ?")
        params.append(estimate_access)
    params.append(emp_id)
    conn.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def toggle_employee(emp_id):
    conn = get_db()
    conn.execute(
        "UPDATE employees SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (emp_id,),
    )
    conn.commit()
    conn.close()


def get_employee_by_username(username, token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM employees WHERE username = ? COLLATE NOCASE AND token = ?",
        (username, token_str),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_employee(username, password, token_str):
    emp = get_employee_by_username(username, token_str)
    if emp and emp.get("password_hash") and check_password_hash(emp["password_hash"], password):
        return emp
    return None


def set_employee_credentials(emp_id, username, password):
    conn = get_db()
    conn.execute(
        "UPDATE employees SET username = ?, password_hash = ? WHERE id = ?",
        (username, generate_password_hash(password), emp_id),
    )
    conn.commit()
    conn.close()


def reset_employee_password(emp_id, new_password):
    conn = get_db()
    conn.execute(
        "UPDATE employees SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), emp_id),
    )
    conn.commit()
    conn.close()


def get_or_create_admin_employee(username, password_hash, token_str):
    """Find or auto-create an employee record for an admin user logging into the company portal.
    Returns the employee dict."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM employees WHERE username = ? AND token = ?",
        (username, token_str),
    ).fetchone()
    if row:
        conn.close()
        return dict(row)
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO employees (name, employee_id, token, username, password_hash,
           is_active, hourly_wage, receipt_access, timekeeper_access,
           job_photos_access, schedule_access, estimate_access, created_at)
           VALUES (?, ?, ?, ?, ?, 1, NULL, 1, 1, 1, 1, 1, ?)""",
        (username, f"PM-{username}", token_str, username, password_hash, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM employees WHERE username = ? AND token = ?",
        (username, token_str),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def check_employee_username_available(username, token_str, exclude_emp_id=None):
    """Check if employee username is available globally (across all companies)."""
    conn = get_db()
    # Check against all employees (cross-company)
    if exclude_emp_id:
        row = conn.execute(
            "SELECT id FROM employees WHERE username = ? COLLATE NOCASE AND id != ?",
            (username, exclude_emp_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM employees WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
    if not row:
        # Also check against admin users table
        row = conn.execute(
            "SELECT id FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
    conn.close()
    return row is None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def get_jobs_by_token(token_str, active_only=False):
    conn = get_db()
    base = """
        SELECT j.*,
            (SELECT e.approval_status FROM estimates e
             WHERE e.job_id = j.id
             ORDER BY CASE e.approval_status
                 WHEN 'in_progress' THEN 1
                 WHEN 'accepted'    THEN 2
                 WHEN 'pending'     THEN 3
                 WHEN 'completed'   THEN 4
                 WHEN 'declined'    THEN 5
                 ELSE 6
             END ASC
             LIMIT 1) AS job_status
        FROM jobs j
        WHERE j.token = ?
    """
    if active_only:
        rows = conn.execute(base + " AND j.is_active = 1 ORDER BY j.job_name ASC", (token_str,)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY j.job_name ASC", (token_str,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job(job_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_job(job_name, job_address, latitude, longitude, token_str):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO jobs (job_name, job_address, latitude, longitude, token, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (job_name, job_address, latitude, longitude, token_str, now),
    )
    conn.commit()
    conn.close()


def update_job(job_id, job_name, job_address, latitude, longitude):
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET job_name = ?, job_address = ?, latitude = ?, longitude = ? WHERE id = ?",
        (job_name, job_address, latitude, longitude, job_id),
    )
    conn.commit()
    conn.close()


def toggle_job(job_id):
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (job_id,),
    )
    conn.commit()
    conn.close()


def archive_job(job_id):
    """Archive a job: marks it inactive and sets is_archived=1."""
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET is_archived = 1, is_active = 0 WHERE id = ?",
        (job_id,),
    )
    conn.commit()
    conn.close()


def unarchive_job(job_id):
    """Unarchive a job: clears is_archived (leaves is_active unchanged)."""
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET is_archived = 0 WHERE id = ?",
        (job_id,),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def get_categories_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM categories WHERE token = ? AND is_active = 1 ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM categories WHERE token = ? ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category(cat_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_category(name, token_str, sort_order=0, account_code=""):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO categories (name, token, sort_order, account_code, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, token_str, sort_order, account_code or "", now),
    )
    conn.commit()
    conn.close()


def update_category(cat_id, name, sort_order=None, account_code=None):
    conn = get_db()
    sets = ["name = ?"]
    params = [name]
    if sort_order is not None:
        sets.append("sort_order = ?")
        params.append(sort_order)
    if account_code is not None:
        sets.append("account_code = ?")
        params.append(account_code)
    params.append(cat_id)
    conn.execute(f"UPDATE categories SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def toggle_category(cat_id):
    conn = get_db()
    conn.execute(
        "UPDATE categories SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (cat_id,),
    )
    conn.commit()
    conn.close()


def bulk_deactivate_categories(token_str):
    conn = get_db()
    conn.execute("UPDATE categories SET is_active = 0 WHERE token = ?", (token_str,))
    conn.commit()
    conn.close()


def get_max_sort_order_categories(token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS mx FROM categories WHERE token = ?", (token_str,)
    ).fetchone()
    conn.close()
    return row["mx"] if row else 0


# ---------------------------------------------------------------------------
# Common Tasks (for scheduling notes dropdown)
# ---------------------------------------------------------------------------

def get_common_tasks_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM common_tasks WHERE token = ? AND is_active = 1 ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM common_tasks WHERE token = ? ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_common_task(task_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM common_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_common_task(name, token_str, sort_order=0):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO common_tasks (name, token, sort_order, created_at) VALUES (?, ?, ?, ?)",
        (name, token_str, sort_order, now),
    )
    conn.commit()
    conn.close()


def update_common_task(task_id, name, sort_order=None):
    conn = get_db()
    if sort_order is not None:
        conn.execute(
            "UPDATE common_tasks SET name = ?, sort_order = ? WHERE id = ?",
            (name, sort_order, task_id),
        )
    else:
        conn.execute("UPDATE common_tasks SET name = ? WHERE id = ?", (name, task_id))
    conn.commit()
    conn.close()


def toggle_common_task(task_id):
    conn = get_db()
    conn.execute(
        "UPDATE common_tasks SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (task_id,),
    )
    conn.commit()
    conn.close()


def bulk_deactivate_common_tasks(token_str):
    conn = get_db()
    conn.execute("UPDATE common_tasks SET is_active = 0 WHERE token = ?", (token_str,))
    conn.commit()
    conn.close()


def get_max_sort_order_common_tasks(token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS mx FROM common_tasks WHERE token = ?", (token_str,)
    ).fetchone()
    conn.close()
    return row["mx"] if row else 0


# ---------------------------------------------------------------------------
# Shift Types
# ---------------------------------------------------------------------------

DEFAULT_SHIFT_TYPES = [
    {"name": "Full Day",  "start_time": "07:00", "end_time": "17:00", "sort_order": 1},
    {"name": "Morning",   "start_time": "07:00", "end_time": "12:00", "sort_order": 2},
    {"name": "Afternoon", "start_time": "12:00", "end_time": "17:00", "sort_order": 3},
]


def seed_default_shift_types(token_str):
    """Create the standard shift types for a company if none exist yet."""
    conn = get_db()
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM shift_types WHERE token = ?", (token_str,)
    ).fetchone()["cnt"]
    if existing == 0:
        now = datetime.now().isoformat()
        for s in DEFAULT_SHIFT_TYPES:
            conn.execute(
                "INSERT INTO shift_types (name, start_time, end_time, token, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (s["name"], s["start_time"], s["end_time"], token_str, s["sort_order"], now),
            )
        conn.commit()
    conn.close()


def get_shift_types_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM shift_types WHERE token = ? AND is_active = 1 ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM shift_types WHERE token = ? ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shift_type(shift_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM shift_types WHERE id = ?", (shift_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_shift_type(name, start_time, end_time, token_str, sort_order=0):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO shift_types (name, start_time, end_time, token, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, start_time, end_time, token_str, sort_order, now),
    )
    conn.commit()
    conn.close()


def update_shift_type(shift_id, name, start_time, end_time, sort_order=None):
    conn = get_db()
    if sort_order is not None:
        conn.execute(
            "UPDATE shift_types SET name = ?, start_time = ?, end_time = ?, sort_order = ? WHERE id = ?",
            (name, start_time, end_time, sort_order, shift_id),
        )
    else:
        conn.execute(
            "UPDATE shift_types SET name = ?, start_time = ?, end_time = ? WHERE id = ?",
            (name, start_time, end_time, shift_id),
        )
    conn.commit()
    conn.close()


def toggle_shift_type(shift_id):
    conn = get_db()
    conn.execute(
        "UPDATE shift_types SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (shift_id,),
    )
    conn.commit()
    conn.close()


def bulk_deactivate_shift_types(token_str):
    conn = get_db()
    conn.execute("UPDATE shift_types SET is_active = 0 WHERE token = ?", (token_str,))
    conn.commit()
    conn.close()


def get_max_sort_order_shift_types(token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS mx FROM shift_types WHERE token = ?", (token_str,)
    ).fetchone()
    conn.close()
    return row["mx"] if row else 0


# ---------------------------------------------------------------------------
# Time Entries
# ---------------------------------------------------------------------------

def create_time_entry(employee_id, job_id, token_str, clock_in_time, clock_in_lat,
                      clock_in_lng, clock_in_method, admin_notes=""):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO time_entries
           (employee_id, job_id, token, clock_in_time, clock_in_lat, clock_in_lng,
            clock_in_method, admin_notes, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
        (employee_id, job_id, token_str, clock_in_time, clock_in_lat, clock_in_lng,
         clock_in_method, admin_notes, now, now),
    )
    entry_id = cur.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def clock_out_entry(entry_id, clock_out_time, clock_out_lat, clock_out_lng,
                    clock_out_method):
    conn = get_db()
    now = datetime.now().isoformat()
    entry = conn.execute("SELECT clock_in_time FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
    total_hours = None
    if entry:
        try:
            t_in = datetime.fromisoformat(entry["clock_in_time"])
            t_out = datetime.fromisoformat(clock_out_time)
            total_hours = round((t_out - t_in).total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            pass
    conn.execute(
        """UPDATE time_entries
           SET clock_out_time = ?, clock_out_lat = ?, clock_out_lng = ?,
               clock_out_method = ?, total_hours = ?, status = 'completed',
               updated_at = ?
           WHERE id = ? AND status = 'active'""",
        (clock_out_time, clock_out_lat, clock_out_lng, clock_out_method,
         total_hours, now, entry_id),
    )
    conn.commit()
    conn.close()
    return total_hours


def create_manual_entry(employee_id, job_id, token_str, manual_time_in, manual_time_out,
                        admin_notes, changed_by, reason=""):
    conn = get_db()
    now = datetime.now().isoformat()
    has_out = bool(manual_time_out and manual_time_out.strip())
    total_hours = None
    if has_out:
        try:
            t_in = datetime.fromisoformat(manual_time_in)
            t_out = datetime.fromisoformat(manual_time_out)
            total_hours = round((t_out - t_in).total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            pass
    status = "completed" if has_out else "active"
    clock_out = manual_time_out if has_out else None
    cur = conn.execute(
        """INSERT INTO time_entries
           (employee_id, job_id, token, clock_in_time, clock_in_method,
            clock_out_time, clock_out_method,
            manual_time_in, manual_time_out,
            admin_notes, total_hours, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'manual', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (employee_id, job_id, token_str, manual_time_in,
         clock_out, 'manual' if has_out else None,
         manual_time_in, clock_out,
         admin_notes, total_hours, status, now, now),
    )
    entry_id = cur.lastrowid
    conn.execute(
        """INSERT INTO audit_log (time_entry_id, token, action, changed_by, reason, timestamp)
           VALUES (?, ?, 'manual_entry_created', ?, ?, ?)""",
        (entry_id, token_str, changed_by, reason, now),
    )
    conn.commit()
    conn.close()
    return entry_id


def get_time_entry(entry_id):
    conn = get_db()
    row = conn.execute(
        """SELECT te.*, e.name as employee_name, e.employee_id as emp_id_str,
                  j.job_name, j.job_address, j.latitude as job_lat, j.longitude as job_lng
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           JOIN jobs j ON te.job_id = j.id
           WHERE te.id = ?""",
        (entry_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_entry_for_employee(employee_id):
    conn = get_db()
    row = conn.execute(
        """SELECT te.*, j.job_name FROM time_entries te
           JOIN jobs j ON te.job_id = j.id
           WHERE te.employee_id = ? AND te.status = 'active'
           ORDER BY te.clock_in_time DESC LIMIT 1""",
        (employee_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_time_entries(token_str, employee_id=None, job_id=None, status=None,
                     date_from=None, date_to=None, limit=100):
    conn = get_db()
    query = """SELECT te.*, e.name as employee_name, e.employee_id as emp_id_str,
                      j.job_name, j.job_address
               FROM time_entries te
               JOIN employees e ON te.employee_id = e.id
               JOIN jobs j ON te.job_id = j.id
               WHERE te.token = ?"""
    params = [token_str]

    if employee_id:
        query += " AND te.employee_id = ?"
        params.append(employee_id)
    if job_id:
        query += " AND te.job_id = ?"
        params.append(job_id)
    if status:
        query += " AND te.status = ?"
        params.append(status)
    if date_from:
        query += " AND te.clock_in_time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND te.clock_in_time <= ?"
        params.append(date_to + "T23:59:59")

    query += " ORDER BY te.clock_in_time DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_entries_for_employee(employee_id):
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT te.*, j.job_name FROM time_entries te
           JOIN jobs j ON te.job_id = j.id
           WHERE te.employee_id = ? AND te.clock_in_time >= ?
           ORDER BY te.clock_in_time DESC""",
        (employee_id, today),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_time_entry(entry_id, token_str, changed_by, reason=""):
    conn = get_db()
    now = datetime.now().isoformat()
    row = conn.execute(
        """SELECT te.*, e.name as employee_name, j.job_name
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           JOIN jobs j ON te.job_id = j.id
           WHERE te.id = ?""",
        (entry_id,),
    ).fetchone()
    old_value = ""
    if row:
        old_value = (
            f"{row['employee_name']} | {row['job_name']} | "
            f"In: {row['clock_in_time'] or ''} | Out: {row['clock_out_time'] or ''} | "
            f"Hours: {row['total_hours'] or ''} | Status: {row['status']}"
        )
    conn.execute(
        """INSERT INTO audit_log (time_entry_id, token, action, field_changed, old_value, changed_by, reason, timestamp)
           VALUES (?, ?, 'entry_deleted', 'time_entry', ?, ?, ?, ?)""",
        (entry_id, token_str, old_value, changed_by, reason, now),
    )
    conn.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def update_entry_notes(entry_id, admin_notes, changed_by, reason=""):
    conn = get_db()
    now = datetime.now().isoformat()
    old = conn.execute("SELECT admin_notes, token FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
    if old:
        conn.execute(
            "UPDATE time_entries SET admin_notes = ?, updated_at = ? WHERE id = ?",
            (admin_notes, now, entry_id),
        )
        conn.execute(
            """INSERT INTO audit_log
               (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
               VALUES (?, ?, 'notes_updated', 'admin_notes', ?, ?, ?, ?, ?)""",
            (entry_id, old["token"], old["admin_notes"], admin_notes, changed_by, reason, now),
        )
        conn.commit()
    conn.close()


def update_entry_status(entry_id, new_status, changed_by, reason=""):
    conn = get_db()
    now = datetime.now().isoformat()
    old = conn.execute("SELECT status, token FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
    if old:
        conn.execute(
            "UPDATE time_entries SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, entry_id),
        )
        conn.execute(
            """INSERT INTO audit_log
               (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
               VALUES (?, ?, 'status_changed', 'status', ?, ?, ?, ?, ?)""",
            (entry_id, old["token"], old["status"], new_status, changed_by, reason, now),
        )
        conn.commit()
    conn.close()


def update_entry_job(entry_id, new_job_id, changed_by, reason=""):
    """Reassign a time entry to a different job with audit logging."""
    conn = get_db()
    now = datetime.now().isoformat()
    old = conn.execute(
        """SELECT te.job_id, te.token, j.job_name as old_job_name
           FROM time_entries te
           JOIN jobs j ON te.job_id = j.id
           WHERE te.id = ?""",
        (entry_id,),
    ).fetchone()
    if old:
        new_job = conn.execute("SELECT job_name FROM jobs WHERE id = ?", (new_job_id,)).fetchone()
        new_job_name = new_job["job_name"] if new_job else str(new_job_id)
        conn.execute(
            "UPDATE time_entries SET job_id = ?, updated_at = ? WHERE id = ?",
            (new_job_id, now, entry_id),
        )
        conn.execute(
            """INSERT INTO audit_log
               (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
               VALUES (?, ?, 'job_changed', 'job_id', ?, ?, ?, ?, ?)""",
            (entry_id, old["token"],
             f"{old['old_job_name']} (id:{old['job_id']})",
             f"{new_job_name} (id:{new_job_id})",
             changed_by, reason, now),
        )
        conn.commit()
    conn.close()


def update_manual_times(entry_id, manual_time_in, manual_time_out, admin_notes, changed_by, reason=""):
    """Update manual time overrides. Either or both times can be provided."""
    conn = get_db()
    now = datetime.now().isoformat()
    old = conn.execute(
        "SELECT manual_time_in, manual_time_out, clock_in_time, clock_out_time, admin_notes, token, status FROM time_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    if old:
        # Determine effective in/out: use new manual if provided, else keep existing manual, else original clock
        new_in = manual_time_in or old["manual_time_in"]
        new_out = manual_time_out or old["manual_time_out"]
        eff_in = new_in or old["clock_in_time"]
        eff_out = new_out or old["clock_out_time"]

        total_hours = None
        if eff_in and eff_out:
            try:
                t_in = datetime.fromisoformat(str(eff_in)[:19])
                t_out = datetime.fromisoformat(str(eff_out)[:19])
                total_hours = round((t_out - t_in).total_seconds() / 3600, 2)
            except (ValueError, TypeError):
                pass

        # If a manual clock-out is being set, mark the entry as completed
        new_status = "completed" if new_out else None

        conn.execute(
            """UPDATE time_entries
               SET manual_time_in = ?, manual_time_out = ?, admin_notes = ?,
                   total_hours = COALESCE(?, total_hours),
                   status = COALESCE(?, status), updated_at = ?
               WHERE id = ?""",
            (new_in, new_out, admin_notes, total_hours, new_status, now, entry_id),
        )

        # Audit log entries for each changed field
        if manual_time_in:
            conn.execute(
                """INSERT INTO audit_log
                   (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
                   VALUES (?, ?, 'manual_override', 'manual_time_in', ?, ?, ?, ?, ?)""",
                (entry_id, old["token"], old["manual_time_in"] or old["clock_in_time"],
                 manual_time_in, changed_by, reason, now),
            )
        if manual_time_out:
            conn.execute(
                """INSERT INTO audit_log
                   (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
                   VALUES (?, ?, 'manual_override', 'manual_time_out', ?, ?, ?, ?, ?)""",
                (entry_id, old["token"], old["manual_time_out"] or old["clock_out_time"],
                 manual_time_out, changed_by, reason, now),
            )
        if new_status and old["status"] != new_status:
            conn.execute(
                """INSERT INTO audit_log
                   (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
                   VALUES (?, ?, 'manual_override', 'status', ?, ?, ?, ?, ?)""",
                (entry_id, old["token"], old["status"], new_status, changed_by,
                 "Auto-completed: manual clock-out override applied", now),
            )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

def get_dashboard_stats(token_str):
    conn = get_db()
    stats = {}
    stats["active_employees"] = conn.execute(
        "SELECT COUNT(*) FROM employees WHERE token = ? AND is_active = 1", (token_str,)
    ).fetchone()[0]
    stats["total_jobs"] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE token = ? AND is_active = 1", (token_str,)
    ).fetchone()[0]
    stats["active_punches"] = conn.execute(
        "SELECT COUNT(*) FROM time_entries WHERE token = ? AND status = 'active'", (token_str,)
    ).fetchone()[0]
    stats["needs_review"] = conn.execute(
        "SELECT COUNT(*) FROM time_entries WHERE token = ? AND status = 'needs_review'", (token_str,)
    ).fetchone()[0]

    today = datetime.now()
    sunday_str = _current_week_start_sunday()
    result = conn.execute(
        """SELECT COALESCE(SUM(total_hours), 0) FROM time_entries
           WHERE token = ? AND clock_in_time >= ? AND total_hours IS NOT NULL""",
        (token_str, sunday_str),
    ).fetchone()
    stats["weekly_hours"] = round(result[0], 1)

    stats["total_entries"] = conn.execute(
        "SELECT COUNT(*) FROM time_entries WHERE token = ?", (token_str,)
    ).fetchone()[0]

    # New stats for company dashboard
    today_str = today.strftime("%Y-%m-%d")
    stats["scheduled_today"] = conn.execute(
        "SELECT COUNT(DISTINCT employee_id) FROM schedules WHERE token = ? AND date = ?",
        (token_str, today_str),
    ).fetchone()[0]

    stats["photos_this_week"] = conn.execute(
        "SELECT COUNT(*) FROM job_photos WHERE token = ? AND created_at >= ?",
        (token_str, sunday_str),
    ).fetchone()[0]

    conn.close()
    return stats


def get_all_company_summaries():
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*,
               (SELECT COUNT(*) FROM employees e WHERE e.token = t.token AND e.is_active = 1) as employee_count,
               (SELECT COUNT(*) FROM jobs j WHERE j.token = t.token AND j.is_active = 1) as active_jobs,
               (SELECT COUNT(*) FROM time_entries te WHERE te.token = t.token AND te.status = 'active') as active_punches
        FROM tokens t
        ORDER BY t.company_name ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def add_audit_log(time_entry_id, token_str, action, field_changed, old_value,
                  new_value, changed_by, reason=""):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO audit_log
           (time_entry_id, token, action, field_changed, old_value, new_value, changed_by, reason, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (time_entry_id, token_str, action, field_changed, old_value, new_value, changed_by, reason, now),
    )
    conn.commit()
    conn.close()


def get_audit_log(token_str, limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE token = ? ORDER BY timestamp DESC LIMIT ?",
        (token_str, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def get_time_entries_for_export(token_str, date_from=None, date_to=None):
    conn = get_db()
    query = """SELECT te.*, e.name as employee_name, e.employee_id as emp_id_str,
                      e.hourly_wage,
                      j.job_name, j.job_address
               FROM time_entries te
               JOIN employees e ON te.employee_id = e.id
               JOIN jobs j ON te.job_id = j.id
               WHERE te.token = ?"""
    params = [token_str]
    if date_from:
        query += " AND te.clock_in_time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND te.clock_in_time <= ?"
        params.append(date_to + "T23:59:59")
    query += " ORDER BY te.clock_in_time ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_effective_rates_for_entries(token_str, entries):
    """Compute OT effective rates for a set of entries.

    Fetches ALL entries for the involved employees so that weekly hour
    totals (and therefore OT) are computed correctly even when the export
    date range cuts across a week boundary.

    Returns the rates dict keyed by (employee_id, week_start).
    """
    emp_ids = list({e["employee_id"] for e in entries if e.get("employee_id")})
    if not emp_ids:
        return {}
    conn = get_db()
    ph = ",".join("?" * len(emp_ids))
    all_rows = conn.execute(
        f"""SELECT te.employee_id, te.total_hours, te.clock_in_time, e.hourly_wage
            FROM time_entries te
            JOIN employees e ON te.employee_id = e.id
            WHERE te.token = ? AND te.employee_id IN ({ph})
            AND te.total_hours IS NOT NULL""",
        [token_str] + emp_ids,
    ).fetchall()
    conn.close()
    return _compute_effective_rates([dict(r) for r in all_rows])


# ---------------------------------------------------------------------------
# Token Labor Burden
# ---------------------------------------------------------------------------

def update_token_burden(token_str, pct):
    conn = get_db()
    conn.execute(
        "UPDATE tokens SET labor_burden_pct = ? WHERE token = ?",
        (pct, token_str),
    )
    conn.commit()
    conn.close()


def update_token_finance_targets(token_str, income_target_pct, overhead_pct,
                                 monthly_overhead=None, cash_on_hand=None):
    conn = get_db()
    conn.execute(
        """UPDATE tokens
           SET income_target_pct = ?, overhead_pct = ?,
               monthly_overhead = ?, cash_on_hand = ?
           WHERE token = ?""",
        (income_target_pct, overhead_pct,
         monthly_overhead or 0, cash_on_hand or 0, token_str),
    )
    conn.commit()
    conn.close()


def get_expense_totals(token_str):
    """Return weekly + YTD receipt expense totals (SUM of submission_categories.amount)."""
    conn = get_db()
    today = datetime.now()
    sunday_str = _current_week_start_sunday()
    jan1_str = today.strftime("%Y-01-01")

    def _sum_period(date_from):
        sql = """SELECT COALESCE(SUM(sc.amount), 0) as total
                 FROM submission_categories sc
                 JOIN submissions s ON sc.submission_id = s.id
                 WHERE s.token = ? AND s.status = 'complete'
                   AND s.timestamp >= ?"""
        return conn.execute(sql, (token_str, date_from)).fetchone()["total"]

    weekly = round(_sum_period(sunday_str), 2)
    ytd = round(_sum_period(jan1_str), 2)
    conn.close()
    return {"weekly": weekly, "ytd": ytd}


# ---------------------------------------------------------------------------
# Dashboard — BDB Receipt Stats
# ---------------------------------------------------------------------------

def get_bdb_receipt_stats():
    conn = get_db()
    stats = {}
    stats["total_unprocessed"] = conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE processed = 0"
    ).fetchone()[0]
    stats["processing"] = conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE status IN ('processing', 'transcribing')"
    ).fetchone()[0]
    sunday_str = _current_week_start_sunday()
    stats["complete_this_week"] = conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE status = 'complete' AND timestamp >= ?",
        (sunday_str,),
    ).fetchone()[0]
    stats["errors"] = conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE status = 'error'"
    ).fetchone()[0]
    conn.close()
    return stats


def get_recent_unprocessed_receipts(limit=20):
    conn = get_db()
    rows = conn.execute(
        """SELECT s.*, t.company_name
           FROM submissions s
           JOIN tokens t ON s.token = t.token
           WHERE s.processed = 0
           ORDER BY s.timestamp DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard — Company Operations
# ---------------------------------------------------------------------------

def get_active_entries(token_str):
    conn = get_db()
    rows = conn.execute(
        """SELECT te.id, te.clock_in_time, e.name as employee_name,
                  j.job_name
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           JOIN jobs j ON te.job_id = j.id
           WHERE te.token = ? AND te.status = 'active'
           ORDER BY te.clock_in_time ASC""",
        (token_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_needs_review_entries(token_str, limit=10):
    conn = get_db()
    rows = conn.execute(
        """SELECT te.id, te.clock_in_time, te.admin_notes, e.name as employee_name,
                  j.job_name
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           JOIN jobs j ON te.job_id = j.id
           WHERE te.token = ? AND te.status = 'needs_review'
           ORDER BY te.clock_in_time DESC LIMIT ?""",
        (token_str, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_todays_schedules(token_str):
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT s.*, e.name as employee_name, j.job_name
           FROM schedules s
           JOIN employees e ON s.employee_id = e.id
           JOIN jobs j ON s.job_id = j.id
           WHERE s.token = ? AND s.date = ?
           ORDER BY s.start_time ASC""",
        (token_str, today),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_schedules_today_count(token_str):
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM schedules WHERE token = ? AND date = ?",
        (token_str, today),
    ).fetchone()[0]
    conn.close()
    return count


def get_photos_this_week_count(token_str):
    conn = get_db()
    sunday_str = _current_week_start_sunday()
    count = conn.execute(
        "SELECT COUNT(*) FROM job_photos WHERE token = ? AND created_at >= ?",
        (token_str, sunday_str),
    ).fetchone()[0]
    conn.close()
    return count


def _get_week_start_sunday(date_str):
    """Return YYYY-MM-DD of the Sunday that starts the Sun–Sat work week."""
    from datetime import timedelta
    dt = datetime.fromisoformat(date_str[:19])
    offset = (dt.weekday() + 1) % 7        # Mon=0 … Sun=6 → Sun=0 … Sat=6
    return (dt - timedelta(days=offset)).strftime("%Y-%m-%d")


def _current_week_start_sunday():
    """Return YYYY-MM-DD of the Sunday that starts the current work week."""
    from datetime import timedelta
    today = datetime.now()
    offset = (today.weekday() + 1) % 7
    return (today - timedelta(days=offset)).strftime("%Y-%m-%d")


def _calc_overtime_pay(total_hours, hourly_wage):
    """Return (regular_hours, ot_hours, total_pay) using 1.5x OT after 40 hrs."""
    reg = min(total_hours, 40.0)
    ot = max(total_hours - 40.0, 0.0)
    pay = reg * hourly_wage + ot * hourly_wage * 1.5
    return reg, ot, pay


def _compute_effective_rates(entries):
    """Build a dict of (employee_id, week_start) → blended effective rate.

    OT rule: hours > 40 per employee per Sun–Sat week are paid at 1.5×.
    The effective rate spreads OT cost evenly across all hours so that
    per-job or per-entry allocation is proportional.

    entries: iterable of dicts with employee_id, hourly_wage, total_hours,
             clock_in_time.
    Returns: dict keyed by (employee_id, week_start) with:
        total_hours, regular_hours, ot_hours, wage, total_pay, effective_rate
    """
    from collections import defaultdict
    emp_weeks = defaultdict(lambda: {"hours": 0.0, "wage": None})
    for e in entries:
        hrs = float(e.get("total_hours") or 0)
        if hrs <= 0:
            continue
        week = _get_week_start_sunday(e["clock_in_time"])
        key = (e["employee_id"], week)
        emp_weeks[key]["hours"] += hrs
        if e.get("hourly_wage") is not None:
            emp_weeks[key]["wage"] = e["hourly_wage"]

    rates = {}
    for key, data in emp_weeks.items():
        wage = data["wage"]
        total = data["hours"]
        if wage is None or total <= 0:
            rates[key] = {"total_hours": total, "regular_hours": total,
                          "ot_hours": 0, "wage": 0, "total_pay": 0,
                          "effective_rate": 0}
            continue
        reg, ot, pay = _calc_overtime_pay(total, wage)
        rates[key] = {
            "total_hours": total, "regular_hours": reg, "ot_hours": ot,
            "wage": wage, "total_pay": pay,
            "effective_rate": pay / total,
        }
    return rates


def get_weekly_payroll_estimate(token_str):
    conn = get_db()
    sunday_str = _current_week_start_sunday()

    # Get labor burden for this company
    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    rows = conn.execute(
        """SELECT e.id, e.name as employee_name, e.employee_id as emp_id_str,
                  e.hourly_wage,
                  COALESCE(SUM(te.total_hours), 0) as total_hours
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           WHERE te.token = ? AND te.clock_in_time >= ? AND te.total_hours IS NOT NULL
           GROUP BY e.id
           ORDER BY e.name ASC""",
        (token_str, sunday_str),
    ).fetchall()
    conn.close()

    employees = []
    total_base = 0.0
    total_burden = 0.0
    total_cost = 0.0
    total_reg_hrs = 0.0
    total_ot_hrs = 0.0
    for r in rows:
        row = dict(r)
        hours = round(row["total_hours"], 2)
        wage = row["hourly_wage"]
        if wage is not None:
            reg_hrs, ot_hrs, base_pay = _calc_overtime_pay(hours, wage)
            reg_hrs = round(reg_hrs, 2)
            ot_hrs = round(ot_hrs, 2)
            base_pay = round(base_pay, 2)
            burden = round(base_pay * (burden_pct / 100), 2)
            cost = round(base_pay + burden, 2)
            total_base += base_pay
            total_burden += burden
            total_cost += cost
            total_reg_hrs += reg_hrs
            total_ot_hrs += ot_hrs
        else:
            reg_hrs = hours
            ot_hrs = 0.0
            base_pay = None
            burden = None
            cost = None
        employees.append({
            "employee_name": row["employee_name"],
            "emp_id_str": row["emp_id_str"],
            "hours": hours,
            "regular_hours": reg_hrs,
            "ot_hours": ot_hrs,
            "hourly_wage": wage,
            "base_pay": base_pay,
            "burden": burden,
            "total_cost": cost,
        })

    return {
        "employees": employees,
        "burden_pct": burden_pct,
        "total_base": round(total_base, 2),
        "total_burden": round(total_burden, 2),
        "total_cost": round(total_cost, 2),
        "total_regular_hours": round(total_reg_hrs, 2),
        "total_ot_hours": round(total_ot_hrs, 2),
    }


def get_weekly_job_costs(token_str):
    conn = get_db()
    sunday_str = _current_week_start_sunday()

    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    # Fetch individual entries so OT can be computed per-employee then allocated
    rows = conn.execute(
        """SELECT te.employee_id, te.total_hours, te.clock_in_time,
                  e.hourly_wage, j.id as job_id, j.job_name
           FROM time_entries te
           JOIN jobs j ON te.job_id = j.id
           JOIN employees e ON te.employee_id = e.id
           WHERE te.token = ? AND te.clock_in_time >= ? AND te.total_hours IS NOT NULL
           ORDER BY j.job_name""",
        (token_str, sunday_str),
    ).fetchall()
    conn.close()

    entries = [dict(r) for r in rows]
    eff_rates = _compute_effective_rates(entries)

    from collections import defaultdict
    job_agg = defaultdict(lambda: {"hours": 0.0, "base": 0.0})
    for e in entries:
        hrs = float(e["total_hours"] or 0)
        if hrs <= 0:
            continue
        jid = e["job_id"]
        job_agg[jid]["job_name"] = e["job_name"]
        job_agg[jid]["hours"] += hrs
        week = _get_week_start_sunday(e["clock_in_time"])
        rate_info = eff_rates.get((e["employee_id"], week))
        if rate_info and rate_info["effective_rate"]:
            job_agg[jid]["base"] += hrs * rate_info["effective_rate"]

    jobs = []
    total_hours = 0.0
    total_cost = 0.0
    for jid, jd in sorted(job_agg.items(), key=lambda x: x[1]["hours"], reverse=True):
        hours = round(jd["hours"], 2)
        base = round(jd["base"], 2)
        burden = round(base * (burden_pct / 100), 2)
        cost = round(base + burden, 2)
        total_hours += hours
        total_cost += cost
        jobs.append({
            "job_name": jd["job_name"],
            "hours": hours,
            "total_cost": cost,
        })

    return {
        "jobs": jobs,
        "total_hours": round(total_hours, 2),
        "total_cost": round(total_cost, 2),
    }


def get_alltime_job_costs(token_str):
    """Same as get_weekly_job_costs but covers all completed time entries (no date filter)."""
    conn = get_db()

    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    rows = conn.execute(
        """SELECT te.employee_id, te.total_hours, te.clock_in_time,
                  e.hourly_wage, j.id as job_id, j.job_name
           FROM time_entries te
           JOIN jobs j ON te.job_id = j.id
           JOIN employees e ON te.employee_id = e.id
           WHERE te.token = ? AND te.total_hours IS NOT NULL
           ORDER BY j.job_name""",
        (token_str,),
    ).fetchall()
    conn.close()

    entries = [dict(r) for r in rows]
    eff_rates = _compute_effective_rates(entries)

    from collections import defaultdict
    job_agg = defaultdict(lambda: {"hours": 0.0, "base": 0.0})
    for e in entries:
        hrs = float(e["total_hours"] or 0)
        if hrs <= 0:
            continue
        jid = e["job_id"]
        job_agg[jid]["job_name"] = e["job_name"]
        job_agg[jid]["hours"] += hrs
        week = _get_week_start_sunday(e["clock_in_time"])
        rate_info = eff_rates.get((e["employee_id"], week))
        if rate_info and rate_info["effective_rate"]:
            job_agg[jid]["base"] += hrs * rate_info["effective_rate"]

    jobs = []
    total_hours = 0.0
    total_cost = 0.0
    for jid, jd in sorted(job_agg.items(), key=lambda x: x[1]["hours"], reverse=True):
        hours = round(jd["hours"], 2)
        base = round(jd["base"], 2)
        burden = round(base * (burden_pct / 100), 2)
        cost = round(base + burden, 2)
        total_hours += hours
        total_cost += cost
        jobs.append({
            "job_name": jd["job_name"],
            "hours": hours,
            "total_cost": cost,
        })

    return {
        "jobs": jobs,
        "total_hours": round(total_hours, 2),
        "total_cost": round(total_cost, 2),
    }


def get_job_financials(token_str, active_only=None):
    """Aggregate financial data per job from accepted/completed estimates."""
    conn = get_db()
    sql = """SELECT j.id, j.job_name, j.is_active, j.is_archived,
                    COALESCE(SUM(e.estimate_value), 0) AS budget,
                    COALESCE(SUM(e.est_materials_cost), 0) AS est_materials,
                    COALESCE(SUM(e.est_labor_cost), 0) AS est_labor,
                    COALESCE(SUM(e.actual_materials_cost), 0) AS actual_materials,
                    COALESCE(SUM(e.actual_labor_cost), 0) AS actual_labor,
                    COALESCE(SUM(e.actual_collected), 0) AS actual_collected,
                    COALESCE(AVG(e.completion_pct), 0) AS avg_completion_pct,
                    COUNT(e.id) AS estimate_count,
                    COUNT(CASE WHEN e.approval_status = 'completed' THEN 1 END) AS completed_estimate_count,
                    COUNT(CASE WHEN e.approval_status IN ('accepted','in_progress') THEN 1 END) AS active_estimate_count,
                    MAX(CASE WHEN e.approval_status = 'completed'
                             THEN COALESCE(NULLIF(e.completed_at,''), e.created_at) END) AS last_completed_at
             FROM jobs j
             LEFT JOIN estimates e ON e.job_id = j.id
                  AND e.approval_status IN ('accepted','in_progress','completed')
             WHERE j.token = ?"""
    params = [token_str]
    if active_only is True:
        sql += " AND j.is_active = 1"
    elif active_only is False:
        sql += " AND j.is_active = 0"
    sql += " GROUP BY j.id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        row = dict(r)
        est_total = row["est_materials"] + row["est_labor"]
        actual_total = row["actual_materials"] + row["actual_labor"]
        predicted_margin = row["budget"] - est_total
        actual_margin = row["actual_collected"] - actual_total
        predicted_margin_pct = round((predicted_margin / row["budget"]) * 100, 1) if row["budget"] else 0
        actual_margin_pct = round((actual_margin / row["actual_collected"]) * 100, 1) if row["actual_collected"] else 0
        budget_pct = round((actual_total / est_total) * 100, 1) if est_total else 0
        row.update({
            "est_total_cost": round(est_total, 2),
            "actual_total_cost": round(actual_total, 2),
            "predicted_margin": round(predicted_margin, 2),
            "predicted_margin_pct": predicted_margin_pct,
            "actual_margin": round(actual_margin, 2),
            "actual_margin_pct": actual_margin_pct,
            "budget_pct": budget_pct,
            "completion_pct": round(row["avg_completion_pct"], 1),
        })
        results.append(row)
    return results


def get_job_hours_and_costs(token_str, date_from=None):
    """Job hours & labour costs with OT — all-time when date_from is None."""
    conn = get_db()
    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    # Fetch individual entries for OT calculation
    sql = """SELECT te.employee_id, te.total_hours, te.clock_in_time,
                    e.hourly_wage, j.id as job_id, j.job_name
             FROM time_entries te
             JOIN jobs j ON te.job_id = j.id
             JOIN employees e ON te.employee_id = e.id
             WHERE te.token = ? AND te.total_hours IS NOT NULL"""
    params = [token_str]
    if date_from is not None:
        sql += " AND te.clock_in_time >= ?"
        params.append(date_from)
    rows = conn.execute(sql, params).fetchall()

    # Also fetch ALL entries for the same employees to get correct weekly totals
    # (an employee's OT depends on total hours across all jobs that week)
    target_entries = [dict(r) for r in rows]
    emp_ids = list({e["employee_id"] for e in target_entries})
    all_entries = []
    if emp_ids:
        ph = ",".join("?" * len(emp_ids))
        all_entries = [dict(r) for r in conn.execute(
            f"""SELECT te.employee_id, te.total_hours, te.clock_in_time, e.hourly_wage
                FROM time_entries te
                JOIN employees e ON te.employee_id = e.id
                WHERE te.token = ? AND te.employee_id IN ({ph})
                AND te.total_hours IS NOT NULL""",
            [token_str] + emp_ids,
        ).fetchall()]
    conn.close()

    eff_rates = _compute_effective_rates(all_entries)

    from collections import defaultdict
    job_agg = defaultdict(lambda: {"hours": 0.0, "base": 0.0, "job_name": ""})
    for e in target_entries:
        hrs = float(e["total_hours"] or 0)
        if hrs <= 0:
            continue
        jid = e["job_id"]
        job_agg[jid]["job_name"] = e["job_name"]
        job_agg[jid]["hours"] += hrs
        week = _get_week_start_sunday(e["clock_in_time"])
        rate_info = eff_rates.get((e["employee_id"], week))
        if rate_info and rate_info["effective_rate"]:
            job_agg[jid]["base"] += hrs * rate_info["effective_rate"]

    jobs = []
    total_hours = 0.0
    total_cost = 0.0
    for jid, jd in sorted(job_agg.items(), key=lambda x: x[1]["hours"], reverse=True):
        hours = round(jd["hours"], 2)
        base = round(jd["base"], 2)
        burden = round(base * (burden_pct / 100), 2)
        cost = round(base + burden, 2)
        total_hours += hours
        total_cost += cost
        jobs.append({
            "job_name": jd["job_name"],
            "hours": hours,
            "total_cost": cost,
        })

    return {
        "jobs": jobs,
        "total_hours": round(total_hours, 2),
        "total_cost": round(total_cost, 2),
    }


def get_job_labor_total(job_id, token_str):
    """Total hours & labour cost for a single job (with burden + OT)."""
    conn = get_db()
    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    # Fetch individual entries for this job
    job_entries = [dict(r) for r in conn.execute(
        """SELECT te.employee_id, te.total_hours, te.clock_in_time, e.hourly_wage
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           WHERE te.job_id = ? AND te.token = ? AND te.total_hours IS NOT NULL""",
        (job_id, token_str),
    ).fetchall()]

    if not job_entries:
        conn.close()
        return {"total_hours": 0, "total_cost": 0}

    # Fetch ALL entries for these employees to compute correct weekly OT totals
    emp_ids = list({e["employee_id"] for e in job_entries})
    ph = ",".join("?" * len(emp_ids))
    all_entries = [dict(r) for r in conn.execute(
        f"""SELECT te.employee_id, te.total_hours, te.clock_in_time, e.hourly_wage
            FROM time_entries te
            JOIN employees e ON te.employee_id = e.id
            WHERE te.token = ? AND te.employee_id IN ({ph})
            AND te.total_hours IS NOT NULL""",
        [token_str] + emp_ids,
    ).fetchall()]
    conn.close()

    eff_rates = _compute_effective_rates(all_entries)

    total_hours = 0.0
    total_base = 0.0
    for e in job_entries:
        hrs = float(e["total_hours"] or 0)
        if hrs <= 0:
            continue
        total_hours += hrs
        week = _get_week_start_sunday(e["clock_in_time"])
        rate_info = eff_rates.get((e["employee_id"], week))
        if rate_info and rate_info["effective_rate"]:
            total_base += hrs * rate_info["effective_rate"]

    hours = round(total_hours, 2)
    base = round(total_base, 2)
    burden = round(base * (burden_pct / 100), 2)
    return {"total_hours": hours, "total_cost": round(base + burden, 2)}


def get_overall_labor_stats(token_str):
    """Return hours + payroll (with OT) for weekly, YTD, and all-time periods."""
    conn = get_db()
    today = datetime.now()
    sunday_str = _current_week_start_sunday()
    jan1_str = today.strftime("%Y-01-01")

    token_row = conn.execute(
        "SELECT labor_burden_pct FROM tokens WHERE token = ?", (token_str,)
    ).fetchone()
    burden_pct = token_row["labor_burden_pct"] if token_row else 0

    # Fetch ALL entries once (all-time), then filter in Python for each period
    all_rows = conn.execute(
        """SELECT te.employee_id, te.total_hours, te.clock_in_time, e.hourly_wage
           FROM time_entries te
           JOIN employees e ON te.employee_id = e.id
           WHERE te.token = ? AND te.total_hours IS NOT NULL""",
        (token_str,),
    ).fetchall()
    conn.close()

    all_entries = [dict(r) for r in all_rows]

    def _calc_period(entries, date_from=None):
        """Compute labour cost with OT for entries on or after date_from."""
        filtered = entries
        if date_from:
            filtered = [e for e in entries if e["clock_in_time"] >= date_from]
        if not filtered:
            return {"total_hours": 0, "base_pay": 0, "burden": 0, "total_cost": 0}

        # For correct OT we need the full weekly totals even for weeks that
        # straddle the date_from boundary.  Collect all entries in any week
        # that contains at least one filtered entry.
        weeks_needed = set()
        for e in filtered:
            weeks_needed.add((e["employee_id"], _get_week_start_sunday(e["clock_in_time"])))
        all_week_entries = [
            e for e in entries
            if (e["employee_id"], _get_week_start_sunday(e["clock_in_time"])) in weeks_needed
        ]

        eff_rates = _compute_effective_rates(all_week_entries)

        total_hours = 0.0
        total_base = 0.0
        for e in filtered:
            hrs = float(e["total_hours"] or 0)
            if hrs <= 0:
                continue
            total_hours += hrs
            week = _get_week_start_sunday(e["clock_in_time"])
            rate_info = eff_rates.get((e["employee_id"], week))
            if rate_info and rate_info["effective_rate"]:
                total_base += hrs * rate_info["effective_rate"]

        hours = round(total_hours, 2)
        base = round(total_base, 2)
        burden = round(base * (burden_pct / 100), 2)
        return {
            "total_hours": hours,
            "base_pay": base,
            "burden": burden,
            "total_cost": round(base + burden, 2),
        }

    return {
        "weekly": _calc_period(all_entries, sunday_str),
        "ytd": _calc_period(all_entries, jan1_str),
        "alltime": _calc_period(all_entries),
    }


# ---------------------------------------------------------------------------
# Submissions (Receipt Capture)
# ---------------------------------------------------------------------------

def create_submission(token, company_name, image_file, audio_file, submitted_ip,
                      job_id=None, category_1_id=None, category_2_id=None):
    now = datetime.now()
    timestamp = now.isoformat()
    month_folder = now.strftime("%Y-%m")
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO submissions
           (token, company_name, timestamp, month_folder, image_file, audio_file,
            submitted_ip, job_id, category_1_id, category_2_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing')""",
        (token, company_name, timestamp, month_folder, image_file, audio_file,
         submitted_ip, job_id, category_1_id, category_2_id),
    )
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def update_submission_transcription(submission_id, transcription, pdf_file):
    conn = get_db()
    conn.execute(
        "UPDATE submissions SET transcription = ?, pdf_file = ?, status = 'complete' WHERE id = ?",
        (transcription, pdf_file, submission_id),
    )
    conn.commit()
    conn.close()


def update_submission_error(submission_id, error_msg):
    conn = get_db()
    conn.execute(
        "UPDATE submissions SET transcription = ?, status = 'error' WHERE id = ?",
        (error_msg, submission_id),
    )
    conn.commit()
    conn.close()


def get_submission(submission_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_submissions(limit=50, token_str=None):
    conn = get_db()
    base = """
        SELECT s.*,
               j.job_name,
               COALESCE(sc_totals.total_amount, 0) AS total_amount
        FROM submissions s
        LEFT JOIN jobs j ON j.id = s.job_id
        LEFT JOIN (
            SELECT submission_id, SUM(amount) AS total_amount
            FROM submission_categories GROUP BY submission_id
        ) sc_totals ON sc_totals.submission_id = s.id
    """
    if token_str:
        rows = conn.execute(
            base + " WHERE s.token = ? ORDER BY s.timestamp DESC LIMIT ?",
            (token_str, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            base + " ORDER BY s.timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_by_token(token):
    conn = get_db()
    rows = conn.execute(
        "SELECT month_folder, COUNT(*) as count FROM submissions WHERE token = ? GROUP BY month_folder ORDER BY month_folder DESC",
        (token,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_by_token_month(token, month):
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*,
               j.job_name,
               COALESCE(sc_totals.total_amount, 0) AS total_amount
        FROM submissions s
        LEFT JOIN jobs j ON j.id = s.job_id
        LEFT JOIN (
            SELECT submission_id, SUM(amount) AS total_amount
            FROM submission_categories GROUP BY submission_id
        ) sc_totals ON sc_totals.submission_id = s.id
        WHERE s.token = ? AND s.month_folder = ?
        ORDER BY s.timestamp DESC
    """, (token, month)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_submission(submission_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM submission_categories WHERE submission_id = ?", (submission_id,))
        conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def claim_next_pending():
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM submissions WHERE status = 'processing' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute(
        "UPDATE submissions SET status = 'transcribing' WHERE id = ? AND status = 'processing'",
        (row["id"],),
    )
    conn.commit()
    claimed = conn.execute(
        "SELECT * FROM submissions WHERE id = ? AND status = 'transcribing'",
        (row["id"],),
    ).fetchone()
    conn.close()
    return dict(claimed) if claimed else None


def toggle_processed(submission_id):
    conn = get_db()
    conn.execute(
        "UPDATE submissions SET processed = CASE WHEN processed = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (submission_id,),
    )
    conn.commit()
    row = conn.execute("SELECT processed FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    return row["processed"] if row else None


def get_submission_categories(submission_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT sc.id, sc.category_id, c.name AS category_name, sc.amount
        FROM submission_categories sc
        JOIN categories c ON c.id = sc.category_id
        WHERE sc.submission_id = ?
        ORDER BY c.name ASC
    """, (submission_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_submission_categories(submission_id, items):
    """Replace all categories for a submission. items = [{category_id, amount}, ...]"""
    conn = get_db()
    conn.execute("DELETE FROM submission_categories WHERE submission_id = ?", (submission_id,))
    now = datetime.now().isoformat()
    for item in items:
        conn.execute(
            "INSERT INTO submission_categories (submission_id, category_id, amount, created_at) VALUES (?, ?, ?, ?)",
            (submission_id, item["category_id"], item.get("amount", 0), now),
        )
    conn.commit()
    conn.close()


def update_submission_vendor(submission_id, vendor):
    conn = get_db()
    conn.execute("UPDATE submissions SET vendor = ? WHERE id = ?", (vendor, submission_id))
    conn.commit()
    conn.close()


def update_submission_job(submission_id, job_id):
    conn = get_db()
    conn.execute("UPDATE submissions SET job_id = ? WHERE id = ?", (job_id or None, submission_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

def create_schedule(employee_id, job_id, token_str, date, start_time, end_time,
                    shift_type, notes, created_by, common_task_id=None,
                    job_task_id=None, custom_note=""):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO schedules
           (employee_id, job_id, token, date, start_time, end_time, shift_type, notes,
            common_task_id, job_task_id, custom_note, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (employee_id, job_id, token_str, date, start_time, end_time, shift_type, notes,
         common_task_id, job_task_id, custom_note, created_by, now, now),
    )
    schedule_id = cur.lastrowid
    conn.commit()
    conn.close()
    return schedule_id


def update_schedule(schedule_id, employee_id, job_id, date, start_time, end_time,
                    shift_type, notes, common_task_id=None, job_task_id=None,
                    custom_note=""):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        """UPDATE schedules
           SET employee_id = ?, job_id = ?, date = ?, start_time = ?, end_time = ?,
               shift_type = ?, notes = ?, common_task_id = ?, job_task_id = ?,
               custom_note = ?, updated_at = ?
           WHERE id = ?""",
        (employee_id, job_id, date, start_time, end_time, shift_type, notes,
         common_task_id, job_task_id, custom_note, now, schedule_id),
    )
    conn.commit()
    conn.close()


def delete_schedule(schedule_id):
    conn = get_db()
    conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()


def get_schedule(schedule_id):
    conn = get_db()
    row = conn.execute(
        """SELECT s.*, e.name as employee_name, j.job_name
           FROM schedules s
           JOIN employees e ON s.employee_id = e.id
           JOIN jobs j ON s.job_id = j.id
           WHERE s.id = ?""",
        (schedule_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_schedules_for_week(token_str, week_start, week_end):
    conn = get_db()
    rows = conn.execute(
        """SELECT s.*, e.name as employee_name, j.job_name
           FROM schedules s
           JOIN employees e ON s.employee_id = e.id
           JOIN jobs j ON s.job_id = j.id
           WHERE s.token = ? AND s.date >= ? AND s.date <= ?
           ORDER BY s.date ASC, s.start_time ASC""",
        (token_str, week_start, week_end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_employee_upcoming_schedules(employee_id, days=7):
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    from datetime import timedelta
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT s.*, j.job_name, j.job_address
           FROM schedules s
           JOIN jobs j ON s.job_id = j.id
           WHERE s.employee_id = ? AND s.date >= ? AND s.date <= ?
           ORDER BY s.date ASC, s.start_time ASC""",
        (employee_id, today, end_date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Job Photos
# ---------------------------------------------------------------------------

def create_job_photo(job_id, token_str, week_folder, image_file, thumb_file="",
                     caption="", taken_by="", latitude=None, longitude=None):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO job_photos
           (job_id, token, week_folder, image_file, thumb_file, caption, taken_by, latitude, longitude, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, token_str, week_folder, image_file, thumb_file, caption, taken_by, latitude, longitude, now),
    )
    photo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return photo_id


def get_job_photo(photo_id):
    conn = get_db()
    row = conn.execute(
        """SELECT jp.*, j.job_name, j.job_address
           FROM job_photos jp
           JOIN jobs j ON jp.job_id = j.id
           WHERE jp.id = ?""",
        (photo_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_job_photos_by_job_week(job_id, week_folder):
    conn = get_db()
    rows = conn.execute(
        """SELECT jp.*, j.job_name
           FROM job_photos jp
           JOIN jobs j ON jp.job_id = j.id
           WHERE jp.job_id = ? AND jp.week_folder = ?
           ORDER BY jp.created_at DESC""",
        (job_id, week_folder),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_photo_weeks(job_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT week_folder, COUNT(*) as photo_count FROM job_photos WHERE job_id = ? GROUP BY week_folder ORDER BY week_folder DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_jobs_with_photos(token_str):
    conn = get_db()
    rows = conn.execute(
        """SELECT j.id, j.job_name, COUNT(jp.id) as photo_count
           FROM job_photos jp
           JOIN jobs j ON jp.job_id = j.id
           WHERE jp.token = ?
           GROUP BY j.id, j.job_name
           ORDER BY j.job_name ASC""",
        (token_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_receipts_for_library(token_str, search=None, date_from=None, date_to=None,
                             job_id=None, limit=50, offset=0):
    """Get completed receipts for employee-facing library view."""
    conn = get_db()
    query = """SELECT s.*, j.job_name, c1.name as cat1_name, c2.name as cat2_name
               FROM submissions s
               LEFT JOIN jobs j ON s.job_id = j.id
               LEFT JOIN categories c1 ON s.category_1_id = c1.id
               LEFT JOIN categories c2 ON s.category_2_id = c2.id
               WHERE s.token = ? AND s.status = 'complete'"""
    params = [token_str]
    if job_id:
        query += " AND s.job_id = ?"
        params.append(int(job_id))
    if search:
        query += " AND s.transcription LIKE ?"
        params.append(f"%{search}%")
    if date_from:
        query += " AND s.timestamp >= ?"
        params.append(date_from)
    if date_to:
        query += " AND s.timestamp <= ?"
        params.append(date_to + "T23:59:59")
    query += " ORDER BY s.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_photos_for_library(token_str, search=None, date_from=None, date_to=None,
                               job_id=None, limit=50, offset=0):
    """Get job photos for employee-facing library view."""
    conn = get_db()
    query = """SELECT jp.*, j.job_name
               FROM job_photos jp
               JOIN jobs j ON jp.job_id = j.id
               WHERE jp.token = ?"""
    params = [token_str]
    if job_id:
        query += " AND jp.job_id = ?"
        params.append(int(job_id))
    if search:
        query += " AND (jp.caption LIKE ? OR j.job_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if date_from:
        query += " AND jp.created_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND jp.created_at <= ?"
        params.append(date_to + "T23:59:59")
    query += " ORDER BY jp.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_job_photo(photo_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM job_photos WHERE id = ?", (photo_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM job_photos WHERE id = ?", (photo_id,))
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


# ---------------------------------------------------------------------------
# Estimates
# ---------------------------------------------------------------------------

def create_estimate(job_id, token_str, title="", audio_file="", created_by=None, status="processing"):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO estimates (job_id, token, title, audio_file, status, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (job_id, token_str, title, audio_file, status, created_by, now),
    )
    estimate_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_estimate(estimate_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_estimates_by_job(job_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM estimates WHERE job_id = ? ORDER BY created_at DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_estimates_by_token(token_str, search=None, limit=50, offset=0):
    conn = get_db()
    query = """SELECT e.*, j.job_name
               FROM estimates e
               LEFT JOIN jobs j ON e.job_id = j.id
               WHERE e.token = ?"""
    params = [token_str]
    if search:
        query += " AND (e.transcription LIKE ? OR e.title LIKE ? OR j.job_name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    query += " ORDER BY e.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_estimate_stats(token_str):
    """Return count + total dollar value for each approval_status, year to date."""
    conn = get_db()
    year_start = datetime.now().strftime("%Y") + "-01-01"
    rows = conn.execute(
        """SELECT approval_status,
                  COUNT(*) as cnt,
                  COALESCE(SUM(estimate_value), 0) as total
           FROM estimates
           WHERE token = ? AND created_at >= ?
           GROUP BY approval_status""",
        (token_str, year_start),
    ).fetchall()
    conn.close()
    stats = {
        "pending": {"count": 0, "total": 0},
        "accepted": {"count": 0, "total": 0},
        "in_progress": {"count": 0, "total": 0},
        "completed": {"count": 0, "total": 0},
        "declined": {"count": 0, "total": 0},
    }
    for r in rows:
        status = r["approval_status"] or "pending"
        if status in stats:
            stats[status] = {"count": r["cnt"], "total": r["total"]}
    return stats


def update_estimate_transcription(estimate_id, transcription):
    conn = get_db()
    conn.execute(
        "UPDATE estimates SET transcription = ?, status = 'complete' WHERE id = ?",
        (transcription, estimate_id),
    )
    conn.commit()
    conn.close()


def update_estimate_error(estimate_id, error_msg):
    conn = get_db()
    conn.execute(
        "UPDATE estimates SET status = 'error', transcription = ? WHERE id = ?",
        (error_msg, estimate_id),
    )
    conn.commit()
    conn.close()


def update_estimate(estimate_id, **kwargs):
    """Update estimate fields. Accepts: title, transcription, notes, status."""
    # Auto-stamp completed_at when approval_status is set to 'completed'
    if kwargs.get("approval_status") == "completed" and not kwargs.get("completed_at"):
        kwargs["completed_at"] = datetime.now().isoformat()
    conn = get_db()
    allowed = {"title", "transcription", "notes", "status", "approval_status", "estimate_value",
                "est_materials_cost", "est_labor_cost", "actual_materials_cost", "actual_labor_cost",
                "actual_collected", "est_labor_hours", "actual_labor_hours",
                "customer_name", "customer_phone", "customer_email",
                "estimate_number", "date_accepted", "expected_completion",
                "sales_tax_rate", "customer_message", "completion_pct", "job_id",
                "client_budget", "append_audio_file", "completed_at"}
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        conn.close()
        return None
    params.append(estimate_id)
    conn.execute(f"UPDATE estimates SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def is_estimate_number_taken(token_str, estimate_number, exclude_id=None):
    """Check if estimate_number is already used by another estimate for this token."""
    conn = get_db()
    sql = "SELECT id FROM estimates WHERE token = ? AND estimate_number = ?"
    params = [token_str, estimate_number]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return row is not None


def delete_estimate(estimate_id):
    conn = get_db()
    conn.execute("DELETE FROM estimate_items WHERE estimate_id = ?", (estimate_id,))
    conn.execute("DELETE FROM estimates WHERE id = ?", (estimate_id,))
    conn.commit()
    conn.close()


def claim_next_pending_estimate():
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM estimates WHERE status = 'processing' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute(
        "UPDATE estimates SET status = 'transcribing' WHERE id = ? AND status = 'processing'",
        (row["id"],),
    )
    conn.commit()
    claimed = conn.execute(
        "SELECT e.*, j.job_name FROM estimates e LEFT JOIN jobs j ON e.job_id = j.id WHERE e.id = ? AND e.status = 'transcribing'",
        (row["id"],),
    ).fetchone()
    conn.close()
    return dict(claimed) if claimed else None


def claim_next_appending_estimate():
    """Atomically claim one estimate with status='appending' for append transcription."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM estimates WHERE status = 'appending' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute(
        "UPDATE estimates SET status = 'transcribing_append' WHERE id = ? AND status = 'appending'",
        (row["id"],),
    )
    conn.commit()
    claimed = conn.execute(
        "SELECT e.*, j.job_name FROM estimates e LEFT JOIN jobs j ON e.job_id = j.id WHERE e.id = ? AND e.status = 'transcribing_append'",
        (row["id"],),
    ).fetchone()
    conn.close()
    return dict(claimed) if claimed else None


def update_estimate_append_transcription(estimate_id, new_text):
    """Append new_text to existing transcription with double-newline separator."""
    conn = get_db()
    existing = conn.execute(
        "SELECT transcription FROM estimates WHERE id = ?", (estimate_id,)
    ).fetchone()
    old = (existing["transcription"] or "").strip() if existing else ""
    combined = (old + "\n\n" + new_text.strip()) if old else new_text.strip()
    conn.execute(
        "UPDATE estimates SET transcription = ?, status = 'complete', append_audio_file = '' WHERE id = ?",
        (combined, estimate_id),
    )
    conn.commit()
    conn.close()


def get_all_job_photos_for_job(job_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM job_photos WHERE job_id = ? ORDER BY created_at DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_job_photo_caption(photo_id, caption):
    conn = get_db()
    conn.execute("UPDATE job_photos SET caption = ? WHERE id = ?", (caption, photo_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Job Tasks
# ---------------------------------------------------------------------------

def create_job_task(job_id, token_str, name, source="manual"):
    conn = get_db()
    now = datetime.now().isoformat()
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM job_tasks WHERE job_id = ?",
        (job_id,),
    ).fetchone()[0]
    cur = conn.execute(
        """INSERT INTO job_tasks (job_id, token, name, source, sort_order, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (job_id, token_str, name, source, max_order + 1, now),
    )
    task_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM job_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_job_tasks(job_id, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM job_tasks WHERE job_id = ? AND is_active = 1 ORDER BY sort_order ASC",
            (job_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM job_tasks WHERE job_id = ? ORDER BY sort_order ASC",
            (job_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_task(task_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM job_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def toggle_job_task(task_id):
    conn = get_db()
    conn.execute(
        "UPDATE job_tasks SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (task_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM job_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Estimate Items
# ---------------------------------------------------------------------------

def get_estimate_items(estimate_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM estimate_items WHERE estimate_id = ? ORDER BY sort_order ASC, id ASC",
        (estimate_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_estimate_item(estimate_id, token_str, description, quantity, unit_price,
                         total, taxable=0, sort_order=0, item_type='product', unit_cost=0):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO estimate_items
           (estimate_id, token, description, quantity, unit_price, unit_cost, total, taxable, sort_order, item_type, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (estimate_id, token_str, description, quantity, unit_price, unit_cost, total, taxable, sort_order, item_type, now),
    )
    item_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM estimate_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_estimate_item(item_id, **kwargs):
    conn = get_db()
    allowed = {"description", "quantity", "unit_price", "unit_cost", "total", "taxable", "sort_order", "item_type"}
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        conn.close()
        return
    params.append(item_id)
    conn.execute(f"UPDATE estimate_items SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_estimate_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM estimate_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Message Snippets
# ---------------------------------------------------------------------------

def get_message_snippets_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM message_snippets WHERE token = ? AND is_active = 1 ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM message_snippets WHERE token = ? ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_message_snippet(snippet_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM message_snippets WHERE id = ?", (snippet_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_message_snippet(name, token_str, sort_order=0):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO message_snippets (name, token, sort_order, created_at) VALUES (?, ?, ?, ?)",
        (name, token_str, sort_order, now),
    )
    conn.commit()
    conn.close()


def update_message_snippet(snippet_id, name, sort_order=None):
    conn = get_db()
    if sort_order is not None:
        conn.execute(
            "UPDATE message_snippets SET name = ?, sort_order = ? WHERE id = ?",
            (name, sort_order, snippet_id),
        )
    else:
        conn.execute("UPDATE message_snippets SET name = ? WHERE id = ?", (name, snippet_id))
    conn.commit()
    conn.close()


def toggle_message_snippet(snippet_id):
    conn = get_db()
    conn.execute(
        "UPDATE message_snippets SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (snippet_id,),
    )
    conn.commit()
    conn.close()


def bulk_deactivate_message_snippets(token_str):
    conn = get_db()
    conn.execute("UPDATE message_snippets SET is_active = 0 WHERE token = ?", (token_str,))
    conn.commit()
    conn.close()


def get_max_sort_order_message_snippets(token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS mx FROM message_snippets WHERE token = ?", (token_str,)
    ).fetchone()
    conn.close()
    return row["mx"] if row else 0


# ---------------------------------------------------------------------------
# Products & Services
# ---------------------------------------------------------------------------

def get_products_services_by_token(token_str, active_only=False):
    conn = get_db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM products_services WHERE token = ? AND is_active = 1 ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM products_services WHERE token = ? ORDER BY sort_order ASC, name ASC",
            (token_str,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_service(ps_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM products_services WHERE id = ?", (ps_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_product_service(name, unit_price, token_str, sort_order=0, unit_cost=0, item_type='product', taxable=0):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO products_services (name, unit_price, unit_cost, item_type, taxable, token, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, unit_price, unit_cost, item_type, taxable, token_str, sort_order, now),
    )
    ps_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM products_services WHERE id = ?", (ps_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_product_service(ps_id, **kwargs):
    conn = get_db()
    allowed = {"name", "unit_price", "unit_cost", "sort_order", "item_type", "taxable"}
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        conn.close()
        return
    params.append(ps_id)
    conn.execute(f"UPDATE products_services SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def toggle_product_service(ps_id):
    conn = get_db()
    conn.execute(
        "UPDATE products_services SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (ps_id,),
    )
    conn.commit()
    conn.close()


def bulk_deactivate_products_services(token_str):
    conn = get_db()
    conn.execute("UPDATE products_services SET is_active = 0 WHERE token = ?", (token_str,))
    conn.commit()
    conn.close()


def get_max_sort_order_products_services(token_str):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS mx FROM products_services WHERE token = ?", (token_str,)
    ).fetchone()
    conn.close()
    return row["mx"] if row else 0
