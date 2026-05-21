from __future__ import annotations

import html
import json
import logging
import re
import smtplib
import subprocess
import sys
import traceback
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - fallback for lean environments
    BeautifulSoup = None

from artifacts import ReleaseArtifact
from config import Config
from content_calendar import Topic
from quality import QualityResult
from runtime_secrets import get_secret

LOGGER = logging.getLogger(__name__)

CLOUDFLARE_EMAIL_WORKER_URL = "https://juno-cloudflare-relay.harnden-trey.workers.dev/send-email"
CLOUDFLARE_EMAIL_FROM = "juno@elevation-engine.com"
EMAIL_ONLY_ON_FAILURE_SUBJECT_PATTERNS = (
    re.compile(r"ERROR:", re.IGNORECASE),
    re.compile(r"\bfailed\b", re.IGNORECASE),
)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "li", "pre", "br", "ul", "ol"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


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


def send_canary_report(subject: str, body: str, config: Config) -> None:
    _send_email(subject, body, config)


def _send_email(subject: str, body: str, config: Config) -> None:
    if not config.notifications.email.enabled:
        _send_discord(subject, body, config)
        return

    _send_discord(subject, body, config)

    if not _should_send_email(subject):
        LOGGER.info("Skipping email for success notification subject=%s", subject)
        return

    password = get_secret("SMTP_PASSWORD")
    username = get_secret("SMTP_USER") or config.notifications.email.from_address
    recipient = get_secret(
        "NOTIFY_EMAIL_TO",
    ) or ",".join(_resolve_recipients(subject, config))
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
        if _allow_cloudflare_email(subject) and _send_via_cloudflare(
            subject,
            body,
            recipients,
            config.notifications.email.from_address,
        ):
            return
        LOGGER.warning("SMTP_PASSWORD missing and AgentMail send failed for subject=%s", subject)
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
    message = _format_discord_message(subject, body_html)
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


def _format_discord_message(subject: str, body_html: str) -> str:
    text_body = _html_to_text(body_html)
    if "Visibility Monitor Alerts" not in subject:
        return f"{subject}\n\n{text_body}"

    metrics = _extract_metric_pairs(text_body)
    alerts = _extract_section_items(text_body, "Alerts", {"Gap Prompts", "Competitor Sightings", "Source Attribution"})
    gaps = _extract_section_items(text_body, "Gap Prompts", {"Competitor Sightings", "Source Attribution"})
    competitors = _extract_section_items(text_body, "Competitor Sightings", {"Source Attribution"})
    sources = _extract_section_items(text_body, "Source Attribution", set())

    lines = [subject, "", "Scorecard"]
    preferred_order = [
        "Brand Visibility Score",
        "Citation Rate",
        "Share of Voice",
        "Sentiment Score",
        "Branded Prompt Visibility",
        "Non-branded Prompt Visibility",
        "Failure count",
    ]
    for key in preferred_order:
        if key in metrics:
            lines.append(f"- {key}: {metrics[key]}")

    if alerts:
        lines.append("")
        lines.append("Alerts")
        lines.extend(f"- {item}" for item in alerts[:8])

    if gaps:
        lines.append("")
        lines.append("Largest prompt gaps")
        lines.extend(f"- {item}" for item in gaps[:5])

    if competitors:
        lines.append("")
        lines.append("Competitor pressure")
        lines.extend(f"- {item}" for item in competitors[:5])

    if sources:
        lines.append("")
        lines.append("Top attributed sources")
        lines.extend(f"- {item}" for item in sources[:5])

    return "\n".join(lines)


def _extract_metric_pairs(text: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {
            "Run date",
            "Prompts checked",
            "Brand Visibility Score",
            "Citation Rate",
            "Share of Voice",
            "Sentiment Score",
            "Branded Prompt Visibility",
            "Non-branded Prompt Visibility",
            "Failure count",
        }:
            metrics[key] = value
    return metrics


def _extract_section_items(text: str, section_name: str, stop_headers: set[str]) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    items: list[str] = []
    in_section = False
    for line in lines:
        if not line:
            continue
        if line == section_name:
            in_section = True
            continue
        if in_section and line in stop_headers:
            break
        if in_section:
            items.append(re.sub(r"^[•*-]\s*", "", line))
    return [item for item in items if item and item != "None"]


def _should_send_email(subject: str) -> bool:
    if subject.startswith("[Folloze GEO] Weekly"):
        return True
    return any(pattern.search(subject) for pattern in EMAIL_ONLY_ON_FAILURE_SUBJECT_PATTERNS)


def _allow_cloudflare_email(subject: str) -> bool:
    # Cloudflare Email Sending requires every destination recipient to be verified.
    # Do not use it for Folloze stakeholder reports or arbitrary outbound email.
    # Keep it only as an explicitly enabled diagnostic/internal-agent fallback.
    return get_secret("ALLOW_CLOUDFLARE_EMAIL_SEND") == "1" and not subject.startswith(
        "[Folloze GEO]"
    )


def _resolve_recipients(subject: str, config: Config) -> list[str]:
    if subject.startswith("[Folloze GEO] Weekly"):
        return config.notifications.email.weekly_geo_to_addresses or []
    return config.notifications.email.to_addresses


def _send_via_cloudflare(
    subject: str,
    body_html: str,
    recipients: list[str],
    from_address: str,
) -> bool:
    token = get_secret("CLOUDFLARE_EMAIL_SEND_TOKEN")
    if not token:
        return False

    worker_url = get_secret("CLOUDFLARE_EMAIL_WORKER_URL") or CLOUDFLARE_EMAIL_WORKER_URL
    effective_from = get_secret("CLOUDFLARE_EMAIL_FROM") or CLOUDFLARE_EMAIL_FROM or from_address
    text_body = _html_to_text(body_html)
    payload = {
        "to": recipients,
        "from": effective_from,
        "subject": subject,
        "html": body_html,
        "text": text_body,
    }
    request = urllib.request.Request(
        worker_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            LOGGER.info(
                "Sent notification via Cloudflare email worker for subject=%s response=%s",
                subject,
                response_body,
            )
            return True
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        LOGGER.error(
            "Cloudflare email send failed for subject=%s status=%s details=%s",
            subject,
            exc.code,
            details,
        )
    except (urllib.error.URLError, OSError) as exc:
        LOGGER.error("Cloudflare email send failed for subject=%s: %s", subject, exc)
    return False


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
    if BeautifulSoup is not None:
        text = BeautifulSoup(value, "html.parser").get_text("\n")
    else:
        parser = _HTMLTextExtractor()
        parser.feed(value)
        parser.close()
        text = parser.get_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)
