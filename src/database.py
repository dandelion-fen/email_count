"""
SQLite 数据库模块
"""
from __future__ import annotations
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from src.config import DB_PATH
from src.utils import setup_logger

logger = setup_logger("database")

_local = threading.local()

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    imap_server TEXT NOT NULL DEFAULT 'imap.163.com',
    imap_port INTEGER NOT NULL DEFAULT 993,
    use_ssl INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name TEXT NOT NULL,
    raw_name TEXT NOT NULL DEFAULT '',
    folder_type TEXT NOT NULL DEFAULT 'other',
    uidvalidity INTEGER DEFAULT 0,
    uidnext INTEGER DEFAULT 0,
    last_sync_uid INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(account_id, name)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    folder_id INTEGER NOT NULL REFERENCES folders(id),
    uid INTEGER NOT NULL,
    message_id TEXT DEFAULT '',
    in_reply_to TEXT DEFAULT '',
    references_str TEXT DEFAULT '',
    date TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    subject_normalized TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    from_name TEXT DEFAULT '',
    to_addrs TEXT DEFAULT '',
    cc_addrs TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    body_text TEXT DEFAULT '',
    body_html_text TEXT DEFAULT '',
    has_attachments INTEGER DEFAULT 0,
    attachment_names TEXT DEFAULT '',
    attachment_types TEXT DEFAULT '',
    is_sent_by_me INTEGER DEFAULT 0,
    is_auto_reply INTEGER DEFAULT 0,
    is_bounce INTEGER DEFAULT 0,
    is_system_notification INTEGER DEFAULT 0,
    content_hash TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(account_id, folder_id, uid)
);

CREATE TABLE IF NOT EXISTS message_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    address_type TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    subject_normalized TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS thread_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    message_id INTEGER NOT NULL REFERENCES messages(id),
    match_method TEXT DEFAULT '',
    UNIQUE(thread_id, message_id)
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name TEXT NOT NULL DEFAULT '',
    institution TEXT DEFAULT '',
    first_sent_at TEXT DEFAULT '',
    last_sent_at TEXT DEFAULT '',
    send_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 0,
    review_reasons TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teacher_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    email TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    UNIQUE(teacher_id, email)
);

CREATE TABLE IF NOT EXISTS teacher_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    message_id INTEGER NOT NULL REFERENCES messages(id),
    message_role TEXT DEFAULT '',
    UNIQUE(teacher_id, message_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    analysis_type TEXT NOT NULL DEFAULT 'rule',
    reply_status TEXT DEFAULT '',
    reply_summary TEXT DEFAULT '',
    evidence_sentences TEXT DEFAULT '',
    admission_intent TEXT DEFAULT '',
    action_required TEXT DEFAULT '',
    recommended_next_step TEXT DEFAULT '',
    actual_responder_role TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    ambiguity_reason TEXT DEFAULT '',
    my_reply_status TEXT DEFAULT '',
    model_name TEXT DEFAULT '',
    analysis_time TEXT DEFAULT '',
    input_hash TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS manual_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT DEFAULT '',
    new_value TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    folder_id INTEGER NOT NULL REFERENCES folders(id),
    uidvalidity INTEGER DEFAULT 0,
    uidnext INTEGER DEFAULT 0,
    last_sync_uid INTEGER DEFAULT 0,
    last_sync_time TEXT DEFAULT '',
    UNIQUE(account_id, folder_id)
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    start_time TEXT NOT NULL,
    end_time TEXT DEFAULT '',
    status TEXT DEFAULT 'running',
    folders_scanned INTEGER DEFAULT 0,
    messages_found INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scan_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id INTEGER REFERENCES scan_runs(id),
    folder_name TEXT DEFAULT '',
    uid INTEGER DEFAULT 0,
    error_type TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_account ON messages(account_id);
CREATE INDEX IF NOT EXISTS idx_messages_folder ON messages(folder_id);
CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id);
CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_email);
CREATE INDEX IF NOT EXISTS idx_messages_subject_norm ON messages(subject_normalized);
CREATE INDEX IF NOT EXISTS idx_messages_sent ON messages(is_sent_by_me);
CREATE INDEX IF NOT EXISTS idx_teacher_emails_email ON teacher_emails(email);
CREATE INDEX IF NOT EXISTS idx_thread_messages_thread ON thread_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_thread_messages_msg ON thread_messages(message_id);
CREATE INDEX IF NOT EXISTS idx_teacher_messages_teacher ON teacher_messages(teacher_id);
CREATE INDEX IF NOT EXISTS idx_analyses_teacher ON analyses(teacher_id);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    path = db_path or DB_PATH
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(path, timeout=30)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db(db_path: str | None = None) -> None:
    """初始化数据库表结构"""
    conn = get_connection(db_path)
    conn.executescript(CREATE_TABLES_SQL)
    conn.commit()
    logger.info("数据库初始化完成")


def close_db() -> None:
    """关闭当前线程的数据库连接"""
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None


def reset_connection(db_path: str | None = None) -> sqlite3.Connection:
    """重置并返回新连接"""
    close_db()
    return get_connection(db_path)


# ── 账户操作 ──

def upsert_account(email: str, imap_server: str = "imap.163.com",
                   imap_port: int = 993, use_ssl: bool = True,
                   db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "SELECT id FROM accounts WHERE email = ?", (email,))
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE accounts SET imap_server=?, imap_port=?, use_ssl=?, updated_at=datetime('now') WHERE id=?",
            (imap_server, imap_port, int(use_ssl), row["id"]))
        conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO accounts (email, imap_server, imap_port, use_ssl) VALUES (?,?,?,?)",
        (email, imap_server, imap_port, int(use_ssl)))
    conn.commit()
    return cur.lastrowid


# ── 文件夹操作 ──

def upsert_folder(account_id: int, name: str, raw_name: str = "",
                  folder_type: str = "other", db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "SELECT id FROM folders WHERE account_id=? AND name=?",
        (account_id, name))
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE folders SET raw_name=?, folder_type=?, updated_at=datetime('now') WHERE id=?",
            (raw_name, folder_type, row["id"]))
        conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO folders (account_id, name, raw_name, folder_type) VALUES (?,?,?,?)",
        (account_id, name, raw_name, folder_type))
    conn.commit()
    return cur.lastrowid


def get_folders(account_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM folders WHERE account_id=?", (account_id,)).fetchall()
    return [dict(r) for r in rows]


def update_folder_sync(folder_id: int, uidvalidity: int, uidnext: int,
                       last_sync_uid: int, message_count: int,
                       db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE folders SET uidvalidity=?, uidnext=?, last_sync_uid=?, message_count=?, updated_at=datetime('now') WHERE id=?",
        (uidvalidity, uidnext, last_sync_uid, message_count, folder_id))
    conn.commit()


# ── 邮件操作 ──

def message_exists(account_id: int, folder_id: int, uid: int,
                   db_path: str | None = None) -> bool:
    conn = get_connection(db_path)
    cur = conn.execute(
        "SELECT 1 FROM messages WHERE account_id=? AND folder_id=? AND uid=?",
        (account_id, folder_id, uid))
    return cur.fetchone() is not None


def insert_message(data: dict, db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    fields = [
        "account_id", "folder_id", "uid", "message_id", "in_reply_to",
        "references_str", "date", "subject", "subject_normalized",
        "from_email", "from_name", "to_addrs", "cc_addrs", "reply_to",
        "body_text", "body_html_text", "has_attachments", "attachment_names",
        "attachment_types", "is_sent_by_me", "is_auto_reply", "is_bounce",
        "is_system_notification", "content_hash",
    ]
    vals = [data.get(f, "") for f in fields]
    placeholders = ",".join(["?"] * len(fields))
    cols = ",".join(fields)
    try:
        cur = conn.execute(f"INSERT INTO messages ({cols}) VALUES ({placeholders})", vals)
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return -1


def get_all_messages(account_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM messages WHERE account_id=? ORDER BY date",
        (account_id,)).fetchall()
    return [dict(r) for r in rows]


def get_sent_messages(account_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM messages WHERE account_id=? AND is_sent_by_me=1 ORDER BY date",
        (account_id,)).fetchall()
    return [dict(r) for r in rows]


def get_received_messages(account_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM messages WHERE account_id=? AND is_sent_by_me=0 ORDER BY date",
        (account_id,)).fetchall()
    return [dict(r) for r in rows]


# ── 线程操作 ──

def insert_thread(account_id: int, subject_normalized: str,
                  db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "INSERT INTO threads (account_id, subject_normalized) VALUES (?,?)",
        (account_id, subject_normalized))
    conn.commit()
    return cur.lastrowid


def link_thread_message(thread_id: int, message_id: int,
                        match_method: str = "", db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO thread_messages (thread_id, message_id, match_method) VALUES (?,?,?)",
            (thread_id, message_id, match_method))
        conn.commit()
    except sqlite3.IntegrityError:
        pass


def get_thread_messages(thread_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT m.* FROM messages m JOIN thread_messages tm ON m.id=tm.message_id WHERE tm.thread_id=? ORDER BY m.date",
        (thread_id,)).fetchall()
    return [dict(r) for r in rows]


# ── 导师操作 ──

def insert_teacher(account_id: int, name: str, institution: str = "",
                   confidence: float = 0.0, needs_review: bool = False,
                   review_reasons: str = "", db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "INSERT INTO teachers (account_id,name,institution,confidence,needs_review,review_reasons) VALUES (?,?,?,?,?,?)",
        (account_id, name, institution, confidence, int(needs_review), review_reasons))
    conn.commit()
    return cur.lastrowid


def add_teacher_email(teacher_id: int, email: str, is_primary: bool = False,
                      source: str = "", db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO teacher_emails (teacher_id,email,is_primary,source) VALUES (?,?,?,?)",
            (teacher_id, email, int(is_primary), source))
        conn.commit()
    except sqlite3.IntegrityError:
        pass


def link_teacher_message(teacher_id: int, message_id: int,
                         message_role: str = "", db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO teacher_messages (teacher_id,message_id,message_role) VALUES (?,?,?)",
            (teacher_id, message_id, message_role))
        conn.commit()
    except sqlite3.IntegrityError:
        pass


def get_all_teachers(account_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM teachers WHERE account_id=? ORDER BY name",
        (account_id,)).fetchall()
    return [dict(r) for r in rows]


def get_teacher_emails(teacher_id: int, db_path: str | None = None) -> list[str]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT email FROM teacher_emails WHERE teacher_id=?",
        (teacher_id,)).fetchall()
    return [r["email"] for r in rows]


def get_teacher_messages(teacher_id: int, db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT m.*, tm.message_role FROM messages m
           JOIN teacher_messages tm ON m.id=tm.message_id
           WHERE tm.teacher_id=? ORDER BY m.date""",
        (teacher_id,)).fetchall()
    return [dict(r) for r in rows]


def update_teacher(teacher_id: int, updates: dict, db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [teacher_id]
    conn.execute(f"UPDATE teachers SET {sets}, updated_at=datetime('now') WHERE id=?", vals)
    conn.commit()


# ── 分析结果 ──

def insert_analysis(data: dict, db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    fields = [
        "teacher_id", "analysis_type", "reply_status", "reply_summary",
        "evidence_sentences", "admission_intent", "action_required",
        "recommended_next_step", "actual_responder_role", "confidence",
        "ambiguity_reason", "my_reply_status", "model_name",
        "analysis_time", "input_hash",
    ]
    vals = [data.get(f, "") for f in fields]
    placeholders = ",".join(["?"] * len(fields))
    cols = ",".join(fields)
    cur = conn.execute(f"INSERT INTO analyses ({cols}) VALUES ({placeholders})", vals)
    conn.commit()
    return cur.lastrowid


def get_latest_analysis(teacher_id: int, analysis_type: str = "rule",
                        db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM analyses WHERE teacher_id=? AND analysis_type=? ORDER BY created_at DESC LIMIT 1",
        (teacher_id, analysis_type)).fetchone()
    return dict(row) if row else None


# ── 人工覆盖 ──

def add_override(entity_type: str, entity_id: int, field_name: str,
                 old_value: str, new_value: str, db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO manual_overrides (entity_type,entity_id,field_name,old_value,new_value) VALUES (?,?,?,?,?)",
        (entity_type, entity_id, field_name, old_value, new_value))
    conn.commit()


def get_overrides(entity_type: str, entity_id: int,
                  db_path: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM manual_overrides WHERE entity_type=? AND entity_id=? ORDER BY created_at DESC",
        (entity_type, entity_id)).fetchall()
    return [dict(r) for r in rows]


def has_override(entity_type: str, entity_id: int, field_name: str,
                 db_path: str | None = None) -> bool:
    conn = get_connection(db_path)
    cur = conn.execute(
        "SELECT 1 FROM manual_overrides WHERE entity_type=? AND entity_id=? AND field_name=?",
        (entity_type, entity_id, field_name))
    return cur.fetchone() is not None


# ── 扫描记录 ──

def start_scan_run(account_id: int, db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "INSERT INTO scan_runs (account_id,start_time,status) VALUES (?,datetime('now'),'running')",
        (account_id,))
    conn.commit()
    return cur.lastrowid


def finish_scan_run(run_id: int, folders: int, messages: int, errors: int,
                    status: str = "completed", db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE scan_runs SET end_time=datetime('now'),status=?,folders_scanned=?,messages_found=?,errors_count=? WHERE id=?",
        (status, folders, messages, errors, run_id))
    conn.commit()


def add_scan_error(run_id: int, folder: str, uid: int,
                   error_type: str, error_msg: str, db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO scan_errors (scan_run_id,folder_name,uid,error_type,error_message) VALUES (?,?,?,?,?)",
        (run_id, folder, uid, error_type, error_msg[:500]))
    conn.commit()


# ── 设置 ──

def get_setting(key: str, default: str = "", db_path: str | None = None) -> str:
    conn = get_connection(db_path)
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str, db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?,updated_at=datetime('now')",
        (key, value, value))
    conn.commit()


# ── 数据清理 ──

def clear_analysis_data(account_id: int, db_path: str | None = None) -> None:
    """清除分析结果但保留邮件数据"""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM analyses WHERE teacher_id IN (SELECT id FROM teachers WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM teacher_messages WHERE teacher_id IN (SELECT id FROM teachers WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM teacher_emails WHERE teacher_id IN (SELECT id FROM teachers WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM thread_messages WHERE thread_id IN (SELECT id FROM threads WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM threads WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM teachers WHERE account_id=?", (account_id,))
    conn.commit()


def clear_all_data(account_id: int, db_path: str | None = None) -> None:
    """清除指定账户的全部数据"""
    clear_analysis_data(account_id, db_path)
    conn = get_connection(db_path)
    conn.execute("DELETE FROM scan_errors WHERE scan_run_id IN (SELECT id FROM scan_runs WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM scan_runs WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM messages WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM sync_state WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM folders WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM manual_overrides WHERE entity_type='teacher' AND entity_id NOT IN (SELECT id FROM teachers)", )
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.commit()
