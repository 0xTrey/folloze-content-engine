from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from citation_monitor.contracts import LEGACY_SEMANTICS_VERSION, NATIVE_SEMANTICS_VERSION

LOGGER = logging.getLogger("content_engine.citation_monitor")

SCHEMA_VERSION = 3
PARSER_VERSION = "provider-native-v2"

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
    sentiment_label TEXT NOT NULL DEFAULT 'neutral',
    source_urls TEXT NOT NULL DEFAULT '[]',
    citation_probability REAL DEFAULT 0.0,
    parser_version TEXT NOT NULL DEFAULT 'regex-v1',
    detection_method TEXT NOT NULL DEFAULT 'regex',
    checked_at TEXT NOT NULL,
    native_citations TEXT NOT NULL DEFAULT '[]',
    raw_evidence TEXT NOT NULL DEFAULT '{}',
    evidence_checksum TEXT,
    grounded_response INTEGER NOT NULL DEFAULT 0,
    metric_semantics_version TEXT NOT NULL DEFAULT 'legacy-mention-proxy-v1'
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
    sentiment_label: str
    source_urls: list[str]
    citation_probability: float
    parser_version: str
    detection_method: str
    checked_at: str
    native_citations: list[dict] = field(default_factory=list)
    raw_evidence: dict = field(default_factory=dict)
    evidence_checksum: str | None = None
    grounded_response: bool = False
    metric_semantics_version: str = NATIVE_SEMANTICS_VERSION


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    _migrate_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
    if row[0] == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    else:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(citation_results)").fetchall()}
    if "sentiment_label" not in columns:
        conn.execute(
            "ALTER TABLE citation_results ADD COLUMN sentiment_label TEXT NOT NULL DEFAULT 'neutral'"
        )
    if "source_urls" not in columns:
        conn.execute(
            "ALTER TABLE citation_results ADD COLUMN source_urls TEXT NOT NULL DEFAULT '[]'"
        )
    migrations = {
        "native_citations": "TEXT NOT NULL DEFAULT '[]'",
        "raw_evidence": "TEXT NOT NULL DEFAULT '{}'",
        "evidence_checksum": "TEXT",
        "grounded_response": "INTEGER NOT NULL DEFAULT 0",
        "metric_semantics_version": (
            f"TEXT NOT NULL DEFAULT '{LEGACY_SEMANTICS_VERSION}'"
        ),
    }
    for column_name, definition in migrations.items():
        if column_name not in columns:
            conn.execute(
                f"ALTER TABLE citation_results ADD COLUMN {column_name} {definition}"
            )


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
        "branded, competitors_mentioned, confidence_flag, sentiment_label, source_urls, "
        "citation_probability, parser_version, detection_method, checked_at, "
        "native_citations, raw_evidence, evidence_checksum, grounded_response, "
        "metric_semantics_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            row.sentiment_label,
            json.dumps(row.source_urls),
            row.citation_probability,
            row.parser_version,
            row.detection_method,
            row.checked_at,
            json.dumps(row.native_citations, sort_keys=True),
            json.dumps(row.raw_evidence, sort_keys=True),
            row.evidence_checksum,
            int(row.grounded_response),
            row.metric_semantics_version,
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
        "AVG(folloze_cited) as citation_rate "
        "FROM citation_results "
        "WHERE julianday('now') - julianday(checked_at) <= ? "
        "AND metric_semantics_version = ? AND grounded_response = 1 "
        "GROUP BY prompt_id",
        (days, NATIVE_SEMANTICS_VERSION),
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
        "SUM(CASE WHEN metric_semantics_version = ? AND grounded_response = 1 "
        "THEN folloze_cited ELSE 0 END) as cited, "
        "SUM(CASE WHEN branded = 1 THEN folloze_mentioned ELSE 0 END) as branded_mentions, "
        "SUM(CASE WHEN branded = 1 THEN 1 ELSE 0 END) as branded_checks, "
        "SUM(CASE WHEN branded = 0 THEN folloze_mentioned ELSE 0 END) as non_branded_mentions, "
        "SUM(CASE WHEN branded = 0 THEN 1 ELSE 0 END) as non_branded_checks, "
        "SUM(CASE WHEN folloze_mentioned = 1 AND sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive_mentions, "
        "SUM(CASE WHEN metric_semantics_version = ? THEN 1 ELSE 0 END) as native_checks, "
        "SUM(CASE WHEN metric_semantics_version = ? AND grounded_response = 1 THEN 1 ELSE 0 END) as grounded_checks, "
        "SUM(CASE WHEN metric_semantics_version != ? THEN 1 ELSE 0 END) as legacy_checks, "
        "SUM(CASE WHEN metric_semantics_version = ? AND branded = 0 AND grounded_response = 1 THEN 1 ELSE 0 END) as non_branded_grounded_checks, "
        "SUM(CASE WHEN metric_semantics_version = ? AND branded = 0 "
        "AND folloze_cited = 1 THEN 1 ELSE 0 END) as non_branded_citations, "
        "SUM(CASE WHEN metric_semantics_version = ? AND grounded_response = 1 "
        "AND folloze_cited = 1 AND source_urls != '[]' THEN 1 ELSE 0 END) "
        "as source_attributed_citations "
        "FROM citation_results WHERE run_id = ?",
        (
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            NATIVE_SEMANTICS_VERSION,
            run_id,
        ),
    ).fetchone()

    total = row[0] or 0
    brand_mentions = row[1] or 0
    brand_citations = row[2] or 0
    branded_mentions = row[3] or 0
    branded_checks = row[4] or 0
    non_branded_mentions = row[5] or 0
    non_branded_checks = row[6] or 0
    positive_mentions = row[7] or 0
    native_checks = row[8] or 0
    grounded_checks = row[9] or 0
    legacy_checks = row[10] or 0
    non_branded_grounded_checks = row[11] or 0
    non_branded_citations = row[12] or 0
    source_attributed_citations = row[13] or 0

    competitor_total = conn.execute(
        "SELECT COALESCE(SUM(sighting_count), 0) FROM competitor_sightings WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0]

    total_for_rate = total or 1
    share_denominator = brand_mentions + competitor_total

    return {
        "total": total,
        "total_checks": total,
        "mentioned": brand_mentions,
        "brand_mentions": brand_mentions,
        "brand_citations": brand_citations,
        "competitor_mentions": competitor_total,
        "brand_visibility_score": brand_mentions / total_for_rate,
        "citation_rate": brand_citations / max(grounded_checks, 1),
        "citation_numerator": brand_citations,
        "citation_denominator": grounded_checks,
        "grounded_checks": grounded_checks,
        "native_checks": native_checks,
        "legacy_checks": legacy_checks,
        "citation_semantics": NATIVE_SEMANTICS_VERSION,
        "source_attribution_rate": (
            source_attributed_citations / max(brand_citations, 1)
        ),
        "non_branded_citation_rate": (
            non_branded_citations / max(non_branded_grounded_checks, 1)
        ),
        "share_of_voice": brand_mentions / share_denominator if share_denominator else 0.0,
        "sentiment_score": positive_mentions / max(brand_mentions, 1),
        "branded_prompt_visibility_score": branded_mentions / max(branded_checks, 1),
        "non_branded_prompt_visibility_score": non_branded_mentions / max(non_branded_checks, 1),
        # Backward-compatible aliases.
        "overall_citation_rate": brand_citations / max(grounded_checks, 1),
        "branded_rate": branded_mentions / max(branded_checks, 1),
        "unbranded_rate": non_branded_mentions / max(non_branded_checks, 1),
    }


def get_run_source_attribution_summary(
    conn: sqlite3.Connection,
    run_id: int,
    limit: int = 10,
) -> list[dict]:
    rows = conn.execute(
        "SELECT source_urls FROM citation_results "
        "WHERE run_id = ? AND source_urls != '[]' AND metric_semantics_version = ?",
        (run_id, NATIVE_SEMANTICS_VERSION),
    ).fetchall()

    counts: dict[str, int] = {}
    for (raw_urls,) in rows:
        try:
            urls = json.loads(raw_urls or "[]")
        except json.JSONDecodeError:
            urls = []
        for url in urls:
            counts[url] = counts.get(url, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"url": url, "count": count} for url, count in ranked[:limit]]


def get_completed_run_summaries(
    conn: sqlite3.Connection,
    end_date: str,
    days: int = 7,
) -> list[dict]:
    end = date.fromisoformat(end_date)
    start = end - timedelta(days=days - 1)
    rows = conn.execute(
        "SELECT run_date, summary_json "
        "FROM monitor_runs "
        "WHERE completed = 1 AND run_date >= ? AND run_date <= ? "
        "ORDER BY run_date ASC, id ASC",
        (start.isoformat(), end.isoformat()),
    ).fetchall()

    summaries: list[dict] = []
    for run_date, summary_json in rows:
        if not summary_json:
            continue
        try:
            parsed = json.loads(summary_json)
        except json.JSONDecodeError:
            LOGGER.warning("Skipping malformed summary_json for run_date=%s", run_date)
            continue
        if isinstance(parsed, dict):
            parsed.setdefault("run_date", run_date)
            parsed.setdefault("citation_semantics", LEGACY_SEMANTICS_VERSION)
            summaries.append(parsed)
    return summaries
