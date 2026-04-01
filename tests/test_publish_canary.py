from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml


def _load_module(repo_copy: Path):
    module_path = repo_copy / "scripts" / "run_publish_canary.py"
    spec = importlib.util.spec_from_file_location("run_publish_canary", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publish_canary_exits_when_today_is_already_live(repo_copy: Path, monkeypatch) -> None:
    module = _load_module(repo_copy)

    monkeypatch.setattr(module.Config, "load", lambda path: object())
    monkeypatch.setattr(
        module,
        "_live_published_entries_for_date",
        lambda target_date, config: (
            [
                {
                    "slug": "already-live",
                    "title": "Already Live",
                    "url": "https://www.folloze-blog.com/insights/already-live",
                }
            ],
            [],
        ),
    )
    monkeypatch.setattr(module, "send_canary_report", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not notify when live")))
    monkeypatch.setattr(sys, "argv", ["run_publish_canary.py", "--date", "2026-04-01"])

    assert module.main() == 0


def test_publish_canary_reruns_daily_publish_for_missed_post(repo_copy: Path, monkeypatch) -> None:
    module = _load_module(repo_copy)

    commands: list[list[str]] = []
    reports: list[str] = []
    attempts = {"count": 0}

    def live_entries(target_date, config):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return [], []
        return (
            [
                {
                    "slug": "recovered-post",
                    "title": "Recovered Post",
                    "url": "https://www.folloze-blog.com/insights/recovered-post",
                }
            ],
            [],
        )

    monkeypatch.setattr(module.Config, "load", lambda path: object())
    monkeypatch.setattr(module, "_live_published_entries_for_date", live_entries)
    monkeypatch.setattr(
        module,
        "_diagnose",
        lambda target_date: {
            "category": "provider_or_schema_failure",
            "run_status": "error",
            "topic": "Recovered Post",
            "failed_stage": "generate_content",
            "error_type": "ValidationError",
            "error": "Generated content too short: 425 < 1000",
            "provider_signals": {},
            "recommended_fix": "Track provider health and route away from flaky profiles.",
        },
    )
    monkeypatch.setattr(
        module,
        "_load_recovery_candidate",
        lambda target_date: (
            module.Topic(
                "Recovered Post",
                "guide",
                "recovered-post",
                ["recovered post"],
                3,
                "pending",
                planned_date="2026-04-01",
            ),
            {
                "slug": "recovered-post",
                "status": "pending",
                "planned_date": "2026-04-01",
            },
        ),
    )
    monkeypatch.setattr(module, "_daily_publish_process_active", lambda: False)
    monkeypatch.setattr(module, "_run_command", lambda command: commands.append(command))
    monkeypatch.setattr(
        module,
        "_write_incident_report",
        lambda incident: {
            "json": "logs/incidents/2026-04-01/publish-canary.json",
            "markdown": "logs/incidents/2026-04-01/publish-canary.md",
        },
    )
    monkeypatch.setattr(module, "send_canary_report", lambda subject, body, config: reports.append(subject))
    monkeypatch.setattr(sys, "argv", ["run_publish_canary.py", "--date", "2026-04-01"])

    assert module.main() == 0
    assert commands == [[sys.executable, str(repo_copy / "scripts" / "run_daily_publish.py")]]
    assert reports == ["[Folloze Insights] Canary recovered missed publish for 2026-04-01"]


def test_publish_canary_requeues_stale_in_progress_topic(repo_copy: Path, monkeypatch) -> None:
    module = _load_module(repo_copy)

    (repo_copy / "content" / "calendar.yaml").write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Stuck Topic",
                        "content_type": "guide",
                        "slug": "stuck-topic",
                        "keywords": ["stuck topic"],
                        "priority": 4,
                        "planned_date": "2026-04-01",
                        "status": "in_progress",
                    }
                ]
            },
            sort_keys=False,
        )
    )

    commands: list[list[str]] = []
    attempts = {"count": 0}

    def live_entries(target_date, config):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return [], []
        return (
            [
                {
                    "slug": "stuck-topic",
                    "title": "Stuck Topic",
                    "url": "https://www.folloze-blog.com/insights/stuck-topic",
                }
            ],
            [],
        )

    monkeypatch.setattr(module.Config, "load", lambda path: object())
    monkeypatch.setattr(module, "_live_published_entries_for_date", live_entries)
    monkeypatch.setattr(
        module,
        "_diagnose",
        lambda target_date: {
            "category": "no_run",
            "run_status": None,
            "topic": None,
            "failed_stage": None,
            "error_type": None,
            "error": None,
            "provider_signals": {},
            "recommended_fix": "Check launchd.",
        },
    )
    monkeypatch.setattr(module, "_daily_publish_process_active", lambda: False)
    monkeypatch.setattr(module, "_run_command", lambda command: commands.append(command))
    monkeypatch.setattr(
        module,
        "_write_incident_report",
        lambda incident: {
            "json": "logs/incidents/2026-04-01/publish-canary.json",
            "markdown": "logs/incidents/2026-04-01/publish-canary.md",
        },
    )
    monkeypatch.setattr(module, "send_canary_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["run_publish_canary.py", "--date", "2026-04-01"])

    assert module.main() == 0
    assert commands == [[sys.executable, str(repo_copy / "scripts" / "run_daily_publish.py")]]

    payload = yaml.safe_load((repo_copy / "content" / "calendar.yaml").read_text())
    item = payload["topics"][0]
    assert item["status"] == "pending"
    assert item["retry_count"] == 1
    assert item["last_error"] == "Recovered stale in_progress topic via publish canary"


def test_publish_canary_reports_failed_recovery_attempt(repo_copy: Path, monkeypatch) -> None:
    module = _load_module(repo_copy)

    incidents: list[dict] = []
    reports: list[str] = []

    monkeypatch.setattr(module.Config, "load", lambda path: object())
    monkeypatch.setattr(module, "_live_published_entries_for_date", lambda target_date, config: ([], []))
    monkeypatch.setattr(
        module,
        "_diagnose",
        lambda target_date: {
            "category": "provider_or_schema_failure",
            "run_status": "error",
            "topic": "Recovered Post",
            "failed_stage": "generate_content",
            "error_type": "ProviderUnavailableError",
            "error": "All providers failed",
            "provider_signals": {},
            "recommended_fix": "Restore cloud fallback profiles.",
        },
    )
    monkeypatch.setattr(
        module,
        "_load_recovery_candidate",
        lambda target_date: (
            module.Topic(
                "Recovered Post",
                "guide",
                "recovered-post",
                ["recovered post"],
                3,
                "pending",
                planned_date="2026-04-01",
            ),
            {
                "slug": "recovered-post",
                "status": "pending",
                "planned_date": "2026-04-01",
            },
        ),
    )
    monkeypatch.setattr(module, "_daily_publish_process_active", lambda: False)
    monkeypatch.setattr(
        module,
        "_run_command",
        lambda command: (_ for _ in ()).throw(subprocess.CalledProcessError(1, command)),
    )
    monkeypatch.setattr(
        module,
        "_write_incident_report",
        lambda incident: (
            incidents.append(incident)
            or {
                "json": "logs/incidents/2026-04-01/publish-canary.json",
                "markdown": "logs/incidents/2026-04-01/publish-canary.md",
            }
        ),
    )
    monkeypatch.setattr(module, "send_canary_report", lambda subject, body, config: reports.append(subject))
    monkeypatch.setattr(sys, "argv", ["run_publish_canary.py", "--date", "2026-04-01"])

    assert module.main() == 1
    assert reports == ["[Folloze Insights] Canary failed to recover publish for 2026-04-01"]
    assert any(
        action.startswith("Automatic recovery publish workflow failed: exit 1")
        for action in incidents[0]["actions"]
    )
