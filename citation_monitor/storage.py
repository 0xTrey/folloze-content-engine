from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger("content_engine.citation_monitor")

SCHEMA_VERSION = 1
PARSER_VERSION = "regex-v1"

DB_PATH = Path("data/citation_monitor.db")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    run_ts TEXT NOT NULL,
    prompt_count INTEGER NOT NULL DEFAULT 0,
    citation_count INTEGER NOT NULL DEFAULT 0,
    alert_fired INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    resumed_from INTEGER REFERENCES monitor_runs(id)
);

CREATE TABLE IF NOT EXISTS prompt_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL,
    variant_text TEXT NOT NULL,
    generation_method TEXT NOT NULL DEFAULT 'template',
    created_date TEXT NOT NULL,
    UNIQUE(prompt_id, variant_text)
);

CREATE TABLE IF NOT EXISTS citation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES monitor_runs(id),
    prompt_id TEXT NOT NULL,
    variant_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    response_text TEXT,
    folloze_mentioned INTEGER NOT NULL DEFAULT 0,
    folloze_cited INTEGER NOT NULL DEFAULT 0,
    folloze_citation_position INTEGER,
    branded INTEGER NOT NULL DEFAULT 0,
    competitors_mentioned TEXT DEFAULT '[]',
    confidence_flag TEXT DEFAULT 'normal',
    citation_probability REAL DEFAULT 0.0,
    parser_version TEXT NOT NULL DEFAULT 'regex-v1',
    detection_method TEXT NOT NULL DEFAULT 'regex',
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competitor_sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES monitor_runs(id),
    prompt_id TEXT NOT NULL,
    competitor TEXT NOT NULL,
    sighting_count INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT NOT NULL,
    UNIQUE(run_id, prompt_id, competitor)
);

CREATE INDEX IF NOT EXISTS idx_citation_results_run
    ON citation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_citation_results_prompt
    ON citation_results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_competitor_sightings_run
    ON competitor_sightings(run_id);
"""


@dataclass(slots=True)
class CitationRow:
    run_id: int
    prompt_id: str
    variant_text: str
    provider: str
    response_text: str
    folloze_mentioned: bool
    folloze_cited: bool
    folloze_citation_position: int | None
    branded: bool
    competitors_mentioned: list[str]
    confidence_flag: str
    citation_probability: float
    parser_version: str
    detection_method: str
    checked_at: str


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    # Set schema version if not present
    row = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
    if row[0] == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    return conn


def create_run(
    conn: sqlite3.Connection,
    run_date: str,
    resumed_from: int | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO monitor_runs (run_date, run_ts, resumed_from) VALUES (?, ?, ?)",
        (run_date, datetime.now().isoformat(), resumed_from),
    )
    conn.commit()
    return cursor.lastrowid


def complete_run(
    conn: sqlite3.Connection,
    run_id: int,
    prompt_count: int,
    citation_count: int,
    alert_fired: bool,
    summary_json: str,
) -> None:
    conn.execute(
        "UPDATE monitor_runs SET prompt_count=?, citation_count=?, "
        "alert_fired=?, summary_json=?, completed=1 WHERE id=?",
        (prompt_count, citation_count, int(alert_fired), summary_json, run_id),
    )
    conn.commit()


def insert_citation(conn: sqlite3.Connection, row: CitationRow) -> None:
    conn.execute(
        "INSERT INTO citation_results "
        "(run_id, prompt_id, variant_text, provider, response_text, "
        "folloze_mentioned, folloze_cited, folloze_citation_position, "
        "branded, competitors_mentioned, confidence_flag, "
        "citation_probability, parser_version, detection_method, checked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            row.run_id,
            row.prompt_id,
            row.variant_text,
            row.provider,
            row.response_text,
            int(row.folloze_mentioned),
            int(row.folloze_cited),
            row.folloze_citation_position,
            int(row.branded),
            json.dumps(row.competitors_mentioned),
            row.confidence_flag,
            row.citation_probability,
            row.parser_version,
            row.detection_method,
            row.checked_at,
        ),
    )
    conn.commit()


def upsert_competitor_sighting(
    conn: sqlite3.Connection,
    run_id: int,
    prompt_id: str,
    competitor: str,
    sighting_count: int,
    checked_at: str,
) -> None:
    conn.execute(
        "INSERT INTO competitor_sightings "
        "(run_id, prompt_id, competitor, sighting_count, checked_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, prompt_id, competitor) "
        "DO UPDATE SET sighting_count=sighting_count + excluded.sighting_count",
        (run_id, prompt_id, competitor, sighting_count, checked_at),
    )
    conn.commit()


def upsert_variant(
    conn: sqlite3.Connection,
    prompt_id: str,
    variant_text: str,
    generation_method: str = "template",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO prompt_variants "
        "(prompt_id, variant_text, generation_method, created_date) "
        "VALUES (?, ?, ?, ?)",
        (prompt_id, variant_text, generation_method, datetime.now().isoformat()),
    )
    conn.commit()


def get_cached_variants(
    conn: sqlite3.Connection,
    prompt_id: str,
    max_age_days: int = 7,
) -> list[str]:
    rows = conn.execute(
        "SELECT variant_text FROM prompt_variants "
        "WHERE prompt_id = ? "
        "AND julianday('now') - julianday(created_date) <= ?",
        (prompt_id, max_age_days),
    ).fetchall()
    return [row[0] for row in rows]


def get_checked_variants_for_run(
    conn: sqlite3.Connection,
    run_id: int,
    prompt_id: str,
    provider: str,
) -> set[str]:
    rows = conn.execute(
        "SELECT variant_text FROM citation_results "
        "WHERE run_id = ? AND prompt_id = ? AND provider = ?",
        (run_id, prompt_id, provider),
    ).fetchall()
    return {row[0] for row in rows}


def get_latest_incomplete_run(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM monitor_runs WHERE completed = 0 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def get_citation_rates(
    conn: sqlite3.Connection,
    days: int = 7,
) -> dict[str, float]:
    rows = conn.execute(
        "SELECT prompt_id, "
        "AVG(folloze_mentioned) as citation_rate "
        "FROM citation_results "
        "WHERE julianday('now') - julianday(checked_at) <= ? "
        "GROUP BY prompt_id",
        (days,),
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def get_competitor_sightings_summary(
    conn: sqlite3.Connection,
    run_id: int,
) -> list[dict]:
    rows = conn.execute(
        "SELECT prompt_id, competitor, SUM(sighting_count) as total "
        "FROM competitor_sightings WHERE run_id = ? "
        "GROUP BY prompt_id, competitor "
        "ORDER BY total DESC",
        (run_id,),
    ).fetchall()
    return [{"prompt_id": r[0], "competitor": r[1], "count": r[2]} for r in rows]


def get_run_citation_stats(
    conn: sqlite3.Connection,
    run_id: int,
) -> dict:
    row = conn.execute(
        "SELECT "
        "COUNT(*) as total, "
        "SUM(folloze_mentioned) as mentioned, "
        "SUM(branded) as branded_count "
        "FROM citation_results WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    total = row[0] or 1
    return {
        "total": row[0],
        "mentioned": row[1] or 0,
        "branded_count": row[2] or 0,
        "overall_citation_rate": (row[1] or 0) / total,
        "branded_rate": (row[2] or 0) / max(row[1] or 0, 1),
    }
