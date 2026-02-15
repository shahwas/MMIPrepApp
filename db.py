"""
SQLite database layer for MMI Prep App.
Tables: questions, attempts, srs, user_skill
"""

import sqlite3
import json
import uuid
import os
from datetime import date, datetime
from typing import Optional

# Support optional Postgres via DATABASE_URL (e.g., Supabase) while keeping
# SQLite fallback for local dev. When DATABASE_URL is set, psycopg is used
# and cursors return dict-like rows.
DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(__file__), "mmi_prep.db")


def get_conn():
    """Return a DB connection. For Postgres returns a psycopg connection,
    for SQLite returns a sqlite3.Connection."""
    if DATABASE_URL:
        import psycopg
        conn = psycopg.connect(DATABASE_URL, autocommit=False)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()

    if DATABASE_URL:
        # Postgres-compatible schema
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL UNIQUE,
                avatar TEXT NOT NULL DEFAULT '🧑‍⚕️',
                external_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                archetype TEXT NOT NULL,
                difficulty_base INTEGER NOT NULL DEFAULT 1,
                prompt_text TEXT NOT NULL,
                tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                source_pack TEXT NOT NULL DEFAULT 'seed',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                difficulty_used INTEGER NOT NULL DEFAULT 1,
                transcript_text TEXT,
                step_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                rubric_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS srs (
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                ease DOUBLE PRECISION NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 1,
                repetitions INTEGER NOT NULL DEFAULT 0,
                due_date DATE NOT NULL,
                PRIMARY KEY (user_id, question_id)
            );

            CREATE TABLE IF NOT EXISTS user_skill (
                user_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                ema_score DOUBLE PRECISION,
                n_attempts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, skill_name)
            );

            CREATE INDEX IF NOT EXISTS idx_srs_due ON srs(user_id, due_date);
            CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_questions_arch ON questions(archetype);
            """
        )
        conn.commit()
        cur.close()
        conn.close()
        return

    # SQLite schema (local dev)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL UNIQUE,
        avatar TEXT NOT NULL DEFAULT '🧑‍⚕️',
        external_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        archetype TEXT NOT NULL,
        difficulty_base INTEGER NOT NULL DEFAULT 1 CHECK(difficulty_base BETWEEN 1 AND 5),
        prompt_text TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]',
        source_pack TEXT NOT NULL DEFAULT 'seed',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'default',
        question_id TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('guided','timed')),
        difficulty_used INTEGER NOT NULL DEFAULT 1,
        transcript_text TEXT,
        step_json TEXT NOT NULL DEFAULT '{}',
        rubric_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS srs (
        user_id TEXT NOT NULL DEFAULT 'default',
        question_id TEXT NOT NULL,
        ease REAL NOT NULL DEFAULT 2.5,
        interval_days INTEGER NOT NULL DEFAULT 1,
        repetitions INTEGER NOT NULL DEFAULT 0,
        due_date TEXT NOT NULL,
        PRIMARY KEY (user_id, question_id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS user_skill (
        user_id TEXT NOT NULL DEFAULT 'default',
        skill_name TEXT NOT NULL,
        ema_score REAL NOT NULL DEFAULT 2.5,
        n_attempts INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, skill_name)
    );

    CREATE INDEX IF NOT EXISTS idx_srs_due ON srs(user_id, due_date);
    CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_questions_arch ON questions(archetype);
    """)
    conn.commit()
    conn.close()


# ─── Question CRUD ───────────────────────────────────────────────

def insert_question(archetype: str, difficulty_base: int, prompt_text: str,
                    tags: list[str], source_pack: str = "seed") -> str:
    qid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO questions (id, archetype, difficulty_base, prompt_text, tags, source_pack) VALUES (?,?,?,?,?,?)",
        (qid, archetype, difficulty_base, prompt_text, json.dumps(tags), source_pack),
    )
    conn.commit()
    conn.close()
    return qid


def get_all_questions() -> list[dict]:
    conn = get_conn()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("SELECT * FROM questions ORDER BY archetype, difficulty_base")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    rows = conn.execute("SELECT * FROM questions ORDER BY archetype, difficulty_base").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_questions_by_archetype(archetype: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM questions WHERE archetype=? ORDER BY difficulty_base", (archetype,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_question_by_id(qid: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_questions() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    conn.close()
    return n


def delete_question(qid: str):
    conn = get_conn()
    conn.execute("DELETE FROM srs WHERE question_id=?", (qid,))
    conn.execute("DELETE FROM attempts WHERE question_id=?", (qid,))
    conn.execute("DELETE FROM questions WHERE id=?", (qid,))
    conn.commit()
    conn.close()


# ─── Attempt CRUD ────────────────────────────────────────────────

def insert_attempt(user_id: str, question_id: str, mode: str,
                   difficulty_used: int, transcript_text: str,
                   step_json: dict, rubric_json: dict) -> str:
    aid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO attempts (id,user_id,question_id,mode,difficulty_used,transcript_text,step_json,rubric_json) VALUES (?,?,?,?,?,?,?,?)",
        (aid, user_id, question_id, mode, difficulty_used, transcript_text,
         json.dumps(step_json), json.dumps(rubric_json)),
    )
    conn.commit()
    conn.close()
    return aid


def get_user_attempts(user_id: str = "default", limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.*, q.prompt_text, q.archetype FROM attempts a
           JOIN questions q ON a.question_id = q.id
           WHERE a.user_id=? ORDER BY a.created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── SRS CRUD ────────────────────────────────────────────────────

def get_srs(user_id: str, question_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM srs WHERE user_id=? AND question_id=?", (user_id, question_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_srs(user_id: str, question_id: str, ease: float, interval_days: int,
               repetitions: int, due_date: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO srs (user_id, question_id, ease, interval_days, repetitions, due_date)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, question_id) DO UPDATE SET
             ease=excluded.ease, interval_days=excluded.interval_days,
             repetitions=excluded.repetitions, due_date=excluded.due_date""",
        (user_id, question_id, ease, interval_days, repetitions, due_date),
    )
    conn.commit()
    conn.close()


def get_due_cards(user_id: str = "default", limit: int = 20) -> list[dict]:
    today = date.today().isoformat()
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.*, q.prompt_text, q.archetype, q.difficulty_base, q.tags
           FROM srs s JOIN questions q ON s.question_id = q.id
           WHERE s.user_id=? AND s.due_date <= ?
           ORDER BY s.due_date ASC LIMIT ?""",
        (user_id, today, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_new_cards(user_id: str = "default", limit: int = 10) -> list[dict]:
    """Questions that have no SRS entry yet."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT q.* FROM questions q
           WHERE q.id NOT IN (SELECT question_id FROM srs WHERE user_id=?)
           ORDER BY RANDOM() LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── User Skill CRUD ─────────────────────────────────────────────

SKILL_NAMES = ["structure", "empathy", "perspective", "reasoning", "actionability", "clarity"]


def get_user_skills(user_id: str = "default") -> dict[str, dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM user_skill WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    skills = {s: {"ema_score": None, "n_attempts": 0} for s in SKILL_NAMES}
    for r in rows:
        skills[r["skill_name"]] = {"ema_score": r["ema_score"], "n_attempts": r["n_attempts"]}
    return skills


def update_user_skill(user_id: str, skill_name: str, new_score: float, alpha: float = 0.3):
    """EMA update: new_ema = alpha * new_score + (1 - alpha) * old_ema"""
    current = get_user_skills(user_id)
    old = current.get(skill_name, {"ema_score": None, "n_attempts": 0})
    old_ema = old["ema_score"] if old["ema_score"] is not None else 2.5
    ema = alpha * new_score + (1 - alpha) * old_ema
    n = old["n_attempts"] + 1
    conn = get_conn()
    conn.execute(
        """INSERT INTO user_skill (user_id, skill_name, ema_score, n_attempts)
           VALUES (?,?,?,?)
           ON CONFLICT(user_id, skill_name) DO UPDATE SET
             ema_score=excluded.ema_score, n_attempts=excluded.n_attempts""",
        (user_id, skill_name, round(ema, 3), n),
    )
    conn.commit()
    conn.close()


def get_weakest_skill(user_id: str = "default") -> str:
    skills = get_user_skills(user_id)
    # Treat None (unassessed) as -1 so it sorts lowest
    return min(skills, key=lambda k: skills[k]["ema_score"] if skills[k]["ema_score"] is not None else -1)


# ─── User CRUD ───────────────────────────────────────────────────

def create_user(display_name: str, avatar: str = "🧑‍⚕️") -> str:
    """Create a new local user (used for mapping OIDC identities to app users)."""
    uid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (id, display_name, avatar) VALUES (?,?,?)",
        (uid, display_name.strip(), avatar),
    )
    conn.commit()
    conn.close()
    return uid


def get_all_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY display_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(uid: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_session_token(token: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE session_token=?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_session_token(uid: str, token: str | None):
    conn = get_conn()
    conn.execute("UPDATE users SET session_token=? WHERE id=?", (token, uid))
    conn.commit()
    conn.close()


def verify_password_for_user(display_name: str, password: str) -> Optional[dict]:
    """Verify password for a user by display_name. Returns user row dict if ok."""
    import bcrypt

    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE lower(display_name)=lower(?)", (display_name,)).fetchone()
    conn.close()
    if not row:
        return None
    if not row["password_hash"]:
        return None
    try:
        ok = bcrypt.checkpw(password.encode('utf-8'), row["password_hash"].encode('utf-8'))
    except Exception:
        ok = False
    return dict(row) if ok else None


def get_user_by_external_id(external_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE external_id=?", (external_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_user_from_oidc(external_id: str, display_name: str, avatar: str = "🩺") -> dict:
    """Map an OIDC external_id to a local user row; create if missing."""
    if not external_id:
        raise ValueError("external_id required")
    user = get_user_by_external_id(external_id)
    if user:
        return user
    # create one
    uid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (id, display_name, avatar, external_id) VALUES (?,?,?,?)",
        (uid, display_name.strip(), avatar, external_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row)


def delete_user(uid: str):
    conn = get_conn()
    conn.execute("DELETE FROM user_skill WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM srs WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM attempts WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()


# ─── Init on import ──────────────────────────────────────────────
init_db()
