from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from html import escape

from citation_monitor.storage import (
    get_competitor_sightings_summary,
    get_run_citation_stats,
)
from config import Config
from notify import send_canary_report


@dataclass(slots=True)
class MonitorRunSummary:
    run_date: str
    prompts_checked: int
    overall_citation_rate: float
    branded_rate: float
    unbranded_rate: float
    tier_breakdown: dict[str, float]
    cluster_breakdown: dict[str, float]
    gaps: list[str]
    competitor_leading: list[dict]
    alerts: list[str]
    incomplete: bool = False
    failure_count: int = 0


def build_summary(
    conn: sqlite3.Connection,
    run_id: int,
    run_date: str,
    prompts: list[dict],
    failure_count: int,
) -> MonitorRunSummary:
    stats = get_run_citation_stats(conn, run_id)
    prompt_rates = {prompt["prompt_id"]: 0.0 for prompt in prompts}

    rows = conn.execute(
        "SELECT prompt_id, AVG(citation_probability) "
        "FROM citation_results WHERE run_id = ? GROUP BY prompt_id",
        (run_id,),
    ).fetchall()
    for prompt_id, rate in rows:
        prompt_rates[prompt_id] = float(rate or 0.0)

    tier_breakdown = _group_rates(prompts, prompt_rates, "tier")
    cluster_breakdown = _group_rates(prompts, prompt_rates, "cluster")
    gaps = sorted(prompt_id for prompt_id, rate in prompt_rates.items() if rate == 0.0)
    competitor_leading = get_competitor_sightings_summary(conn, run_id)
    alerts = _build_alerts(prompt_rates, competitor_leading, 1.0 - stats["branded_rate"])

    return MonitorRunSummary(
        run_date=run_date,
        prompts_checked=len(prompts),
        overall_citation_rate=stats["overall_citation_rate"],
        branded_rate=stats["branded_rate"],
        unbranded_rate=1.0 - stats["branded_rate"],
        tier_breakdown=tier_breakdown,
        cluster_breakdown=cluster_breakdown,
        gaps=gaps,
        competitor_leading=competitor_leading,
        alerts=alerts,
        incomplete=failure_count > 0,
        failure_count=failure_count,
    )


def fire_alerts(summary: MonitorRunSummary, config: Config) -> bool:
    if not summary.alerts:
        return False

    subject = f"[Folloze GEO] Citation Monitor Alerts — {summary.run_date}"
    alerts_html = "".join(f"<li>{escape(alert)}</li>" for alert in summary.alerts)
    gaps_html = (
        "".join(f"<li>{escape(prompt_id)}</li>" for prompt_id in summary.gaps) or "<li>None</li>"
    )
    competitor_html = (
        "".join(
            "<li>"
            f"{escape(entry['competitor'])} on {escape(entry['prompt_id'])}: {entry['count']}"
            "</li>"
            for entry in summary.competitor_leading[:10]
        )
        or "<li>None</li>"
    )
    body = f"""
    <h1>Citation Monitor Alerts</h1>
    <p>Run date: {escape(summary.run_date)}</p>
    <p>Prompts checked: {summary.prompts_checked}</p>
    <p>Overall citation rate: {summary.overall_citation_rate:.0%}</p>
    <p>Branded rate: {summary.branded_rate:.0%}</p>
    <p>Unbranded rate: {summary.unbranded_rate:.0%}</p>
    <p>Failure count: {summary.failure_count}</p>
    <h2>Alerts</h2>
    <ul>{alerts_html}</ul>
    <h2>Gap Prompts</h2>
    <ul>{gaps_html}</ul>
    <h2>Competitor Sightings</h2>
    <ul>{competitor_html}</ul>
    """
    send_canary_report(subject, body, config)
    return True


def _group_rates(
    prompts: list[dict],
    prompt_rates: dict[str, float],
    field: str,
) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for prompt in prompts:
        key = str(prompt.get(field, "unknown"))
        grouped.setdefault(key, []).append(prompt_rates.get(prompt["prompt_id"], 0.0))
    return {key: (sum(values) / len(values) if values else 0.0) for key, values in grouped.items()}


def _build_alerts(
    prompt_rates: dict[str, float],
    competitor_leading: list[dict],
    unbranded_rate: float,
) -> list[str]:
    alerts: list[str] = []
    for prompt_id, rate in sorted(prompt_rates.items()):
        if rate < 0.1:
            alerts.append(f"LOW CITATION: {prompt_id}")

    seen_competitors: set[str] = set()
    for entry in competitor_leading:
        competitor = entry["competitor"]
        if entry["count"] > 5 and competitor not in seen_competitors:
            alerts.append(f"COMPETITOR LEADING: {competitor}")
            seen_competitors.add(competitor)

    if unbranded_rate < 0.6:
        alerts.append("RATIO WARNING")

    return alerts
