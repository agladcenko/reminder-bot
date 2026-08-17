import sqlite3
from datetime import datetime

DB_NAME = "reminders.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            timezone TEXT NOT NULL DEFAULT 'Europe/Moscow'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            repeat_type TEXT NOT NULL,
            days_before INTEGER NOT NULL DEFAULT 3,
            notify_time TEXT NOT NULL DEFAULT '09:00',
            is_done INTEGER NOT NULL DEFAULT 0,
            is_paused INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    conn.commit()
    conn.close()

def ensure_user(user_id: int, timezone: str = "Europe/Moscow") -> None:
    """Регистрирует пользователя, если его ещё нет."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, timezone) VALUES (?, ?)",
        (user_id, timezone),
    )
    conn.commit()
    conn.close()


def get_timezone(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT timezone FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["timezone"] if row else "Europe/Moscow"


def set_timezone(user_id: int, timezone: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET timezone = ? WHERE user_id = ?", (timezone, user_id)
    )
    conn.commit()
    conn.close()


def add_event(
        user_id: int,
        title: str,
        due_date: str,
        repeat_type: str,
        days_before: int = 3,
        notify_time: str = "09:00",
) -> int:
    """Создаёт событие, возвращает его id."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO events
            (user_id, title, due_date, repeat_type, days_before, notify_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title,
            due_date,
            repeat_type,
            days_before,
            notify_time,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_user_events(user_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY due_date",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_event(event_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    conn.close()
    return row


def mark_done(event_id: int, next_due_date: str | None) -> None:
    """
    Отмечает выполнение. Если событие повторяемое — переносит срок
    на следующий и снимает отметку. Если разовое — помечает выполненным.
    """
    conn = get_connection()
    if next_due_date:
        conn.execute(
            "UPDATE events SET due_date = ?, is_done = 0 WHERE id = ?",
            (next_due_date, event_id),
        )
    else:
        conn.execute("UPDATE events SET is_done = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def delete_event(event_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def get_all_active_events() -> list[sqlite3.Row]:
    """Все события, по которым нужно проверять напоминания."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM events WHERE is_done = 0 AND is_paused = 0"
    ).fetchall()
    conn.close()
    return rows

def set_paused(event_id: int, paused: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE events SET is_paused = ? WHERE id = ?",
        (1 if paused else 0, event_id),
    )
    conn.commit()
    conn.close()