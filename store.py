import json
import time
import uuid
from typing import Dict, List, Optional

from db import get_connection
from models.activity import Activity

WEIGHT_LB = "weight_lb"
STEPS = "steps"
SLEEP_MINUTES = "sleep_minutes"
SLEEP_SCORE = "sleep_score"
RESTING_HR = "resting_hr"
READINESS = "readiness"


def init_store():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            source TEXT NOT NULL,
            id TEXT NOT NULL,
            activity_type TEXT,
            name TEXT,
            date TEXT NOT NULL,
            duration_minutes REAL,
            distance_miles REAL,
            avg_mph REAL,
            elevation_gain_ft REAL,
            calories REAL,
            load_score REAL,
            synced_at INTEGER NOT NULL,
            PRIMARY KEY (source, id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date)")

    columns = {r["name"] for r in cur.execute("PRAGMA table_info(activities)")}
    for name, ddl in [
        ("is_primary", "INTEGER NOT NULL DEFAULT 1"),
        ("start_ts", "INTEGER"),
        ("active_zone_minutes", "REAL"),
    ]:
        if name not in columns:
            cur.execute(f"ALTER TABLE activities ADD COLUMN {name} {ddl}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT,
            extra TEXT,
            synced_at INTEGER NOT NULL,
            PRIMARY KEY (date, metric)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS personal_bests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            value REAL,
            display_value TEXT,
            unit TEXT,
            date_achieved TEXT,
            source TEXT,
            updated_at INTEGER NOT NULL,
            UNIQUE(category, name)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tools TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON conversation_messages(conversation_id, id)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            source TEXT PRIMARY KEY,
            last_synced_at INTEGER,
            status TEXT,
            detail TEXT,
            count INTEGER
        )
    """)

    conn.commit()
    conn.close()


def upsert_activities(activities: List[Activity]) -> int:
    if not activities:
        return 0

    now = int(time.time())
    rows = [
        (
            a.source, a.id, a.activity_type, a.name, a.date, a.start_ts,
            a.duration_minutes, a.distance_miles, a.avg_mph,
            a.elevation_gain_ft, a.calories, a.active_zone_minutes, a.load_score, now,
        )
        for a in activities
    ]

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO activities
            (source, id, activity_type, name, date, start_ts, duration_minutes,
             distance_miles, avg_mph, elevation_gain_ft, calories,
             active_zone_minutes, load_score, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, id) DO UPDATE SET
            activity_type=excluded.activity_type,
            name=excluded.name,
            date=excluded.date,
            start_ts=excluded.start_ts,
            duration_minutes=excluded.duration_minutes,
            distance_miles=excluded.distance_miles,
            avg_mph=excluded.avg_mph,
            elevation_gain_ft=excluded.elevation_gain_ft,
            calories=excluded.calories,
            active_zone_minutes=excluded.active_zone_minutes,
            load_score=excluded.load_score,
            synced_at=excluded.synced_at
    """, rows)
    conn.commit()
    conn.close()

    return len(rows)


def delete_activities(source: str, ids: List[str]) -> int:
    if not ids:
        return 0

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        "DELETE FROM activities WHERE source = ? AND id = ?",
        [(source, str(i)) for i in ids],
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    return deleted


def get_activities(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: Optional[str] = None,
    activity_type: Optional[str] = None,
    include_duplicates: bool = False,
) -> List[Activity]:
    clauses = []
    params = []

    if not include_duplicates:
        clauses.append("is_primary = 1")

    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    if source:
        clauses.append("LOWER(source) = ?")
        params.append(source.lower())
    if activity_type:
        clauses.append("LOWER(activity_type) = ?")
        params.append(activity_type.lower())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM activities {where} ORDER BY date DESC", params)
    rows = cur.fetchall()
    conn.close()

    return [
        Activity(
            id=r["id"], source=r["source"], activity_type=r["activity_type"] or "unknown",
            name=r["name"] or "", date=r["date"], start_ts=r["start_ts"],
            duration_minutes=r["duration_minutes"], distance_miles=r["distance_miles"],
            avg_mph=r["avg_mph"], elevation_gain_ft=r["elevation_gain_ft"],
            calories=r["calories"], active_zone_minutes=r["active_zone_minutes"],
            load_score=r["load_score"],
        )
        for r in rows
    ]


def upsert_daily_metrics(points: List[Dict]) -> int:
    if not points:
        return 0

    now = int(time.time())
    rows = [
        (
            p["date"], p["metric"], p["value"], p.get("source"),
            json.dumps(p["extra"]) if p.get("extra") else None, now,
        )
        for p in points
    ]

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO daily_metrics (date, metric, value, source, extra, synced_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, metric) DO UPDATE SET
            value=excluded.value,
            source=excluded.source,
            extra=excluded.extra,
            synced_at=excluded.synced_at
    """, rows)
    conn.commit()
    conn.close()

    return len(rows)


def get_daily_metrics(
    metric: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    clauses = ["metric = ?"]
    params = [metric]

    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM daily_metrics WHERE {' AND '.join(clauses)} ORDER BY date",
        params,
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "date": r["date"],
            "value": r["value"],
            "source": r["source"],
            "extra": json.loads(r["extra"]) if r["extra"] else None,
        }
        for r in rows
    ]


def upsert_personal_best(
    category: str,
    name: str,
    value: Optional[float] = None,
    display_value: Optional[str] = None,
    unit: Optional[str] = None,
    date_achieved: Optional[str] = None,
    source: Optional[str] = None,
    only_if_missing: bool = False,
) -> None:
    conn = get_connection()
    cur = conn.cursor()

    if only_if_missing:
        cur.execute("""
            INSERT INTO personal_bests
                (category, name, value, display_value, unit, date_achieved, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, name) DO NOTHING
        """, (category, name, value, display_value, unit, date_achieved, source, int(time.time())))
    else:
        cur.execute("""
            INSERT INTO personal_bests
                (category, name, value, display_value, unit, date_achieved, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, name) DO UPDATE SET
                value=excluded.value,
                display_value=excluded.display_value,
                unit=excluded.unit,
                date_achieved=excluded.date_achieved,
                source=excluded.source,
                updated_at=excluded.updated_at
        """, (category, name, value, display_value, unit, date_achieved, source, int(time.time())))

    conn.commit()
    conn.close()


def get_personal_bests(category: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cur = conn.cursor()

    if category:
        cur.execute(
            "SELECT * FROM personal_bests WHERE LOWER(category) = ? ORDER BY id",
            (category.lower(),),
        )
    else:
        cur.execute("SELECT * FROM personal_bests ORDER BY id")

    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def delete_personal_best(category: str, name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM personal_bests WHERE LOWER(category) = ? AND name = ?",
        (category.lower(), name),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_personal_best(category: str, name: str) -> Optional[Dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM personal_bests WHERE LOWER(category) = ? AND name = ?",
        (category.lower(), name),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# Weekly Active Zone Minutes goal. Fitbit ships 150, which is the WHO floor for
# moderate activity; 300 is the top of the WHO range and a truer target for
# someone already training most days.
DEFAULT_SETTINGS = {
    "weekly_azm_goal": 300,
    "weekly_cardio_minutes_goal": 150,
    # Empty means "fall back to the .env value"; setting either here overrides it
    # at request time, so switching models needs no restart.
    "assistant_model": "",
    "assistant_base_url": "",
}


def get_settings() -> Dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    stored = {r["key"]: json.loads(r["value"]) for r in cur.fetchall()}
    conn.close()
    return {**DEFAULT_SETTINGS, **stored}


def set_settings(values: Dict) -> Dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, [(k, json.dumps(v)) for k, v in values.items()])
    conn.commit()
    conn.close()
    return get_settings()


CONVERSATION_TITLE_LENGTH = 60


def create_conversation(title: Optional[str] = None) -> str:
    conversation_id = uuid.uuid4().hex
    now = int(time.time())

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conversation_id, title, now, now),
    )
    conn.commit()
    conn.close()

    return conversation_id


def conversation_exists(conversation_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,))
    found = cur.fetchone() is not None
    conn.close()
    return found


def add_message(conversation_id: str, role: str, content: str, tools: Optional[List] = None) -> None:
    now = int(time.time())

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversation_messages (conversation_id, role, content, tools, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (conversation_id, role, content, json.dumps(tools) if tools else None, now),
    )

    # The first user message names the conversation.
    cur.execute(
        "UPDATE conversations SET updated_at = ?, "
        "title = COALESCE(title, ?) WHERE id = ?",
        (now, content[:CONVERSATION_TITLE_LENGTH] if role == "user" else None, conversation_id),
    )
    conn.commit()
    conn.close()


def get_messages(conversation_id: str, limit: Optional[int] = None) -> List[Dict]:
    conn = get_connection()
    cur = conn.cursor()

    if limit:
        cur.execute(
            "SELECT * FROM (SELECT * FROM conversation_messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id",
            (conversation_id, limit),
        )
    else:
        cur.execute(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        )

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "role": r["role"],
            "content": r["content"],
            "tools": json.loads(r["tools"]) if r["tools"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_conversations(limit: int = 30) -> List[Dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.title, c.created_at, c.updated_at,
               COUNT(m.id) AS message_count
        FROM conversations c
        LEFT JOIN conversation_messages m ON m.conversation_id = c.id
        GROUP BY c.id
        HAVING message_count > 0
        ORDER BY c.updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_conversation(conversation_id: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
    cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def set_sync_state(source: str, status: str, count: int = 0, detail: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sync_state (source, last_synced_at, status, detail, count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            last_synced_at=excluded.last_synced_at,
            status=excluded.status,
            detail=excluded.detail,
            count=excluded.count
    """, (source, int(time.time()), status, detail, count))
    conn.commit()
    conn.close()


def get_sync_state() -> Dict[str, Dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sync_state")
    rows = cur.fetchall()
    conn.close()

    return {
        r["source"]: {
            "last_synced_at": r["last_synced_at"],
            "status": r["status"],
            "detail": r["detail"],
            "count": r["count"],
        }
        for r in rows
    }
