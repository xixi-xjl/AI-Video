import os
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")


def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_vip INTEGER DEFAULT 0,
                vip_expire_at TEXT,
                daily_summary_count INTEGER DEFAULT 0,
                last_summary_date TEXT,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'cny',
                status TEXT DEFAULT 'pending',
                plan_type TEXT DEFAULT 'monthly',
                stripe_session_id TEXT UNIQUE,
                stripe_payment_intent_id TEXT,
                paid_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no);
            CREATE INDEX IF NOT EXISTS idx_orders_stripe_session_id ON orders(stripe_session_id);

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_url TEXT NOT NULL,
                video_title TEXT DEFAULT '',
                summary_text TEXT NOT NULL,
                mindmap_md TEXT DEFAULT '',
                subtitle_json TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, video_url)
            );

            CREATE INDEX IF NOT EXISTS idx_summaries_user_id ON summaries(user_id);
            CREATE INDEX IF NOT EXISTS idx_summaries_video_url ON summaries(video_url);
        """)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass


def ensure_admin_account():
    """根据环境变量创建或更新管理员账号。"""
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return

    from auth import hash_password

    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        hashed = hash_password(password)
        if row:
            conn.execute(
                "UPDATE users SET password_hash = ?, is_admin = 1, updated_at = datetime('now') WHERE id = ?",
                (hashed, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)",
                (email, hashed),
            )


FREE_DAILY_SUMMARY_LIMIT = 3


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(email: str, password_hash: str) -> dict:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return {"id": cursor.lastrowid, "email": email}


def check_summary_permission(user_id: int) -> tuple[bool, int]:
    """检查配额，不扣减次数。返回 (allowed, remaining)，-1 表示 VIP 无限。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, 0

        if user["is_vip"] and user["vip_expire_at"]:
            expire = datetime.fromisoformat(user["vip_expire_at"])
            if expire > datetime.now(timezone.utc):
                return True, -1

        if user["last_summary_date"] != today:
            return True, FREE_DAILY_SUMMARY_LIMIT

        current = user["daily_summary_count"]
        if current >= FREE_DAILY_SUMMARY_LIMIT:
            return False, 0

        return True, FREE_DAILY_SUMMARY_LIMIT - current


def increment_summary_count(user_id: int) -> int:
    """总结成功后扣减配额，返回剩余次数（VIP 返回 -1）。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return 0

        if user["is_vip"] and user["vip_expire_at"]:
            expire = datetime.fromisoformat(user["vip_expire_at"])
            if expire > datetime.now(timezone.utc):
                return -1

        if user["last_summary_date"] != today:
            conn.execute(
                "UPDATE users SET daily_summary_count = 1, last_summary_date = ? WHERE id = ?",
                (today, user_id),
            )
            return FREE_DAILY_SUMMARY_LIMIT - 1

        conn.execute(
            "UPDATE users SET daily_summary_count = daily_summary_count + 1 WHERE id = ?",
            (user_id,),
        )
        current = user["daily_summary_count"] + 1
        return max(FREE_DAILY_SUMMARY_LIMIT - current, 0)


def check_and_increment_summary(user_id: int) -> tuple[bool, int]:
    """兼容旧调用：检查并扣减（建议新代码使用 check + increment 分离）。"""
    allowed, remaining = check_summary_permission(user_id)
    if not allowed:
        return False, 0
    if remaining == -1:
        return True, -1
    new_remaining = increment_summary_count(user_id)
    return True, new_remaining


def save_summary(
    user_id: int,
    video_url: str,
    video_title: str,
    summary_text: str,
    mindmap_md: str = "",
    subtitle_json: str = "",
) -> dict:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO summaries (user_id, video_url, video_title, summary_text, mindmap_md, subtitle_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, video_url) DO UPDATE SET
                video_title = excluded.video_title,
                summary_text = excluded.summary_text,
                mindmap_md = excluded.mindmap_md,
                subtitle_json = excluded.subtitle_json,
                updated_at = datetime('now')
            """,
            (user_id, video_url, video_title, summary_text, mindmap_md, subtitle_json),
        )
        row = conn.execute(
            "SELECT * FROM summaries WHERE user_id = ? AND video_url = ?",
            (user_id, video_url),
        ).fetchone()
        return dict(row) if row else {}


def get_summary_by_url(user_id: int, video_url: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM summaries WHERE user_id = ? AND video_url = ?",
            (user_id, video_url),
        ).fetchone()
        return dict(row) if row else None


def get_user_summaries(user_id: int, limit: int = 20) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, video_url, video_title, created_at, updated_at FROM summaries WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def create_order(user_id: int, order_no: str, amount: int, currency: str = "cny", plan_type: str = "monthly") -> dict:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO orders (order_no, user_id, amount, currency, plan_type) VALUES (?, ?, ?, ?, ?)",
            (order_no, user_id, amount, currency, plan_type),
        )
        return {"order_no": order_no, "user_id": user_id, "amount": amount}


def update_order_stripe_session(order_no: str, session_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE orders SET stripe_session_id = ?, updated_at = datetime('now') WHERE order_no = ?",
            (session_id, order_no),
        )


def complete_order(session_id: str, payment_intent_id: str) -> dict | None:
    """
    支付完成时更新订单状态、激活 VIP。
    使用事务保证幂等：只有 pending 状态的订单才会被更新。
    """
    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE stripe_session_id = ? AND status = 'pending'",
            (session_id,),
        ).fetchone()

        if not order:
            return None

        now = datetime.now(timezone.utc).isoformat()

        from dateutil.relativedelta import relativedelta
        user = conn.execute("SELECT * FROM users WHERE id = ?", (order["user_id"],)).fetchone()

        current_expire = None
        if user["vip_expire_at"]:
            try:
                current_expire = datetime.fromisoformat(user["vip_expire_at"])
            except ValueError:
                pass

        base_time = datetime.now(timezone.utc)
        if current_expire and current_expire > base_time:
            base_time = current_expire

        if order["plan_type"] == "monthly":
            new_expire = base_time + relativedelta(months=1)
        elif order["plan_type"] == "yearly":
            new_expire = base_time + relativedelta(years=1)
        else:
            new_expire = base_time + relativedelta(months=1)

        conn.execute(
            "UPDATE orders SET status = 'paid', stripe_payment_intent_id = ?, paid_at = ?, updated_at = ? WHERE id = ?",
            (payment_intent_id, now, now, order["id"]),
        )

        conn.execute(
            "UPDATE users SET is_vip = 1, vip_expire_at = ?, updated_at = ? WHERE id = ?",
            (new_expire.isoformat(), now, order["user_id"]),
        )

        return dict(order)


def get_order_by_no(order_no: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()
        return dict(row) if row else None


def get_user_orders(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_admin_stats() -> dict:
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        vip_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_vip = 1 AND vip_expire_at IS NOT NULL"
        ).fetchone()["c"]
        total_orders = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        paid_orders = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status = 'paid'").fetchone()["c"]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM orders WHERE status = 'paid'"
        ).fetchone()["s"]
        total_summaries = conn.execute("SELECT COUNT(*) AS c FROM summaries").fetchone()["c"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_summaries = conn.execute(
            "SELECT COUNT(*) AS c FROM summaries WHERE date(updated_at) = ?", (today,)
        ).fetchone()["c"]
        return {
            "total_users": total_users,
            "vip_users": vip_users,
            "total_orders": total_orders,
            "paid_orders": paid_orders,
            "revenue_cents": revenue,
            "total_summaries": total_summaries,
            "today_summaries": today_summaries,
        }


def list_users(page: int = 1, limit: int = 20, q: str = "") -> dict:
    offset = (page - 1) * limit
    with get_db() as conn:
        if q:
            like = f"%{q}%"
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE email LIKE ?", (like,)
            ).fetchone()["c"]
            rows = conn.execute(
                """
                SELECT id, email, is_vip, vip_expire_at, daily_summary_count,
                       last_summary_date, is_admin, created_at
                FROM users WHERE email LIKE ?
                ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (like, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            rows = conn.execute(
                """
                SELECT id, email, is_vip, vip_expire_at, daily_summary_count,
                       last_summary_date, is_admin, created_at
                FROM users ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return {"total": total, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


def admin_update_user(user_id: int, **fields) -> dict | None:
    allowed = {"is_vip", "vip_expire_at", "daily_summary_count", "last_summary_date", "is_admin"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_user_by_id(user_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
    return get_user_by_id(user_id)


def list_all_orders(page: int = 1, limit: int = 20) -> dict:
    offset = (page - 1) * limit
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        rows = conn.execute(
            """
            SELECT o.*, u.email AS user_email
            FROM orders o LEFT JOIN users u ON o.user_id = u.id
            ORDER BY o.created_at DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return {"total": total, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


def list_all_summaries(page: int = 1, limit: int = 20) -> dict:
    offset = (page - 1) * limit
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM summaries").fetchone()["c"]
        rows = conn.execute(
            """
            SELECT s.id, s.user_id, s.video_url, s.video_title, s.created_at, s.updated_at,
                   u.email AS user_email,
                   LENGTH(s.summary_text) AS summary_length
            FROM summaries s LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.updated_at DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return {"total": total, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


def delete_summary_by_id(summary_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
        return cur.rowcount > 0
