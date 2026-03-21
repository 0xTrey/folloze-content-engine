from __future__ import annotations

import html
import json
import logging
import smtplib
import subprocess
import sys
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from bs4 import BeautifulSoup

from artifacts import ReleaseArtifact
from config import Config
from content_calendar import Topic
from quality import QualityResult
from runtime_secrets import get_secret

LOGGER = logging.getLogger(__name__)


def send_release_ready(
    topic: Topic,
    artifact: ReleaseArtifact,
    quality: QualityResult,
    run_dir: Path,
    config: Config,
) -> None:
    review_items = "".join(
        f"<li>{html.escape(note)}</li>" for note in artifact.review_notes
    ) or "<li>No flags</li>"
    body = f"""
    <h1>Release Ready: {html.escape(topic.title)}</h1>
    <p>Content type: {html.escape(topic.content_type)}</p>
    <p>AEO score: {quality.score}/100</p>
    <p>Route: {html.escape(artifact.route)}</p>
    <p>Run directory: {html.escape(str(run_dir))}</p>
    <h2>JSON-LD Preview</h2>
    <pre>{html.escape(json.dumps(json.loads(artifact.json_ld), indent=2))}</pre>
    <h2>Review Notes</h2>
    <ul>{review_items}</ul>
    <p>Review the rendered preview and promote manually if approved.</p>
    """
    _send_email(f"[Folloze Insights] Release ready: {topic.title}", body, config)


def send_published(topic: Topic, url: str, quality: QualityResult, config: Config) -> None:
    body = f"""
    <h1>Published: {html.escape(topic.title)}</h1>
    <p>Live URL: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
    <p>AEO score: {quality.score}/100</p>
    """
    _send_email(f"[Folloze Insights] Published: {topic.title}", body, config)


def send_error(stage: str, error: Exception, topic: Topic | None, config: Config) -> None:
    topic_name = topic.title if topic else "N/A"
    traceback_html = html.escape(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    body = f"""
    <h1>Pipeline Error</h1>
    <p>Stage: {html.escape(stage)}</p>
    <p>Topic: {html.escape(topic_name)}</p>
    <pre>{traceback_html}</pre>
    """
    _send_email(
        f"[Folloze Insights] ERROR: {type(error).__name__} in {stage}",
        body,
        config,
    )


def _send_email(subject: str, body: str, config: Config) -> None:
    if not config.notifications.email.enabled:
        _send_discord(subject, body, config)
        return

    _send_discord(subject, body, config)

    password = get_secret("SMTP_PASSWORD")
    username = get_secret("SMTP_USER") or config.notifications.email.from_address
    recipient = get_secret(
        "NOTIFY_EMAIL_TO",
    ) or ",".join(config.notifications.email.to_addresses)
    recipients = [entry.strip() for entry in recipient.split(",") if entry.strip()]
    if not recipients:
        LOGGER.warning(
            "No email recipients configured, skipping email send for subject=%s",
            subject,
        )
        return
    if not password:
        if _send_via_agentmail(subject, body, recipients, config.notifications.email.from_address):
            return
        LOGGER.warning("SMTP_PASSWORD missing, skipping email send for subject=%s", subject)
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = config.notifications.email.from_address
    message["To"] = recipient
    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(
            get_secret("SMTP_HOST") or config.notifications.email.smtp_host,
            int(get_secret("SMTP_PORT") or config.notifications.email.smtp_port),
            timeout=15,
        ) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(
                config.notifications.email.from_address,
                recipients,
                message.as_string(),
            )
    except OSError as exc:
        LOGGER.error("Failed to send email for subject=%s: %s", subject, exc)


def _send_discord(subject: str, body_html: str, config: Config) -> None:
    discord = config.notifications.discord
    if not discord.enabled:
        return

    openclaw_cli = get_secret("OPENCLAW_CLI") or "openclaw"
    message = f"{subject}\n\n{_html_to_text(body_html)}"
    try:
        subprocess.run(
            [
                openclaw_cli,
                "message",
                "send",
                "--channel",
                "discord",
                "--target",
                discord.channel_target,
                "--message",
                message,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        LOGGER.info("Sent Discord notification for subject=%s", subject)
    except (OSError, subprocess.CalledProcessError) as exc:
        LOGGER.error("Discord notification failed for subject=%s: %s", subject, exc)


def _send_via_agentmail(
    subject: str,
    body_html: str,
    recipients: list[str],
    from_address: str,
) -> bool:
    cli_path = _resolve_agentmail_cli()
    if cli_path is None:
        return False

    body_text = _html_to_text(body_html)
    for recipient in recipients:
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(cli_path),
                    "send",
                    "--from",
                    from_address,
                    "--to",
                    recipient,
                    "--subject",
                    subject,
                    "--body",
                    body_text,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            LOGGER.error(
                "AgentMail fallback failed for recipient=%s subject=%s: %s",
                recipient,
                subject,
                exc,
            )
            return False
    LOGGER.info("Sent notification via AgentMail for subject=%s", subject)
    return True


def _resolve_agentmail_cli() -> Path | None:
    configured = get_secret("AGENTMAIL_CLI")
    candidates = [
        Path(configured) if configured else None,
        Path.home() / ".openclaw" / "workspace" / "skills" / "agentmail" / "agentmail.py",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def _html_to_text(value: str) -> str:
    text = BeautifulSoup(value, "html.parser").get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)
