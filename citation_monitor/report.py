from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from html import escape

from citation_monitor.storage import (
    get_completed_run_summaries,
    get_competitor_sightings_summary,
    get_run_citation_stats,
    get_run_source_attribution_summary,
)
from config import Config


@dataclass(slots=True)
class MonitorRunSummary:
    run_date: str
    prompts_checked: int
    brand_visibility_score: float
    citation_rate: float
    share_of_voice: float
    sentiment_score: float
    branded_prompt_visibility_score: float
    non_branded_prompt_visibility_score: float
    tier_breakdown: dict[str, float]
    cluster_breakdown: dict[str, float]
    gaps: list[str]
    competitor_leading: list[dict]
    source_attribution: list[dict]
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
    source_attribution = get_run_source_attribution_summary(conn, run_id)
    alerts = _build_alerts(prompt_rates, competitor_leading, stats)

    return MonitorRunSummary(
        run_date=run_date,
        prompts_checked=len(prompts),
        brand_visibility_score=stats["brand_visibility_score"],
        citation_rate=stats["citation_rate"],
        share_of_voice=stats["share_of_voice"],
        sentiment_score=stats["sentiment_score"],
        branded_prompt_visibility_score=stats["branded_prompt_visibility_score"],
        non_branded_prompt_visibility_score=stats["non_branded_prompt_visibility_score"],
        tier_breakdown=tier_breakdown,
        cluster_breakdown=cluster_breakdown,
        gaps=gaps,
        competitor_leading=competitor_leading,
        source_attribution=source_attribution,
        alerts=alerts,
        incomplete=failure_count > 0,
        failure_count=failure_count,
    )


def fire_alerts(
    summary: MonitorRunSummary,
    config: Config,
    conn: sqlite3.Connection | None = None,
) -> bool:
    if not _is_weekly_summary_day(summary.run_date):
        return False

    weekly_summaries = (
        get_completed_run_summaries(conn, summary.run_date, days=7) if conn is not None else []
    )
    if not weekly_summaries:
        weekly_summaries = [asdict(summary)]

    from notify import send_canary_report

    subject, body = _build_weekly_report(summary, weekly_summaries)
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


def _is_weekly_summary_day(run_date: str) -> bool:
    return date.fromisoformat(run_date).weekday() == 0


def _build_weekly_report(
    latest_summary: MonitorRunSummary,
    weekly_summaries: list[dict],
) -> tuple[str, str]:
    end = date.fromisoformat(latest_summary.run_date)
    start = end - timedelta(days=6)
    subject = f"[Folloze GEO] Weekly Visibility Monitor — {start.isoformat()} to {end.isoformat()}"

    avg_brand_visibility = _average_metric(weekly_summaries, "brand_visibility_score")
    avg_citation_rate = _average_metric(weekly_summaries, "citation_rate")
    avg_share_of_voice = _average_metric(weekly_summaries, "share_of_voice")
    avg_non_branded_visibility = _average_metric(
        weekly_summaries,
        "non_branded_prompt_visibility_score",
    )
    alert_counts = Counter(
        alert
        for weekly_summary in weekly_summaries
        for alert in weekly_summary.get("alerts", [])
    )

    summary_rows = [
        ("Coverage window", f"{start.isoformat()} to {end.isoformat()}"),
        ("Latest run date", latest_summary.run_date),
        ("Runs captured", str(len(weekly_summaries))),
        ("Average Brand Visibility Score", f"{avg_brand_visibility:.0%}"),
        ("Average Citation Rate", f"{avg_citation_rate:.0%}"),
        ("Average Share of Voice", f"{avg_share_of_voice:.0%}"),
        (
            "Average Non-branded Prompt Visibility",
            f"{avg_non_branded_visibility:.0%}",
        ),
    ]
    latest_rows = [
        ("Prompts checked", str(latest_summary.prompts_checked)),
        ("Brand Visibility Score", f"{latest_summary.brand_visibility_score:.0%}"),
        ("Citation Rate", f"{latest_summary.citation_rate:.0%}"),
        ("Share of Voice", f"{latest_summary.share_of_voice:.0%}"),
        ("Sentiment Score", f"{latest_summary.sentiment_score:.0%}"),
        (
            "Branded Prompt Visibility",
            f"{latest_summary.branded_prompt_visibility_score:.0%}",
        ),
        (
            "Non-branded Prompt Visibility",
            f"{latest_summary.non_branded_prompt_visibility_score:.0%}",
        ),
        ("Failure count", str(latest_summary.failure_count)),
    ]
    daily_rows = [
        (
            str(summary.get("run_date", "")),
            _render_metric_cell(
                "Brand Visibility Score",
                float(summary.get("brand_visibility_score", 0.0) or 0.0),
                _metric_tone(float(summary.get("brand_visibility_score", 0.0) or 0.0)),
            ),
            _render_metric_cell(
                "Citation Rate",
                float(summary.get("citation_rate", 0.0) or 0.0),
                _metric_tone(float(summary.get("citation_rate", 0.0) or 0.0)),
            ),
            _render_metric_cell(
                "Share of Voice",
                float(summary.get("share_of_voice", 0.0) or 0.0),
                _metric_tone(float(summary.get("share_of_voice", 0.0) or 0.0)),
            ),
            _render_metric_cell(
                "Non-branded Prompt Visibility",
                float(summary.get("non_branded_prompt_visibility_score", 0.0) or 0.0),
                _metric_tone(float(summary.get("non_branded_prompt_visibility_score", 0.0) or 0.0)),
            ),
            _render_alert_badges(summary.get("alerts", [])[:3]),
        )
        for summary in weekly_summaries
    ]
    alert_rows = [
        (alert, f"{count} run{'s' if count != 1 else ''}")
        for alert, count in sorted(alert_counts.items())
    ] or [("None", "0 runs")]
    gap_rows = [(prompt_id, "Open gap") for prompt_id in latest_summary.gaps] or [("None", "-")]
    competitor_rows = [
        (f"{entry['competitor']} on {entry['prompt_id']}", str(entry['count']))
        for entry in latest_summary.competitor_leading[:10]
    ] or [("None", "0")]
    source_rows = [
        (entry["url"], str(entry["count"]))
        for entry in latest_summary.source_attribution[:10]
    ] or [("None", "0")]

    hero_summary = "7-day rollup"
    body = f"""
    <div style="margin:0; padding:24px 0; background-color:#f3f6fb;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:collapse;">
        <tr>
          <td align="center">
            <table role="presentation" width="760" cellpadding="0" cellspacing="0" border="0" style="width:760px; max-width:760px; border-collapse:collapse; background-color:#ffffff; border:1px solid #dbe4f0; border-radius:18px; overflow:hidden;">
              <tr>
                <td style="padding:32px 36px; background:linear-gradient(135deg, #102a43 0%, #1f4b99 60%, #3b82f6 100%); color:#ffffff;">
                  <div style="font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; letter-spacing:1.2px; text-transform:uppercase; opacity:0.84;">Folloze GEO</div>
                  <div style="font-family:Arial, Helvetica, sans-serif; font-size:30px; line-height:38px; font-weight:700; margin-top:8px;">Weekly Visibility Monitor</div>
                  <div style="font-family:Arial, Helvetica, sans-serif; font-size:15px; line-height:24px; margin-top:10px; color:#dbeafe;">{escape(hero_summary)} · {escape(start.isoformat())} to {escape(end.isoformat())}</div>
                </td>
              </tr>
              <tr>
                <td style="padding:28px 36px 10px 36px; font-family:Arial, Helvetica, sans-serif; color:#102a43;">
                  <div style="font-size:18px; font-weight:700; line-height:26px; margin-bottom:16px;">Summary Metrics</div>
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; border-collapse:separate; border-spacing:12px;">
                    <tr>
                      <td width="50%" valign="top">{_render_metric_card('Average Brand Visibility Score', avg_brand_visibility, 'brand')}</td>
                      <td width="50%" valign="top">{_render_metric_card('Average Citation Rate', avg_citation_rate, 'citation')}</td>
                    </tr>
                    <tr>
                      <td width="50%" valign="top">{_render_metric_card('Average Share of Voice', avg_share_of_voice, 'sov')}</td>
                      <td width="50%" valign="top">{_render_metric_card('Average Non-branded Prompt Visibility', avg_non_branded_visibility, 'gap')}</td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 36px 0 36px; font-family:Arial, Helvetica, sans-serif; color:#102a43;">
                  {_render_section_card('Executive Summary', _render_kv_table(summary_rows, headers=('Metric', 'Value'), compact=True))}
                  {_render_section_card('Latest Daily Snapshot', _render_kv_table(latest_rows, headers=('Metric', 'Value'), compact=True))}
                  {_render_section_card(
                      'Daily Snapshots',
                      _render_data_table(
                          headers=(
                              'Run date',
                              'Brand Visibility Score',
                              'Citation Rate',
                              'Share of Voice',
                              'Non-branded Prompt Visibility',
                              'Top alerts',
                          ),
                          rows=daily_rows,
                          escape_cells=(True, False, False, False, False, False),
                      ),
                  )}
                  {_render_section_card('Weekly Alert Frequency', _render_kv_table(alert_rows, headers=('Alert', 'Frequency'), compact=True))}
                  {_render_section_card('Latest Gap Prompts', _render_kv_table(gap_rows, headers=('Prompt', 'Status'), compact=True))}
                  {_render_section_card('Latest Competitor Sightings', _render_kv_table(competitor_rows, headers=('Competitor / Prompt', 'Count'), compact=True))}
                  {_render_section_card('Latest Source Attribution', _render_kv_table(source_rows, headers=('Source URL', 'Count'), compact=True))}
                </td>
              </tr>
              <tr>
                <td style="padding:4px 36px 32px 36px; font-family:Arial, Helvetica, sans-serif; color:#6b7c93; font-size:12px; line-height:18px;">
                  Generated for email-safe rendering with inline HTML and table-based layout for consistent inbox display.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
    """
    return subject, body


def _average_metric(summaries: list[dict], key: str) -> float:
    values = [float(summary.get(key, 0.0) or 0.0) for summary in summaries]
    return sum(values) / len(values) if values else 0.0


def _format_percent(value: object) -> str:
    try:
        return f"{float(value or 0.0):.0%}"
    except (TypeError, ValueError):
        return "0%"


def _render_kv_table(
    rows: list[tuple[str, str]],
    headers: tuple[str, str] = ("Metric", "Value"),
    compact: bool = False,
) -> str:
    row_style = (
        "padding:10px 12px; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:20px; "
        "border-bottom:1px solid #e6edf5; color:#102a43; vertical-align:top;"
    )
    if compact:
        row_style = (
            "padding:8px 12px; font-family:Arial, Helvetica, sans-serif; font-size:13px; line-height:18px; "
            "border-bottom:1px solid #e6edf5; color:#102a43; vertical-align:top;"
        )
    body_rows = "".join(
        "<tr>"
        f"<td style='{row_style} font-weight:600; width:42%; background-color:#f8fbff;'>{escape(label)}</td>"
        f"<td style='{row_style}'>{escape(value)}</td>"
        "</tr>"
        for label, value in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%; border-collapse:separate; border-spacing:0; border:1px solid #dbe4f0; border-radius:12px; overflow:hidden; background-color:#ffffff;">'
        f'<thead><tr><th align="left" style="padding:10px 12px; background-color:#eef4fb; color:#486581; font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; text-transform:uppercase; letter-spacing:0.6px;">{escape(headers[0])}</th><th align="left" style="padding:10px 12px; background-color:#eef4fb; color:#486581; font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; text-transform:uppercase; letter-spacing:0.6px;">{escape(headers[1])}</th></tr></thead>'
        f"<tbody>{body_rows}</tbody></table>"
    )


def _render_data_table(
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    escape_cells: tuple[bool, ...] | None = None,
) -> str:
    if escape_cells is None:
        escape_cells = tuple(True for _ in headers)
    header_html = "".join(
        f'<th align="left" style="padding:12px 14px; background-color:#eef4fb; color:#486581; font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; text-transform:uppercase; letter-spacing:0.6px; border-bottom:1px solid #dbe4f0;">{escape(header)}</th>'
        for header in headers
    )
    row_html_parts: list[str] = []
    for row_index, row in enumerate(rows):
        bg = "#ffffff" if row_index % 2 == 0 else "#f8fbff"
        cells = []
        for idx, cell in enumerate(row):
            cell_value = escape(str(cell)) if escape_cells[idx] else str(cell)
            cells.append(
                f'<td style="padding:12px 14px; font-family:Arial, Helvetica, sans-serif; font-size:13px; line-height:18px; color:#102a43; border-bottom:1px solid #e6edf5; background-color:{bg}; vertical-align:top;">{cell_value}</td>'
            )
        row_html_parts.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%; border-collapse:separate; border-spacing:0; border:1px solid #dbe4f0; border-radius:12px; overflow:hidden; background-color:#ffffff;">'
        f"<thead><tr>{header_html}</tr></thead><tbody>{''.join(row_html_parts)}</tbody></table>"
    )


def _render_section_card(title: str, inner_html: str) -> str:
    return (
        '<div style="margin:0 0 18px 0; padding:0; border:1px solid #dbe4f0; border-radius:16px; overflow:hidden; background-color:#ffffff;">'
        f'<div style="padding:14px 16px; background-color:#f8fbff; color:#102a43; font-family:Arial, Helvetica, sans-serif; font-size:17px; line-height:24px; font-weight:700;">{escape(title)}</div>'
        f'<div style="padding:16px;">{inner_html}</div>'
        '</div>'
    )


def _render_metric_card(title: str, value: float, tone: str) -> str:
    palette = {
        "brand": ("#ecfdf3", "#027a48", "#12b76a"),
        "citation": ("#eff8ff", "#175cd3", "#3b82f6"),
        "sov": ("#f5f3ff", "#6d28d9", "#8b5cf6"),
        "gap": ("#fff7ed", "#c2410c", "#f97316"),
        "good": ("#ecfdf3", "#027a48", "#12b76a"),
        "watch": ("#fff7ed", "#c2410c", "#f97316"),
        "risk": ("#fef2f2", "#b42318", "#ef4444"),
    }
    bg, fg, accent = palette[tone]
    return (
        f'<div style="border-radius:16px; border:1px solid #dbe4f0; background-color:{bg}; padding:18px 18px 16px 18px;">'
        f'<div style="font-family:Arial, Helvetica, sans-serif; font-size:13px; line-height:18px; color:#486581; text-transform:uppercase; letter-spacing:0.5px;">{escape(title)}</div>'
        f'<div style="font-family:Arial, Helvetica, sans-serif; font-size:32px; line-height:38px; font-weight:700; color:{fg}; margin-top:10px;">{_format_percent(value)}</div>'
        f'{_render_progress_bar(value, accent)}'
        f'<div style="font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; color:#6b7c93; margin-top:10px;">{escape(_tone_label(value))}</div>'
        '</div>'
    )


def _render_metric_cell(title: str, value: float, tone: str) -> str:
    palette = {
        "good": "#12b76a",
        "watch": "#f97316",
        "risk": "#ef4444",
    }
    accent = palette[tone]
    return (
        f'<div style="min-width:120px;"><div style="font-family:Arial, Helvetica, sans-serif; font-size:18px; line-height:24px; font-weight:700; color:#102a43;">{_format_percent(value)}</div>'
        f'{_render_progress_bar(value, accent, height=6, margin_top=8)}'
        f'<div style="font-family:Arial, Helvetica, sans-serif; font-size:11px; line-height:16px; color:#6b7c93; margin-top:6px;">{escape(title)}</div></div>'
    )


def _render_progress_bar(value: float, accent: str, height: int = 8, margin_top: int = 12) -> str:
    safe = max(0.0, min(1.0, float(value)))
    width = int(round(safe * 100))
    return (
        f'<div style="margin-top:{margin_top}px; width:100%; background-color:#dbe4f0; border-radius:999px; height:{height}px;">'
        f'<div style="width:{width}%; min-width:8px; max-width:100%; background-color:{accent}; border-radius:999px; height:{height}px;"></div>'
        '</div>'
    )


def _render_alert_badges(alerts: list[str]) -> str:
    if not alerts:
        return '<span style="display:inline-block; padding:5px 10px; border-radius:999px; background-color:#ecfdf3; color:#027a48; font-family:Arial, Helvetica, sans-serif; font-size:11px; line-height:16px; font-weight:700;">No active alerts</span>'
    parts = []
    for alert in alerts:
        bg, fg = _alert_badge_colors(alert)
        parts.append(
            f'<span style="display:inline-block; margin:0 6px 6px 0; padding:5px 10px; border-radius:999px; background-color:{bg}; color:{fg}; font-family:Arial, Helvetica, sans-serif; font-size:11px; line-height:16px; font-weight:700;">{escape(alert)}</span>'
        )
    return ''.join(parts)


def _metric_tone(value: float) -> str:
    if value >= 0.6:
        return "good"
    if value >= 0.3:
        return "watch"
    return "risk"


def _tone_label(value: float) -> str:
    tone = _metric_tone(value)
    if tone == "good":
        return "Healthy range"
    if tone == "watch":
        return "Watchlist range"
    return "Needs attention"


def _alert_badge_colors(alert: str) -> tuple[str, str]:
    if "LOW" in alert or "GAP" in alert:
        return ("#fff4e5", "#b54708")
    if "SENTIMENT" in alert:
        return ("#fef3f2", "#b42318")
    if "COMPETITOR" in alert:
        return ("#f5f3ff", "#6d28d9")
    return ("#eef4fb", "#486581")


def _build_alerts(
    prompt_rates: dict[str, float],
    competitor_leading: list[dict],
    stats: dict,
) -> list[str]:
    alerts: list[str] = []
    for prompt_id, rate in sorted(prompt_rates.items()):
        if rate < 0.1:
            alerts.append(f"LOW VISIBILITY: {prompt_id}")

    seen_competitors: set[str] = set()
    for entry in competitor_leading:
        competitor = entry["competitor"]
        if entry["count"] > 5 and competitor not in seen_competitors:
            alerts.append(f"COMPETITOR LEADING: {competitor}")
            seen_competitors.add(competitor)

    if stats["share_of_voice"] < 0.15:
        alerts.append("LOW SHARE OF VOICE")
    if stats["sentiment_score"] < 0.7 and stats["brand_mentions"] > 0:
        alerts.append("SENTIMENT WARNING")
    if stats["non_branded_prompt_visibility_score"] < 0.3:
        alerts.append("NON-BRANDED VISIBILITY GAP")

    return alerts
