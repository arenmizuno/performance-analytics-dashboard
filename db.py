import sqlite3

DB_PATH = "app.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS strava_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id TEXT UNIQUE,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            scope TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_strava_token(athlete_id, access_token, refresh_token, expires_at, scope):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO strava_tokens (athlete_id, access_token, refresh_token, expires_at, scope)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(athlete_id) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            expires_at=excluded.expires_at,
            scope=excluded.scope
    """, (athlete_id, access_token, refresh_token, expires_at, scope))

    conn.commit()
    conn.close()


def get_any_strava_token():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM strava_tokens ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row