from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.send_latest_weekly_geo_report import build_latest_weekly_geo_report


def _summary(run_date: str, score: float = 0.25) -> dict:
    return {
        "run_date": run_date,
        "prompts_checked": 15,
        "brand_visibility_score": score,
        "citation_rate": score,
        "share_of_voice": 0.2,
        "sentiment_score": 0.8,
        "branded_prompt_visibility_score": 1.0,
        "non_branded_prompt_visibility_score": 0.1,
        "tier_breakdown": {},
        "cluster_breakdown": {},
        "gaps": [],
        "competitor_leading": [],
        "source_attribution": [],
        "alerts": [],
        "incomplete": False,
        "failure_count": 0,
    }


def test_build_latest_weekly_geo_report_uses_latest_completed_run(tmp_path: Path) -> None:
    db_path = tmp_path / "citation_monitor.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE monitor_runs (id INTEGER PRIMARY KEY, run_date TEXT, run_ts TEXT, prompt_count INTEGER, citation_count INTEGER, alert_fired INTEGER, summary_json TEXT, completed INTEGER, resumed_from INTEGER)"
    )
    conn.execute(
        "INSERT INTO monitor_runs VALUES (1, '2026-05-18', '', 15, 3, 0, ?, 1, NULL)",
        (json.dumps(_summary("2026-05-18", 0.2)),),
    )
    conn.execute(
        "INSERT INTO monitor_runs VALUES (2, '2026-05-19', '', 15, 4, 0, ?, 1, NULL)",
        (json.dumps(_summary("2026-05-19", 0.3)),),
    )
    conn.execute(
        "INSERT INTO monitor_runs VALUES (3, '2026-05-20', '', 0, 0, 0, '', 0, NULL)"
    )
    conn.commit()
    conn.close()

    report = build_latest_weekly_geo_report(db_path)

    assert report.run_id == 2
    assert report.run_date == "2026-05-19"
    assert report.summary_count == 2
    assert report.subject == "[Folloze GEO] Weekly Visibility Monitor — 2026-05-13 to 2026-05-19"
    assert "Weekly Visibility Monitor" in report.body_html


def test_build_latest_weekly_geo_report_raises_without_completed_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "citation_monitor.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE monitor_runs (id INTEGER PRIMARY KEY, run_date TEXT, run_ts TEXT, prompt_count INTEGER, citation_count INTEGER, alert_fired INTEGER, summary_json TEXT, completed INTEGER, resumed_from INTEGER)"
    )
    conn.commit()
    conn.close()

    try:
        build_latest_weekly_geo_report(db_path)
    except RuntimeError as exc:
        assert "No completed citation monitor runs" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
