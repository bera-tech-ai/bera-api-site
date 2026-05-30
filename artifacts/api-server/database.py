"""
SQLite database setup and CRUD operations for Bruce Bera AI API.
"""
import aiosqlite
import secrets
import string
import json
import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "bruce_ai.db"

RATE_LIMITS = {
    "free": 100,
    "pro": 10000,
    "enterprise": -1,  # unlimited
}


def _generate_api_key() -> str:
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(32))
    return f"bruce_live_{random_part}"


async def init_db():
    """Initialize the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                rate_limit_per_day INTEGER NOT NULL DEFAULT 100,
                requests_used_today INTEGER NOT NULL DEFAULT 0,
                last_reset_date TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_active_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                user_message TEXT NOT NULL,
                actions_taken TEXT NOT NULL DEFAULT '[]',
                response TEXT,
                response_time_ms INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 1,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                ip_address TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)"
        )
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def _reset_daily_counts_if_needed(db: aiosqlite.Connection, user_id: int):
    """Reset requests_used_today if it's a new calendar day."""
    today_str = date.today().isoformat()
    await db.execute(
        """
        UPDATE users SET requests_used_today = 0, last_reset_date = ?
        WHERE id = ? AND (last_reset_date IS NULL OR last_reset_date != ?)
        """,
        (today_str, user_id, today_str),
    )


async def create_user(email: str, name: str, plan: str = "free", rate_limit: Optional[int] = None) -> dict:
    """Create a new user and return their API key."""
    api_key = _generate_api_key()
    rl = rate_limit if rate_limit is not None else RATE_LIMITS.get(plan, 100)
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO users (email, name, api_key, plan, rate_limit_per_day, last_reset_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, name, api_key, plan, rl, date.today().isoformat()),
            )
            await db.commit()
            return {"api_key": api_key, "plan": plan}
        except aiosqlite.IntegrityError:
            raise ValueError(f"Email '{email}' already registered")


async def get_user_by_api_key(api_key: str) -> Optional[dict]:
    """Fetch user by API key, resetting daily counter if needed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE api_key = ?", (api_key,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
        user = dict(row)
        await _reset_daily_counts_if_needed(db, user["id"])
        await db.commit()
        # Re-fetch to get updated count
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user["id"],)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def increment_request_count(user_id: int):
    """Increment requests_used_today and update last_active_at."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET requests_used_today = requests_used_today + 1,
                last_active_at = datetime('now')
            WHERE id = ?
            """,
            (user_id,),
        )
        await db.commit()


async def revoke_key(api_key: str) -> bool:
    """Delete a user by their API key. Returns True if found."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE api_key = ?", (api_key,))
        await db.commit()
        return cursor.rowcount > 0


async def revoke_key_by_id(user_id: int) -> bool:
    """Delete a user by their id. Returns True if found."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0


async def log_request(
    user_id: Optional[int],
    user_message: str,
    actions_taken: list,
    response: Optional[str],
    response_time_ms: int,
    success: bool,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO requests (user_id, user_message, actions_taken, response, response_time_ms, success)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_message,
                json.dumps(actions_taken),
                response,
                response_time_ms,
                1 if success else 0,
            ),
        )
        await db.commit()


async def add_audit_log(
    user_id: Optional[int],
    action: str,
    details: dict,
    ip_address: str = "",
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO audit_log (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, action, json.dumps(details), ip_address),
        )
        await db.commit()


async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT COUNT(*) AS cnt FROM users") as c:
            row = await c.fetchone()
            total_users = row["cnt"]

        async with db.execute("SELECT COUNT(*) AS cnt FROM requests") as c:
            row = await c.fetchone()
            total_requests = row["cnt"]

        async with db.execute(
            "SELECT AVG(response_time_ms) AS avg_rt FROM requests"
        ) as c:
            row = await c.fetchone()
            avg_rt = round(row["avg_rt"] or 0, 1)

        today_str = date.today().isoformat()
        async with db.execute(
            "SELECT COUNT(*) AS cnt FROM requests WHERE DATE(timestamp) = ?",
            (today_str,),
        ) as c:
            row = await c.fetchone()
            requests_today = row["cnt"]

        async with db.execute(
            """SELECT COUNT(DISTINCT user_id) AS cnt FROM requests
               WHERE DATE(timestamp) = ?""",
            (today_str,),
        ) as c:
            row = await c.fetchone()
            active_today = row["cnt"]

        return {
            "total_users": total_users,
            "total_requests": total_requests,
            "avg_response_time": avg_rt,
            "requests_today": requests_today,
            "active_users_today": active_today,
        }


async def get_audit_log(limit: int = 100) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT a.*, u.email AS user_email
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_requests(limit: int = 100) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT r.*, u.email AS user_email
            FROM requests r
            LEFT JOIN users u ON r.user_id = u.id
            ORDER BY r.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
