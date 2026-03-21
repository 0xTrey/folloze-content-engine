from __future__ import annotations

import json
import sys
from dataclasses import asdict

import pipeline
from artifacts import ReleaseArtifact
from content_calendar import Topic
from generator import GeneratedContent
from optimizer import OptimizedContent
from quality import QualityResult
from research import ResearchContext


def _topic() -> Topic:
    return Topic(
        "Folloze vs Mutiny",
        "comparison",
        "folloze-vs-mutiny",
        ["folloze vs mutiny"],
        5,
        "pending",
    )


def test_full_happy_path_release_ready(project_root, monkeypatch) -> None:
    topic = _topic()
    research = ResearchContext(topic, [], "summary", "brief", "brand")
    generated = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Folloze is a platform.</p>",
        [],
        1000,
        "comparison",
        "folloze vs mutiny",
    )
    optimized = OptimizedContent(
        generated,
        "<p>Folloze is a platform. According to Gartner, 98%.</p><h2>FAQ</h2><p>Q</p>",
        '{"@context":"https://schema.org","@type":"Article"}',
        "Article",
    )
    artifact = ReleaseArtifact(
        title="Title",
        slug="folloze-vs-mutiny",
        route="/insights/folloze-vs-mutiny",
        content_type="comparison",
        body_html=optimized.body_html,
        meta_title="Title",
        meta_description="Desc",
        json_ld=optimized.json_ld,
        target_keywords=["folloze vs mutiny"],
        published_date="2026-03-20",
        citation_score=82,
        word_count=1000,
        canonical_url="https://insights.folloze.com/insights/folloze-vs-mutiny",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )

    monkeypatch.setattr(pipeline, "enrich", lambda *args, **kwargs: research)
    monkeypatch.setattr(pipeline, "generate", lambda *args, **kwargs: generated)
    monkeypatch.setattr(pipeline, "optimize", lambda *args, **kwargs: optimized)
    monkeypatch.setattr(pipeline, "gate", lambda *args, **kwargs: QualityResult(True, 82, [], []))

    def fake_write_release_artifact(*args, **kwargs):
        run_dir = args[4]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "release-artifact.json").write_text(json.dumps(asdict(artifact), indent=2))
        (run_dir / "rendered-preview.html").write_text(
            "<html><head><title>Title</title><meta name='description' content='Desc'>"
            "<link rel='canonical' href='https://example.com'>"
            "<script type='application/ld+json'>{\"@context\":\"https://schema.org\",\"@type\":\"Article\"}</script>"
            "</head><body></body></html>"
        )
        return artifact

    sent = {"called": False}
    monkeypatch.setattr(pipeline, "write_release_artifact", fake_write_release_artifact)
    monkeypatch.setattr(
        pipeline,
        "send_release_ready",
        lambda *args, **kwargs: sent.__setitem__("called", True),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    assert sent["called"] is True
    run_dir = next((project_root / "logs" / "runs").iterdir())
    assert (run_dir / "run-events.jsonl").exists()
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["events_file"].endswith("run-events.jsonl")


def test_lock_file_prevents_concurrent_run(project_root, monkeypatch) -> None:
    (project_root / ".content-engine.lock").mkdir()
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 0


def test_calendar_exhausted_exits_clean(project_root, monkeypatch) -> None:
    calendar_path = project_root / "content" / "calendar.yaml"
    payload = json.loads(json.dumps({"topics": []}))
    import yaml

    calendar_path.write_text(yaml.safe_dump(payload))
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 0


def test_provider_unavailable_sends_notification(project_root, monkeypatch) -> None:
    called = {"error": False}
    monkeypatch.setattr(
        pipeline,
        "enrich",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pipeline.ProviderUnavailableError("down")
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "send_error",
        lambda *args, **kwargs: called.__setitem__("error", True),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 1
    assert called["error"] is True


def test_manual_topic_uses_existing_calendar_entry(project_root, monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--topic",
            "The Power of Individual-Level Engagement in Folloze",
            "--type",
            "blog",
        ],
    )
    args = pipeline._build_parser().parse_args()
    topic = pipeline._select_topic(args, dry_run=False)
    assert topic.slug == "the-power-of-individual-level-engagement-in-folloze"
    assert topic.keywords[0] == "individual-level engagement"
