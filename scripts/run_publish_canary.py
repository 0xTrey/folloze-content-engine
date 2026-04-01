#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact  # noqa: E402
from config import Config  # noqa: E402
from content_calendar import (  # noqa: E402
    Topic,
    get_oldest_due_topic,
    load_calendar,
    mark_retry_pending,
)
from notify import send_canary_report  # noqa: E402
from runtime_secrets import get_secret  # noqa: E402
from site_rendering import retarget_release_artifact  # noqa: E402
from verify import check_live_against_artifact  # noqa: E402

LOGGER = logging.getLogger("daily_publish_canary")
LOCK_PATH = ROOT / ".content-engine.lock"
RUN_DATE_RE = re.compile(r"logs/runs/(\d{4}-\d{2}-\d{2})/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 9:15 Folloze publish canary and auto-recover missed posts"
    )
    parser.add_argument("--date", help="YYYY-MM-DD publish date to verify, defaults to today")
    parser.add_argument(
        "--skip-retry",
        action="store_true",
        help="Diagnose only and do not attempt automatic recovery",
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Pass --skip-deploy through to the recovery publish command",
    )
    args = parser.parse_args()

    _configure_logging()
    config = Config.load(ROOT / "config.yaml")
    target_date = args.date or dt.date.today().isoformat()

    LOGGER.info("Starting publish canary for %s", target_date)
    live_entries, failed_live_entries = _live_published_entries_for_date(target_date, config)
    if live_entries:
        LOGGER.info("Publish canary passed for %s with %d live entry(s)", target_date, len(live_entries))
        return 0

    diagnosis = _diagnose(target_date)
    calendar_topic, calendar_item = _load_recovery_candidate(target_date)
    actions: list[str] = []
    recovered = False
    active_publish_process = _daily_publish_process_active()

    if active_publish_process:
        actions.append("Skipped auto-retry because run_daily_publish.py was still active at canary time")
    elif not args.skip_retry:
        recovery_command = _build_recovery_command(
            target_date,
            diagnosis,
            calendar_topic,
            calendar_item,
            skip_deploy=args.skip_deploy,
        )
        if calendar_topic and calendar_topic.status == "in_progress" and recovery_command:
            mark_retry_pending(
                ROOT / "content" / "calendar.yaml",
                calendar_topic,
                "Recovered stale in_progress topic via publish canary",
                target_date,
            )
            actions.append(f"Requeued stale in_progress topic '{calendar_topic.slug}' back to pending")
        if recovery_command:
            actions.append("Ran automatic recovery publish workflow")
            try:
                _run_command(recovery_command)
            except subprocess.CalledProcessError as exc:
                actions.append(
                    "Automatic recovery publish workflow failed: "
                    f"exit {exc.returncode} from {' '.join(exc.cmd)}"
                )
                LOGGER.error("Automatic recovery publish failed: %s", exc)

    live_entries, failed_live_entries = _live_published_entries_for_date(target_date, config)
    recovered = bool(live_entries)

    if not actions:
        actions.append("No recovery action was taken")

    incident = {
        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        "target_date": target_date,
        "status": "recovered" if recovered else "failed",
        "active_publish_process": active_publish_process,
        "diagnosis": diagnosis,
        "recovery_candidate": (
            {
                "title": calendar_topic.title,
                "slug": calendar_topic.slug,
                "status": calendar_topic.status,
                "planned_date": calendar_topic.planned_date,
            }
            if calendar_topic
            else None
        ),
        "actions": actions,
        "live_entries": live_entries,
        "failed_live_entries": failed_live_entries,
    }
    incident_paths = _write_incident_report(incident)

    subject = (
        f"[Folloze Insights] Canary recovered missed publish for {target_date}"
        if recovered
        else f"[Folloze Insights] Canary failed to recover publish for {target_date}"
    )
    send_canary_report(
        subject,
        _render_incident_html(incident, incident_paths["markdown"]),
        config,
    )
    LOGGER.info("Publish canary complete for %s status=%s", target_date, incident["status"])
    return 0 if recovered else 1


def _configure_logging() -> None:
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "daily-publish-canary.log"),
            logging.StreamHandler(),
        ],
    )


def _live_published_entries_for_date(target_date: str, config: Config) -> tuple[list[dict], list[dict]]:
    live_entries: list[dict] = []
    failed_entries: list[dict] = []
    for path in sorted((ROOT / "site" / "published").glob("*.json")):
        payload = json.loads(path.read_text())
        if payload.get("published_date") != target_date:
            continue
        artifact = retarget_release_artifact(load_release_artifact(path), config)
        try:
            check_live_against_artifact(
                artifact.canonical_url,
                artifact,
                timeout_seconds=10,
                poll_interval=2,
            )
            live_entries.append(
                {
                    "slug": artifact.slug,
                    "title": artifact.title,
                    "url": artifact.canonical_url,
                    "path": str(path.relative_to(ROOT)),
                }
            )
        except Exception as exc:  # pragma: no cover - verified via caller behavior
            failed_entries.append(
                {
                    "slug": artifact.slug,
                    "title": artifact.title,
                    "url": artifact.canonical_url,
                    "path": str(path.relative_to(ROOT)),
                    "error": str(exc),
                }
            )
    return live_entries, failed_entries


def _diagnose(target_date: str) -> dict:
    run_dir = ROOT / "logs" / "runs" / target_date
    diagnosis: dict[str, object] = {
        "category": "no_run",
        "run_date": target_date,
        "run_status": None,
        "topic": None,
        "failed_stage": None,
        "error_type": None,
        "error": None,
        "quality_failures": [],
        "provider_signals": _provider_signals_for_date(target_date),
        "log_excerpt": _log_excerpt(target_date),
        "recommended_fix": (
            "The 9:05 job never wrote a run directory. Check launchd state, launchagent-error.log, "
            "and Python/venv path resolution before the next scheduled run."
        ),
    }

    manifest_path = run_dir / "run-manifest.json"
    if not manifest_path.exists():
        return diagnosis

    manifest = json.loads(manifest_path.read_text())
    diagnosis["run_status"] = manifest.get("status")
    diagnosis["topic"] = manifest.get("topic")

    run_id = manifest.get("run_id")
    events = _load_run_events(run_dir / "run-events.jsonl", run_id)
    latest_error = next(
        (
            event
            for event in reversed(events)
            if event.get("event") in {"run_error", "stage_failed"}
        ),
        None,
    )
    latest_repair = next(
        (
            event
            for event in reversed(events)
            if event.get("event") == "quality_repair_requested"
        ),
        None,
    )

    if latest_error:
        diagnosis["failed_stage"] = latest_error.get("stage")
        diagnosis["error_type"] = latest_error.get("error_type")
        diagnosis["error"] = latest_error.get("error")
    if latest_repair:
        diagnosis["quality_failures"] = latest_repair.get("failures", [])

    diagnosis["category"], diagnosis["recommended_fix"] = _classify_diagnosis(diagnosis)
    return diagnosis


def _load_run_events(path: Path, run_id: str | None) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if run_id and payload.get("run_id") != run_id:
            continue
        events.append(payload)
    return events


def _classify_diagnosis(diagnosis: dict) -> tuple[str, str]:
    run_status = diagnosis.get("run_status")
    failed_stage = diagnosis.get("failed_stage")
    error_type = diagnosis.get("error_type")
    error = str(diagnosis.get("error") or "")
    quality_failures = diagnosis.get("quality_failures") or []

    if run_status == "release_ready":
        return (
            "publish_interrupted",
            "The content pipeline finished, but the publish path did not finish. Resume from the existing artifact and add retry telemetry around promote, export, deploy, and verify.",
        )
    if run_status == "locked":
        return (
            "pipeline_locked",
            "The content pipeline was still locked when the run ended. Check for stale .content-engine.lock handling and long-running provider calls that exceeded the normal publish window.",
        )
    if run_status == "empty":
        return (
            "no_due_topic",
            "There was no due pending topic to publish. Check content/calendar.yaml coverage and make sure planned dates extend past today.",
        )
    if failed_stage == "quality_gate" and error_type == "ValidationError":
        failures = ", ".join(quality_failures) if quality_failures else error
        return (
            "quality_gate_failure",
            "The repair loop did not fully resolve a quality gate miss. Add an explicit repair instruction and a regression test for: "
            f"{failures}.",
        )
    if failed_stage == "generate_content" and error_type in {
        "ProviderUnavailableError",
        "ValidationError",
    }:
        return (
            "provider_or_schema_failure",
            "Generation failed before the quality gate. Tighten structured-output validation, track per-profile failure rates, and route away from flaky profiles that keep returning short or invalid payloads.",
        )
    if failed_stage == "enrich_research":
        return (
            "research_provider_failure",
            "Research enrichment failed. Add stronger fallback routing for research providers and alert when all research profiles degrade in the same run.",
        )
    return (
        "unknown_failure",
        "The failure mode was not classified cleanly. Inspect the run events and log excerpt, then add a new canary classifier once the root cause is clear.",
    )


def _provider_signals_for_date(target_date: str) -> dict[str, list[str]]:
    log_path = ROOT / "logs" / "content-engine.log"
    signals = {
        "gemini_failures": [],
        "gateway_failures": [],
        "gateway_successes": [],
        "research_fallbacks": [],
    }
    if not log_path.exists():
        return signals

    patterns = {
        "gemini_failures": ("Gemini failed after all retries", 3),
        "gateway_failures": ("Gateway profile=", 5),
        "gateway_successes": ("Gateway fallback succeeded via profile=", 3),
        "research_fallbacks": ("Research gateway fallback succeeded via profile=", 3),
    }
    for line in log_path.read_text().splitlines():
        if not line.startswith(target_date):
            continue
        for key, (needle, limit) in patterns.items():
            if needle in line and len(signals[key]) < limit:
                signals[key].append(line)
    return signals


def _log_excerpt(target_date: str) -> dict[str, list[str]]:
    return {
        "daily_publish": _tail_matching_lines(ROOT / "logs" / "daily-publish.log", target_date, 10),
        "launchagent_error": _tail_matching_lines(
            ROOT / "logs" / "launchagent-error.log",
            target_date,
            10,
        ),
    }


def _tail_matching_lines(path: Path, prefix: str, limit: int) -> list[str]:
    if not path.exists():
        return []
    matches = [line for line in path.read_text().splitlines() if line.startswith(prefix)]
    return matches[-limit:]


def _load_recovery_candidate(target_date: str) -> tuple[Topic | None, dict | None]:
    as_of = dt.date.fromisoformat(target_date)
    topics = load_calendar(ROOT / "content" / "calendar.yaml")
    topic = get_oldest_due_topic(topics, as_of)
    if topic is None:
        return None, None

    raw = yaml.safe_load((ROOT / "content" / "calendar.yaml").read_text()) or {}
    for item in raw.get("topics", []):
        item_slug = item.get("slug") or topic.slug
        if item_slug == topic.slug:
            return topic, item
    return topic, None


def _build_recovery_command(
    target_date: str,
    diagnosis: dict,
    topic: Topic | None,
    topic_item: dict | None,
    *,
    skip_deploy: bool,
) -> list[str] | None:
    script = str(ROOT / "scripts" / "run_daily_publish.py")
    command = [sys.executable, script]
    if skip_deploy:
        command.append("--skip-deploy")

    local_published_today = any(
        json.loads(path.read_text()).get("published_date") == target_date
        for path in sorted((ROOT / "site" / "published").glob("*.json"))
    )
    run_status = diagnosis.get("run_status")

    if local_published_today or run_status == "release_ready":
        command.extend(["--skip-pipeline", "--date", target_date])
        return command

    if topic and topic.status == "release_ready":
        artifact_path = (topic_item or {}).get("release_artifact_path", "")
        run_date = _infer_run_date_from_artifact(artifact_path)
        if run_date:
            command.extend(["--skip-pipeline", "--date", run_date])
            return command

    if topic and topic.status in {"pending", "in_progress"} and not LOCK_PATH.exists():
        return command
    return None


def _infer_run_date_from_artifact(value: str) -> str | None:
    match = RUN_DATE_RE.search(value or "")
    if not match:
        return None
    return match.group(1)


def _daily_publish_process_active() -> bool:
    try:
        completed = subprocess.run(
            ["pgrep", "-fl", "scripts/run_daily_publish.py"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False

    current_pid = str(os.getpid())
    for line in completed.stdout.splitlines():
        pid, _, command = line.partition(" ")
        if pid and pid != current_pid and "run_daily_publish.py" in command:
            return True
    return False


def _write_incident_report(incident: dict) -> dict[str, str]:
    stamp = dt.datetime.now().strftime("%H-%M-%S")
    incident_dir = ROOT / "logs" / "incidents" / incident["target_date"]
    incident_dir.mkdir(parents=True, exist_ok=True)
    base = incident_dir / f"publish-canary-{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(incident, indent=2))
    md_path.write_text(_render_incident_markdown(incident))
    return {
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
    }


def _render_incident_markdown(incident: dict) -> str:
    diagnosis = incident["diagnosis"]
    live_entries = incident.get("live_entries") or []
    failed_live_entries = incident.get("failed_live_entries") or []
    actions = "\n".join(f"- {action}" for action in incident["actions"]) or "- None"
    provider_lines = []
    for key, values in diagnosis.get("provider_signals", {}).items():
        if not values:
            continue
        provider_lines.append(f"## {key.replace('_', ' ').title()}")
        provider_lines.extend(f"- {value}" for value in values)
    provider_block = "\n".join(provider_lines) or "## Provider Signals\n- None captured"
    live_block = "\n".join(
        f"- {entry['title']} -> {entry['url']}" for entry in live_entries
    ) or "- None"
    failed_live_block = "\n".join(
        f"- {entry['title']} -> {entry['error']}" for entry in failed_live_entries
    ) or "- None"
    return f"""# Publish Canary Incident

- Target date: {incident['target_date']}
- Status: {incident['status']}
- Active publish process: {incident['active_publish_process']}
- Diagnosis category: {diagnosis.get('category')}
- Run status: {diagnosis.get('run_status')}
- Topic: {diagnosis.get('topic')}
- Failed stage: {diagnosis.get('failed_stage')}
- Error type: {diagnosis.get('error_type')}
- Error: {diagnosis.get('error')}

## Actions
{actions}

## Live Entries
{live_block}

## Failed Live Checks
{failed_live_block}

## Recommended Fix
{diagnosis.get('recommended_fix')}

{provider_block}
"""


def _render_incident_html(incident: dict, markdown_path: str) -> str:
    diagnosis = incident["diagnosis"]
    live_entries = "".join(
        f"<li><a href=\"{entry['url']}\">{entry['title']}</a></li>"
        for entry in incident.get("live_entries", [])
    ) or "<li>None</li>"
    actions = "".join(f"<li>{action}</li>" for action in incident["actions"]) or "<li>None</li>"
    provider_items = []
    for key, values in diagnosis.get("provider_signals", {}).items():
        if not values:
            continue
        items = "".join(f"<li>{value}</li>" for value in values)
        provider_items.append(f"<h2>{key.replace('_', ' ').title()}</h2><ul>{items}</ul>")
    provider_block = "".join(provider_items) or "<p>No provider signals captured.</p>"
    return f"""
    <h1>Publish Canary {incident['status'].title()}</h1>
    <p>Date: {incident['target_date']}</p>
    <p>Diagnosis: {diagnosis.get('category')}</p>
    <p>Run status: {diagnosis.get('run_status')}</p>
    <p>Topic: {diagnosis.get('topic') or 'N/A'}</p>
    <p>Recommended fix: {diagnosis.get('recommended_fix')}</p>
    <h2>Actions</h2>
    <ul>{actions}</ul>
    <h2>Live Entries</h2>
    <ul>{live_entries}</ul>
    <h2>Incident Report</h2>
    <p>{markdown_path}</p>
    {provider_block}
    """


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault(
        "PATH",
        "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    )
    token = get_secret("VERCEL_TOKEN")
    if token:
        env["VERCEL_TOKEN"] = token
    return env


def _run_command(command: list[str]) -> None:
    LOGGER.info("Running command: %s", " ".join(command))
    resolved = shutil.which(command[0], path=_command_env().get("PATH"))
    if resolved is None and not Path(command[0]).exists():
        raise FileNotFoundError(f"Command not found: {command[0]}")
    subprocess.run(command, cwd=ROOT, env=_command_env(), check=True)


if __name__ == "__main__":
    raise SystemExit(main())
