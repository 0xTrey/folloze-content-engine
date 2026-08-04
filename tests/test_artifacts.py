from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from artifacts import (
    ReleaseArtifact,
    load_release_artifact,
    render_preview_html,
    write_release_artifact,
)
from config import Config
from content_calendar import Topic
from evidence import SourceCandidate, build_evidence_report
from generator import GeneratedContent
from optimizer import OptimizedContent
from quality import QualityResult


def test_write_release_artifact_outputs_expected_shape(project_root: Path) -> None:
    run_dir = project_root / "logs" / "runs" / "2026-03-20"
    topic = Topic("Hello", "guide", "hello", ["hello"], 5, "pending")
    generated = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Folloze is a system.</p>",
        [],
        1000,
        "guide",
        "hello",
    )
    optimized = OptimizedContent(
        generated,
        generated.body_html,
        '{"@context":"https://schema.org","@type":"Article"}',
        "Article",
    )
    quality = QualityResult(True, 80, ["ok"], [])
    artifact = write_release_artifact(topic, optimized, quality, Config.load(), run_dir, "run-1")
    assert (run_dir / "release-artifact.json").exists()
    assert (run_dir / "social-brief.json").exists()
    loaded = load_release_artifact(run_dir / "release-artifact.json")
    assert loaded.slug == artifact.slug


def test_write_release_artifact_includes_backward_compatible_evidence_fields(
    project_root: Path,
) -> None:
    run_dir = project_root / "logs" / "runs" / "2026-03-21"
    topic = Topic("Evidence", "guide", "evidence", ["evidence"], 5, "pending")
    body_html = (
        '<p>Teams improved conversion by 25% in the '
        '<a href="https://research.example/report">benchmark report</a>.</p>'
    )
    generated = GeneratedContent(
        topic,
        "Evidence",
        "Evidence description",
        body_html,
        [],
        1000,
        "guide",
        "evidence",
    )
    optimized = OptimizedContent(
        generated,
        body_html,
        '{"@context":"https://schema.org","@type":"Article"}',
        "Article",
    )
    report = build_evidence_report(
        body_html,
        [
            SourceCandidate(
                title="Benchmark report",
                url="https://research.example/report",
                publisher="Research Example",
                origin="brave",
            )
        ],
    )
    artifact = write_release_artifact(
        topic,
        optimized,
        QualityResult(True, 80, ["ok"], []),
        Config.load(),
        run_dir,
        "run-evidence",
        evidence_report=report,
    )

    assert artifact.evidence_status == "ready"
    assert artifact.evidence_score == 100
    assert artifact.source_candidates is not None
    assert artifact.evidence_plan is not None


def test_render_preview_html_contains_metadata(project_root: Path) -> None:
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
    html = render_preview_html(artifact, project_root / "site" / "templates")
    assert "<title>Meta</title>" in html
    assert "application/ld+json" in html


def test_load_release_artifact_rejects_invalid_shape(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bad.json"
    artifact_path.write_text(json.dumps({"slug": "missing-fields"}))
    with pytest.raises(Exception):
        load_release_artifact(artifact_path)


def test_load_release_artifact_ignores_publish_metadata(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "title": "Title",
                "slug": "title",
                "route": "/insights/title",
                "content_type": "guide",
                "body_html": "<p>Hello</p>",
                "meta_title": "Meta",
                "meta_description": "Desc",
                "json_ld": '{"@context":"https://schema.org","@type":"Article"}',
                "target_keywords": ["hello"],
                "published_date": "2026-03-20",
                "citation_score": 80,
                "word_count": 1000,
                "canonical_url": "https://insights.folloze.com/insights/title",
                "source_run_id": "run-1",
                "status": "published",
                "review_notes": [],
                "promoted_at": "2026-03-20T12:00:00+00:00",
            }
        )
    )
    artifact = load_release_artifact(artifact_path)
    assert artifact.slug == "title"


def test_build_site_generates_output(repo_copy: Path) -> None:
    artifact = {
        "title": "Title",
        "slug": "title",
        "route": "/insights/title",
        "content_type": "guide",
        "body_html": "<p>Hello</p>",
        "meta_title": "Meta",
        "meta_description": "Desc",
        "json_ld": '{"@context":"https://schema.org","@type":"Article"}',
        "target_keywords": ["hello"],
        "published_date": "2026-03-20",
        "citation_score": 80,
        "word_count": 1000,
        "canonical_url": "https://insights.folloze.com/insights/title",
        "source_run_id": "run-1",
        "status": "published",
        "review_notes": [],
    }
    (repo_copy / "site" / "published" / "title.json").write_text(json.dumps(artifact, indent=2))
    social_briefs_dir = repo_copy / "site" / "published" / "social-briefs"
    social_briefs_dir.mkdir(parents=True, exist_ok=True)
    social_brief = {
        "title": "Title",
        "slug": "title",
        "published_date": "2026-03-20",
        "canonical_url": "https://insights.folloze.com/insights/title",
        "source_run_id": "run-1",
        "content_type": "guide",
        "theme": "Title",
        "thesis": "A concise thesis.",
        "summary": "A concise summary.",
        "target_keywords": ["hello"],
        "key_takeaways": ["First takeaway"],
        "proof_points": ["50% faster campaign builds"],
        "brand_posture": "personal_thought_leadership_rooted_in_blog",
        "role_angle_suggestions": {"marketing": "Use the practical marketing angle."},
        "generated_at": "2026-03-20T12:00:00+00:00",
    }
    (social_briefs_dir / "title.json").write_text(json.dumps(social_brief, indent=2))
    (social_briefs_dir / "latest.json").write_text(json.dumps(social_brief, indent=2))
    (repo_copy / "site" / "published" / "index.json").write_text(
        json.dumps({"artifacts": [{"slug": "title", "path": "title.json"}]}, indent=2)
    )
    subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "build-site.py")],
        cwd=repo_copy,
        check=True,
    )
    assert (repo_copy / "site" / "dist" / "insights" / "title" / "index.html").exists()
    rendered_article = (
        repo_copy / "site" / "dist" / "insights" / "title" / "index.html"
    ).read_text(encoding="utf-8")
    assert "googletagmanager.com/gtag/js?id=G-JDDWKS0VX6" in rendered_article
    assert "gtag('config', 'G-JDDWKS0VX6'" in rendered_article
    assert (repo_copy / "site" / "dist" / "social-briefs" / "title.json").exists()
    assert (repo_copy / "site" / "dist" / "social-briefs" / "latest.json").exists()
    deployment_manifest = json.loads(
        (repo_copy / "site" / "dist" / "deployment-manifest.json").read_text()
    )
    assert deployment_manifest["artifact_count"] == 1
    assert deployment_manifest["routes"][0]["slug"] == "title"
    assert deployment_manifest["routes"][0]["social_brief_url"].endswith("/social-briefs/title.json")
    assert deployment_manifest["latest_social_brief"]["slug"] == "title"


def test_promote_artifact_is_idempotent(repo_copy: Path) -> None:
    artifact = {
        "title": "Title",
        "slug": "folloze-vs-mutiny",
        "route": "/insights/folloze-vs-mutiny",
        "content_type": "comparison",
        "body_html": "<p>Hello</p>",
        "meta_title": "Meta",
        "meta_description": "Desc",
        "json_ld": '{"@context":"https://schema.org","@type":"Article"}',
        "target_keywords": ["folloze vs mutiny"],
        "published_date": "2026-03-20",
        "citation_score": 80,
        "word_count": 1000,
        "canonical_url": "https://insights.folloze.com/insights/folloze-vs-mutiny",
        "source_run_id": "run-1",
        "status": "release_ready",
        "review_notes": [],
    }
    run_dir = repo_copy / "logs" / "runs" / "2026-03-20"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "release-artifact.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))
    (run_dir / "social-brief.json").write_text(
        json.dumps(
            {
                "title": "Title",
                "slug": "folloze-vs-mutiny",
                "published_date": "2026-03-20",
                "canonical_url": "https://insights.folloze.com/insights/folloze-vs-mutiny",
                "source_run_id": "run-1",
                "content_type": "comparison",
                "theme": "Title",
                "thesis": "A concise thesis.",
                "summary": "A concise summary.",
                "target_keywords": ["folloze vs mutiny"],
                "key_takeaways": ["First takeaway"],
                "proof_points": ["$6.3M pipeline"],
                "brand_posture": "specific_folloze_branded_ok",
                "role_angle_suggestions": {"sales": "Use the sales angle."},
                "generated_at": "2026-03-20T12:00:00+00:00",
            },
            indent=2,
        )
    )
    command = [
        sys.executable,
        str(repo_copy / "scripts" / "promote-artifact.py"),
        "--artifact",
        str(artifact_path),
    ]
    subprocess.run(command, cwd=repo_copy, check=True)
    subprocess.run(command, cwd=repo_copy, check=True)
    manifest = json.loads((repo_copy / "site" / "published" / "index.json").read_text())
    folloze_entries = [
        entry for entry in manifest["artifacts"] if entry["slug"] == "folloze-vs-mutiny"
    ]
    assert len(folloze_entries) == 1
    assert folloze_entries[0]["social_brief_path"] == "social-briefs/folloze-vs-mutiny.json"
    assert folloze_entries[0]["social_brief_url"].endswith("/social-briefs/folloze-vs-mutiny.json")
    assert (repo_copy / "site" / "published" / "social-briefs" / "folloze-vs-mutiny.json").exists()
    assert (repo_copy / "site" / "published" / "social-briefs" / "latest.json").exists()
    promotion_log = (repo_copy / "logs" / "promotions.jsonl").read_text().strip().splitlines()
    assert len(promotion_log) == 2


def test_export_vercel_writes_prebuilt_output(repo_copy: Path) -> None:
    artifact = {
        "title": "Title",
        "slug": "title",
        "route": "/insights/title",
        "content_type": "guide",
        "body_html": "<p>Hello</p>",
        "meta_title": "Meta",
        "meta_description": "Desc",
        "json_ld": '{"@context":"https://schema.org","@type":"Article"}',
        "target_keywords": ["hello"],
        "published_date": "2026-03-20",
        "citation_score": 80,
        "word_count": 1000,
        "canonical_url": "https://insights.folloze.com/insights/title",
        "source_run_id": "run-1",
        "status": "published",
        "review_notes": [],
    }
    (repo_copy / "site" / "published" / "title.json").write_text(json.dumps(artifact, indent=2))
    (repo_copy / "site" / "published" / "index.json").write_text(
        json.dumps({"artifacts": [{"slug": "title", "path": "title.json"}]}, indent=2)
    )
    subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "export-vercel.py")],
        cwd=repo_copy,
        check=True,
    )
    assert (
        repo_copy / ".vercel" / "output" / "static" / "insights" / "title" / "index.html"
    ).exists()
    assert (repo_copy / ".vercel" / "output" / "config.json").exists()
