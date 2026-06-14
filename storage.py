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


def get_stats():
    """إحصائيات الأعضاء: الإجمالي + حسب اللغة + الجدد اليوم وآخر 7 أيام."""
    today = time.strftime("%Y-%m-%d")
    week_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
    with _conn() as c:
        def one(sql, params=()):
            return c.execute(sql, params).fetchone()["n"]

        return {
            "total": one("SELECT COUNT(*) AS n FROM users"),
            "ar": one("SELECT COUNT(*) AS n FROM users WHERE language = 'ar'"),
            "en": one("SELECT COUNT(*) AS n FROM users WHERE language = 'en'"),
            "today": one(
                "SELECT COUNT(*) AS n FROM users WHERE substr(joined_at,1,10) = ?",
                (today,),
            ),
            "week": one(
                "SELECT COUNT(*) AS n FROM users WHERE substr(joined_at,1,10) >= ?",
                (week_ago,),
            ),
        }


def export_users_text():
    """نص يحتوي كل الأعضاء (لإرساله كملف للأدمن)."""
    lines = ["user_id | username | name | lang | joined_at"]
    for u in get_all_users():
        lines.append(
            f"{u['user_id']} | @{u['username'] or '-'} | "
            f"{u['first_name'] or '-'} | {u['language'] or '-'} | {u['joined_at'] or '-'}"
        )
    return "\n".join(lines)
