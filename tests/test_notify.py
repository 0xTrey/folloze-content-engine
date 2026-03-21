from __future__ import annotations

import subprocess
from pathlib import Path

from artifacts import ReleaseArtifact
from config import Config
from content_calendar import Topic
from notify import send_error, send_release_ready
from quality import QualityResult


class FakeSMTP:
    sent_messages: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        return None

    def login(self, username, password):
        self.username = username
        self.password = password

    def sendmail(self, from_address, recipients, message):
        self.sent_messages.append(message)


class FakeCompletedProcess(subprocess.CompletedProcess):
    def __init__(self, args):
        super().__init__(args=args, returncode=0, stdout="", stderr="")


def test_send_release_ready_renders_email(project_root, monkeypatch) -> None:
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )
    artifact = ReleaseArtifact(
        title="Title",
        slug="title",
        route="/insights/title",
        content_type="guide",
        body_html="<p>Hello</p>",
        meta_title="Meta",
        meta_description="Desc",
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        target_keywords=["hello"],
        published_date="2026-03-20",
        citation_score=80,
        word_count=1000,
        canonical_url="https://example.com/insights/title",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )
    send_release_ready(
        Topic("Title", "guide", "title", ["hello"], 5, "release_ready"),
        artifact,
        QualityResult(True, 80, [], []),
        Path("logs/runs/2026-03-20"),
        Config.load(),
    )
    assert FakeSMTP.sent_messages


def test_send_error_renders_email(project_root, monkeypatch) -> None:
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )
    send_error("pipeline", RuntimeError("boom"), None, Config.load())
    assert any("RuntimeError" in message for message in FakeSMTP.sent_messages)


def test_send_release_ready_falls_back_to_agentmail(project_root, monkeypatch, tmp_path) -> None:
    agentmail_cli = tmp_path / "agentmail.py"
    agentmail_cli.write_text("print('ok')\n")
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setattr(
        "notify.get_secret",
        lambda name, *services: None if name == "SMTP_PASSWORD" else "",
    )
    monkeypatch.setattr("notify._resolve_agentmail_cli", lambda: agentmail_cli)
    monkeypatch.setattr("notify.subprocess.run", fake_run)

    artifact = ReleaseArtifact(
        title="Title",
        slug="title",
        route="/insights/title",
        content_type="guide",
        body_html="<p>Hello</p>",
        meta_title="Meta",
        meta_description="Desc",
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        target_keywords=["hello"],
        published_date="2026-03-20",
        citation_score=80,
        word_count=1000,
        canonical_url="https://example.com/insights/title",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )
    send_release_ready(
        Topic("Title", "guide", "title", ["hello"], 5, "release_ready"),
        artifact,
        QualityResult(True, 80, [], []),
        Path("logs/runs/2026-03-20"),
        Config.load(),
    )
    assert calls
    assert calls[0][2] == "send"


def test_send_release_ready_posts_to_discord(project_root, monkeypatch) -> None:
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        return FakeCompletedProcess(command)

    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("notify.subprocess.run", fake_run)

    artifact = ReleaseArtifact(
        title="Title",
        slug="title",
        route="/insights/title",
        content_type="guide",
        body_html="<p>Hello</p>",
        meta_title="Meta",
        meta_description="Desc",
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        target_keywords=["hello"],
        published_date="2026-03-20",
        citation_score=80,
        word_count=1000,
        canonical_url="https://example.com/insights/title",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )
    send_release_ready(
        Topic("Title", "guide", "title", ["hello"], 5, "release_ready"),
        artifact,
        QualityResult(True, 80, [], []),
        Path("logs/runs/2026-03-20"),
        Config.load(),
    )
    assert any(command[0] == "openclaw" for command in calls)
