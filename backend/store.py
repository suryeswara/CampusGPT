import sqlite3
from datetime import datetime, timezone

from backend import config


def _conn():
    return sqlite3.connect(config.SQLITE_PATH)


def init() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS feedback (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts TEXT, question TEXT, answer TEXT, rating INTEGER, mode TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS query_log (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts TEXT, question TEXT, rewritten TEXT, mode TEXT,
                   n_hits INTEGER, latency_ms INTEGER)"""
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_feedback(question, answer, rating, mode) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback (ts, question, answer, rating, mode) VALUES (?,?,?,?,?)",
            (_now(), question, answer, rating, mode),
        )


def log_query(question, rewritten, mode, n_hits, latency_ms) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO query_log (ts, question, rewritten, mode, n_hits, latency_ms)"
            " VALUES (?,?,?,?,?,?)",
            (_now(), question, rewritten, mode, n_hits, latency_ms),
        )
