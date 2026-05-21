#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from citation_monitor.report import MonitorRunSummary, _build_weekly_report  # noqa: E402
from citation_monitor.storage import get_completed_run_summaries  # noqa: E402
from config import Config  # noqa: E402
from notify import send_canary_report  # noqa: E402


@dataclass(slots=True)
class WeeklyGeoReport:
    run_id: int
    run_date: str
    summary_count: int
    subject: str
    body_html: str


def build_latest_weekly_geo_report(db_path: Path) -> WeeklyGeoReport:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT id, run_date, summary_json
            FROM monitor_runs
            WHERE completed = 1
              AND summary_json IS NOT NULL
              AND summary_json <> ''
            ORDER BY run_date DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No completed citation monitor runs with summaries found in {db_path}")

        run_id, run_date, summary_json = row
        summary = MonitorRunSummary(**json.loads(summary_json))
        weekly_summaries = get_completed_run_summaries(conn, run_date, days=7)
        subject, body_html = _build_weekly_report(summary, weekly_summaries)
        return WeeklyGeoReport(
            run_id=int(run_id),
            run_date=str(run_date),
            summary_count=len(weekly_summaries),
            subject=subject,
            body_html=body_html,
        )
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send the latest Folloze GEO weekly report")
    parser.add_argument(
        "--db-path",
        default=str(ROOT / "data" / "citation_monitor.db"),
        help="Path to citation_monitor.db",
    )
    parser.add_argument(
        "--to",
        help="Comma-separated recipient override. Defaults to configured weekly GEO recipients.",
    )
    parser.add_argument("--subject-suffix", help="Optional suffix appended to the subject")
    parser.add_argument("--html-out", help="Optional path to write rendered HTML")
    parser.add_argument("--dry-run", action="store_true", help="Render and print metadata without sending")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_latest_weekly_geo_report(Path(args.db_path))
    subject = report.subject
    if args.subject_suffix:
        subject = f"{subject} ({args.subject_suffix})"

    html_out = Path(args.html_out) if args.html_out else ROOT / "logs" / f"weekly-geo-report-latest-{report.run_date}.html"
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(report.body_html)

    metadata = {
        "subject": subject,
        "latest_completed_run_id": report.run_id,
        "latest_completed_run_date": report.run_date,
        "weekly_summary_count": report.summary_count,
        "html_out": str(html_out),
        "dry_run": args.dry_run,
    }
    if args.to:
        metadata["recipient_override"] = [entry.strip() for entry in args.to.split(",") if entry.strip()]

    print(json.dumps(metadata, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    if args.to:
        os.environ["NOTIFY_EMAIL_TO"] = args.to
    send_canary_report(subject, report.body_html, Config.load(ROOT / "config.yaml"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
