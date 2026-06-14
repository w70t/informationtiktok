"""
storage.py
----------
تخزين أعضاء البوت في SQLite (بدون أي خادم خارجي) لاستخدامه في:
  - حفظ الاسم واليوزر ولغة كل عضو.
  - إرسال رسالة جماعية لاحقاً لكل الأعضاء.
الملف bot_data.db يُنشأ تلقائياً بجانب الكود.
"""

import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.db")
_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _lock, _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                language   TEXT DEFAULT 'ar',
                joined_at  TEXT
            )"""
        )


def add_user(user_id, username, first_name):
    """إضافة عضو جديد أو تحديث بياناته (يحافظ على لغته السابقة)."""
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO users (user_id, username, first_name, joined_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username   = excluded.username,
                   first_name = excluded.first_name""",
            (user_id, username, first_name, time.strftime("%Y-%m-%d %H:%M:%S")),
        )


def set_language(user_id, language):
    with _lock, _conn() as c:
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))


def get_language(user_id):
    with _conn() as c:
        row = c.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["language"] if row and row["language"] else None


def get_all_user_ids():
    with _conn() as c:
        return [r["user_id"] for r in c.execute("SELECT user_id FROM users").fetchall()]


def count_users():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_all_users():
    """قائمة بكل الأعضاء (للتصدير أو المراجعة)."""
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT user_id, username, first_name, language, joined_at FROM users"
        ).fetchall()]
