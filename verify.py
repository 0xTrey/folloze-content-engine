from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from artifacts import ReleaseArtifact
from exceptions import PreviewValidationError, VerificationTimeoutError


def check_preview_file(path: Path) -> None:
    html = path.read_text()
    _validate_html(html)


def check_live(url: str, timeout_seconds: int = 300, poll_interval: int = 15) -> bool:
    html = _wait_for_live_html(url, timeout_seconds, poll_interval)
    _validate_html(html)
    return True


def check_live_against_artifact(
    url: str,
    artifact: ReleaseArtifact,
    timeout_seconds: int = 300,
    poll_interval: int = 15,
) -> bool:
    html = _wait_for_live_html(url, timeout_seconds, poll_interval)
    _validate_html(html)
    _validate_against_artifact(html, artifact)
    return True


def extract_json_ld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    payloads: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text(strip=True)
        if not text:
            continue
        payloads.append(json.loads(text))
    return payloads


def _wait_for_live_html(url: str, timeout_seconds: int, poll_interval: int) -> str:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.text
            last_error = PreviewValidationError(
                f"Unexpected status {response.status_code} for {url}"
            )
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(poll_interval)
    raise VerificationTimeoutError(f"Timed out waiting for {url}: {last_error}")


def _validate_html(html: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.title or not soup.title.get_text(strip=True):
        raise PreviewValidationError("Rendered page missing <title>")
    meta_description = soup.find("meta", attrs={"name": "description"})
    if not meta_description or not meta_description.get("content", "").strip():
        raise PreviewValidationError("Rendered page missing meta description")
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if not canonical or not canonical.get("href"):
        raise PreviewValidationError("Rendered page missing canonical link")
    if not extract_json_ld(html):
        raise PreviewValidationError("Rendered page missing JSON-LD")


def _validate_against_artifact(html: str, artifact: ReleaseArtifact) -> None:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    if title != artifact.meta_title:
        raise PreviewValidationError(
            f"Rendered page title mismatch: '{title}' != '{artifact.meta_title}'"
        )

    meta_description = soup.find("meta", attrs={"name": "description"})
    description = meta_description.get("content", "").strip() if meta_description else ""
    if description != artifact.meta_description:
        raise PreviewValidationError("Rendered page meta description does not match artifact")

    canonical = soup.find("link", attrs={"rel": "canonical"})
    canonical_href = canonical.get("href", "").strip() if canonical else ""
    if canonical_href != artifact.canonical_url:
        raise PreviewValidationError(
            f"Rendered page canonical mismatch: '{canonical_href}' != '{artifact.canonical_url}'"
        )

    h1 = soup.find("h1")
    heading = h1.get_text(" ", strip=True) if h1 else ""
    if heading != artifact.title:
        raise PreviewValidationError(
            f"Rendered page heading mismatch: '{heading}' != '{artifact.title}'"
        )
