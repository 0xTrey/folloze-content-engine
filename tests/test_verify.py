from __future__ import annotations

from pathlib import Path

import pytest
import requests

from artifacts import ReleaseArtifact
from exceptions import PreviewValidationError, VerificationTimeoutError
from verify import check_live, check_live_against_artifact, check_preview_file


def test_check_preview_file_passes_with_valid_html(tmp_path: Path) -> None:
    html_path = tmp_path / "preview.html"
    html_path.write_text(
        """
        <html><head>
        <title>Example</title>
        <meta name="description" content="desc">
        <link rel="canonical" href="https://example.com">
        <script type="application/ld+json">{"@context":"https://schema.org","@type":"Article"}</script>
        </head><body></body></html>
        """
    )
    check_preview_file(html_path)


def test_check_preview_file_raises_on_missing_json_ld(tmp_path: Path) -> None:
    html_path = tmp_path / "preview.html"
    html_path.write_text(
        """
        <html><head>
        <title>Example</title>
        <meta name="description" content="desc">
        <link rel="canonical" href="https://example.com">
        </head><body></body></html>
        """
    )
    with pytest.raises(PreviewValidationError):
        check_preview_file(html_path)


def test_check_live_times_out_cleanly(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr("verify.requests.get", fake_get)
    monkeypatch.setattr("verify.time.sleep", lambda *_args, **_kwargs: None)
    with pytest.raises(VerificationTimeoutError):
        check_live("https://example.com", timeout_seconds=0, poll_interval=0)


def test_check_live_against_artifact_rejects_metadata_mismatch(monkeypatch) -> None:
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
        canonical_url="https://insights.folloze.com/insights/title",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )

    class Response:
        status_code = 200
        text = """
        <html><head>
        <title>Wrong</title>
        <meta name="description" content="Desc">
        <link rel="canonical" href="https://insights.folloze.com/insights/title">
        <script type="application/ld+json">{"@context":"https://schema.org","@type":"Article"}</script>
        </head><body><h1>Title</h1></body></html>
        """

    monkeypatch.setattr("verify.requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(PreviewValidationError):
        check_live_against_artifact("https://preview.example.com/insights/title", artifact)
