from __future__ import annotations

import subprocess
from pathlib import Path

from artifacts import ReleaseArtifact
from config import Config
from content_calendar import Topic
from notify import (
    _format_discord_message,
    _resolve_recipients,
    _should_send_email,
    send_canary_report,
    send_error,
    send_published,
    send_release_ready,
)
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


def test_send_release_ready_skips_email_for_success(project_root, monkeypatch) -> None:
    FakeSMTP.sent_messages.clear()
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
    assert not FakeSMTP.sent_messages


def test_send_published_skips_email_for_success(project_root, monkeypatch) -> None:
    FakeSMTP.sent_messages.clear()
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )

    send_published(
        Topic("Title", "guide", "title", ["hello"], 5, "published"),
        "https://example.com/insights/title",
        QualityResult(True, 80, [], []),
        Config.load(),
    )

    assert not FakeSMTP.sent_messages


def test_send_error_renders_email(project_root, monkeypatch) -> None:
    FakeSMTP.sent_messages.clear()
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )
    send_error("pipeline", RuntimeError("boom"), None, Config.load())
    assert any("RuntimeError" in message for message in FakeSMTP.sent_messages)


def test_send_canary_recovered_skips_email(project_root, monkeypatch) -> None:
    FakeSMTP.sent_messages.clear()
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )

    send_canary_report(
        "[Folloze Insights] Canary recovered missed publish for 2026-04-01",
        "<p>Recovered</p>",
        Config.load(),
    )

    assert not FakeSMTP.sent_messages


def test_send_canary_failed_still_emails(project_root, monkeypatch) -> None:
    FakeSMTP.sent_messages.clear()
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setattr("notify.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )

    send_canary_report(
        "[Folloze Insights] Canary failed to recover publish for 2026-04-01",
        "<p>Failed</p>",
        Config.load(),
    )

    assert any("Canary failed to recover publish" in message for message in FakeSMTP.sent_messages)


def test_resolve_recipients_uses_weekly_geo_list(project_root) -> None:
    config = Config.load()

    recipients = _resolve_recipients(
        "[Folloze GEO] Weekly Visibility Monitor — 2026-04-14 to 2026-04-20",
        config,
    )

    assert recipients == [
        "trey.harnden@folloze.com",
        "kristi.tutt@folloze.com",
    ]


def test_weekly_geo_subject_sends_email() -> None:
    assert _should_send_email(
        "[Folloze GEO] Weekly Visibility Monitor — 2026-04-14 to 2026-04-20"
    )


def test_weekly_geo_uses_agentmail_not_cloudflare(project_root, monkeypatch, tmp_path) -> None:
    agentmail_cli = tmp_path / "agentmail.py"
    agentmail_cli.write_text("print('ok')\n")
    cloudflare_calls = []
    agentmail_calls = []

    def fake_cloudflare(subject, body, recipients, from_address):
        cloudflare_calls.append((subject, recipients, from_address))
        return True

    def fake_agentmail(subject, body, recipients, from_address):
        agentmail_calls.append((subject, recipients, from_address))
        return True

    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("ALLOW_CLOUDFLARE_EMAIL_SEND", raising=False)
    monkeypatch.setattr("notify._resolve_agentmail_cli", lambda: agentmail_cli)
    monkeypatch.setattr("notify._send_via_cloudflare", fake_cloudflare)
    monkeypatch.setattr("notify._send_via_agentmail", fake_agentmail)
    monkeypatch.setattr(
        "notify.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(args[0]),
    )

    subject = "[Folloze GEO] Weekly Visibility Monitor — 2026-04-14 to 2026-04-20"
    send_canary_report(subject, "<p>Weekly GEO report</p>", Config.load())

    assert cloudflare_calls == []
    assert agentmail_calls == [
        (
            subject,
            ["trey.harnden@folloze.com", "kristi.tutt@folloze.com"],
            "juno@elevationengine.co",
        )
    ]


def test_resolve_recipients_keeps_errors_off_weekly_geo_list(project_root) -> None:
    config = Config.load()

    recipients = _resolve_recipients(
        "[Folloze Insights] ERROR: RuntimeError in pipeline",
        config,
    )

    assert recipients == ["trey.harnden@folloze.com"]


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
    assert not any(
        len(command) > 2 and str(command[1]).endswith("agentmail.py") and command[2] == "send"
        for command in calls
    )


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


def test_format_visibility_discord_message() -> None:
    body = """
    <h1>Visibility Monitor Alerts</h1>
    <p>Run date: 2026-04-14</p>
    <p>Prompts checked: 15</p>
    <p>Brand Visibility Score: 31%</p>
    <p>Citation Rate: 12%</p>
    <p>Share of Voice: 18%</p>
    <p>Sentiment Score: 80%</p>
    <p>Branded Prompt Visibility: 60%</p>
    <p>Non-branded Prompt Visibility: 22%</p>
    <p>Failure count: 0</p>
    <h2>Alerts</h2>
    <ul><li>LOW SHARE OF VOICE</li><li>NON-BRANDED VISIBILITY GAP</li></ul>
    <h2>Gap Prompts</h2>
    <ul><li>t1-001</li></ul>
    <h2>Competitor Sightings</h2>
    <ul><li>mutiny on t1-001: 6</li></ul>
    <h2>Source Attribution</h2>
    <ul><li>https://www.folloze.com/insights/example: 2</li></ul>
    """
    message = _format_discord_message(
        "[Folloze GEO] Visibility Monitor Alerts — 2026-04-14",
        body,
    )
    assert "Scorecard" in message
    assert "- Brand Visibility Score: 31%" in message
    assert "Alerts" in message
    assert "Largest prompt gaps" in message
    assert "Top attributed sources" in message
