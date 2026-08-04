from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

import pipeline
import yaml
from artifacts import ReleaseArtifact
from content_calendar import Topic
from exceptions import ValidationError
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
            '<script type=\'application/ld+json\'>{"@context":"https://schema.org","@type":"Article"}</script>'
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
    assert sent["called"] is False
    run_dir = next((project_root / "logs" / "runs").iterdir())
    assert (run_dir / "run-events.jsonl").exists()
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["events_file"].endswith("run-events.jsonl")


def test_manual_release_mode_sends_release_ready_notification(project_root, monkeypatch) -> None:
    config_path = project_root / "config.yaml"
    raw_config = yaml.safe_load(config_path.read_text())
    raw_config["delivery"]["release_mode"] = "manual"
    config_path.write_text(yaml.safe_dump(raw_config, sort_keys=False))

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
    monkeypatch.setattr(
        pipeline,
        "write_release_artifact",
        lambda *args, **kwargs: artifact,
    )

    sent = {"called": False}
    monkeypatch.setattr(
        pipeline,
        "send_release_ready",
        lambda *args, **kwargs: sent.__setitem__("called", True),
    )
    monkeypatch.setattr(pipeline, "check_preview_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    assert sent["called"] is True


def test_lock_file_prevents_concurrent_run(project_root, monkeypatch) -> None:
    (project_root / ".content-engine.lock").mkdir()
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 0


def test_stale_lock_is_removed_and_reacquired(project_root, monkeypatch) -> None:
    lock_dir = project_root / ".content-engine.lock"
    lock_dir.mkdir()
    stale_time = 1_700_000_000
    os.utime(lock_dir, (stale_time, stale_time))

    monkeypatch.setattr(pipeline, "_content_engine_process_active", lambda exclude_pids=None: False)
    monkeypatch.setattr(pipeline, "_pid_is_running", lambda pid: False)

    pipeline._acquire_lock()

    assert lock_dir.exists()
    metadata = json.loads((lock_dir / "owner.json").read_text())
    assert metadata["pid"] == os.getpid()

    pipeline._release_lock()
    assert not lock_dir.exists()


def test_calendar_exhausted_exits_clean(project_root, monkeypatch) -> None:
    calendar_path = project_root / "content" / "calendar.yaml"
    payload = json.loads(json.dumps({"topics": []}))
    import yaml

    calendar_path.write_text(yaml.safe_dump(payload))
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 0


def test_provider_unavailable_sends_notification(project_root, monkeypatch) -> None:
    expected_topic = pipeline._select_topic(pipeline._build_parser().parse_args([]), dry_run=False)
    called = {"error": False}
    monkeypatch.setattr(
        pipeline,
        "enrich",
        lambda *args, **kwargs: (_ for _ in ()).throw(pipeline.ProviderUnavailableError("down")),
    )
    monkeypatch.setattr(
        pipeline,
        "send_error",
        lambda *args, **kwargs: called.__setitem__("error", True),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 1
    assert called["error"] is True
    payload = yaml.safe_load((project_root / "content" / "calendar.yaml").read_text())
    topic = next(item for item in payload["topics"] if item["slug"] == expected_topic.slug)
    assert topic["status"] == "pending"
    assert topic["retry_count"] == 1
    assert topic["last_error"] == "down"


def test_select_topic_rejects_calendar_topic_with_forbidden_primary_keyword(project_root) -> None:
    calendar_path = project_root / "content" / "calendar.yaml"
    payload = yaml.safe_load(calendar_path.read_text())
    payload["topics"] = [
        {
            "title": "What Is a B2B Buyer Experience Platform?",
            "content_type": "glossary",
            "slug": "what-is-a-b2b-buyer-experience-platform",
            "keywords": ["buyer experience platform", "abx platform"],
            "priority": 5,
            "status": "pending",
            "notes": "Legacy category term without search-intent-only framing.",
        }
    ]
    calendar_path.write_text(yaml.safe_dump(payload, sort_keys=False))

    args = pipeline._build_parser().parse_args([])
    try:
        pipeline._select_topic(args, dry_run=False)
        raise AssertionError("Expected ValidationError for forbidden primary keyword")
    except ValidationError as exc:
        assert "forbidden" in str(exc).lower()
        assert "search-intent only" in str(exc).lower()


def test_quality_gate_triggers_single_repair_pass(project_root, monkeypatch) -> None:
    topic = _topic()
    research = ResearchContext(topic, [], "summary", "brief", "brand")
    initial = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Short intro.</p>",
        [{"heading": "Deep Dive", "html": "<p>Body</p>"}],
        200,
        "comparison",
        "folloze vs mutiny",
    )
    repaired = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Folloze vs mutiny is a comparison for B2B teams.</p>"
        "<h2>Frequently Asked Questions</h2><p>Answer.</p>",
        [],
        1100,
        "comparison",
        "folloze vs mutiny",
    )
    optimized = OptimizedContent(
        repaired,
        repaired.body_html,
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
        word_count=1100,
        canonical_url="https://insights.folloze.com/insights/folloze-vs-mutiny",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )

    monkeypatch.setattr(pipeline, "enrich", lambda *args, **kwargs: research)
    monkeypatch.setattr(pipeline, "generate", lambda *args, **kwargs: initial)
    repair_calls = {"count": 0, "failures": None}

    def fake_regenerate(*args, **kwargs):
        repair_calls["count"] += 1
        repair_calls["failures"] = args[4]
        return repaired

    monkeypatch.setattr(pipeline, "regenerate_for_quality", fake_regenerate)
    monkeypatch.setattr(
        pipeline,
        "optimize",
        lambda content, *_: OptimizedContent(
            content,
            content.body_html,
            '{"@context":"https://schema.org","@type":"Article"}',
            "Article",
        ),
    )
    gate_results = iter(
        [
            QualityResult(False, 50, [], ["Missing definition block", "Missing FAQ section"]),
            QualityResult(True, 82, [], []),
        ]
    )
    monkeypatch.setattr(pipeline, "gate", lambda *args, **kwargs: next(gate_results))

    def fake_write_release_artifact(*args, **kwargs):
        run_dir = args[4]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "release-artifact.json").write_text(json.dumps(asdict(artifact), indent=2))
        (run_dir / "rendered-preview.html").write_text(
            "<html><head><title>Title</title><meta name='description' content='Desc'>"
            "<link rel='canonical' href='https://example.com'>"
            '<script type=\'application/ld+json\'>{"@context":"https://schema.org","@type":"Article"}</script>'
            "</head><body></body></html>"
        )
        return artifact

    monkeypatch.setattr(pipeline, "write_release_artifact", fake_write_release_artifact)
    monkeypatch.setattr(pipeline, "send_release_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    assert repair_calls["count"] == 1
    assert repair_calls["failures"] == ["Missing definition block", "Missing FAQ section"]


def test_quality_gate_uses_multiple_repair_passes_when_needed(project_root, monkeypatch) -> None:
    topic = _topic()
    research = ResearchContext(topic, [], "summary", "brief", "brand")
    initial = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Short intro.</p>",
        [],
        200,
        "comparison",
        "folloze vs mutiny",
    )
    repaired = GeneratedContent(
        topic,
        "Title",
        "Desc",
        "<p>Folloze vs mutiny is a comparison for B2B teams.</p>"
        "<h2>Frequently Asked Questions</h2><p>Answer.</p>",
        [],
        1100,
        "comparison",
        "folloze vs mutiny",
    )
    optimized = OptimizedContent(
        repaired,
        repaired.body_html,
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
        word_count=1100,
        canonical_url="https://insights.folloze.com/insights/folloze-vs-mutiny",
        source_run_id="run-1",
        status="release_ready",
        review_notes=[],
    )

    monkeypatch.setattr(pipeline, "enrich", lambda *args, **kwargs: research)
    monkeypatch.setattr(pipeline, "generate", lambda *args, **kwargs: initial)
    repair_calls: list[list[str]] = []

    def fake_regenerate(*args, **kwargs):
        repair_calls.append(args[4])
        return repaired

    monkeypatch.setattr(pipeline, "regenerate_for_quality", fake_regenerate)
    monkeypatch.setattr(
        pipeline,
        "optimize",
        lambda content, *_: OptimizedContent(
            content,
            content.body_html,
            '{"@context":"https://schema.org","@type":"Article"}',
            "Article",
        ),
    )
    gate_results = iter(
        [
            QualityResult(False, 50, [], ["Missing definition block"]),
            QualityResult(False, 68, [], ["Missing approved proof point"]),
            QualityResult(True, 82, [], []),
        ]
    )
    monkeypatch.setattr(pipeline, "gate", lambda *args, **kwargs: next(gate_results))

    def fake_write_release_artifact(*args, **kwargs):
        run_dir = args[4]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "release-artifact.json").write_text(json.dumps(asdict(artifact), indent=2))
        (run_dir / "rendered-preview.html").write_text(
            "<html><head><title>Title</title><meta name='description' content='Desc'>"
            "<link rel='canonical' href='https://example.com'>"
            '<script type=\'application/ld+json\'>{"@context":"https://schema.org","@type":"Article"}</script>'
            "</head><body></body></html>"
        )
        return artifact

    monkeypatch.setattr(pipeline, "write_release_artifact", fake_write_release_artifact)
    monkeypatch.setattr(pipeline, "send_release_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    assert repair_calls == [["Missing definition block"], ["Missing approved proof point"]]


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


def test_stage_for_error_maps_research_provider_failures() -> None:
    error = pipeline.ProviderUnavailableError("Gemini research call failed: Gemini rate limit")
    assert pipeline._stage_for_error(error) == "enrich_research"


def test_stage_for_error_maps_generation_validation_failures() -> None:
    error = pipeline.ValidationError("Gemini payload missing 'sections'")
    assert pipeline._stage_for_error(error) == "generate_content"


def _stub_successful_pipeline(monkeypatch) -> None:
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
        "<p>Folloze is a platform.</p>",
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
    monkeypatch.setattr(pipeline, "write_release_artifact", lambda *args, **kwargs: artifact)
    monkeypatch.setattr(pipeline, "check_preview_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "send_release_ready", lambda *args, **kwargs: None)


def test_pre_publish_flag_true_calls_and_writes_json(project_root, monkeypatch) -> None:
    _stub_successful_pipeline(monkeypatch)
    calls = {"count": 0}

    def fake_pre_publish(topic):
        calls["count"] += 1
        return pipeline.PrePublishLLMResult(
            provider="perplexity",
            keyword=topic.keywords[0],
            query="query",
            response_excerpt="excerpt",
            folloze_mentioned=False,
            competitors_mentioned=["mutiny"],
            source_urls=["https://example.com"],
            recommendation="gap",
            checked_at="2026-05-24T00:00:00+00:00",
        )

    monkeypatch.setattr(pipeline, "run_pre_publish_llm_test", fake_pre_publish)
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    assert calls["count"] == 1
    run_dir = next((project_root / "logs" / "runs").iterdir())
    payload = json.loads((run_dir / "pre-publish-llm-test.json").read_text())
    assert payload["recommendation"] == "gap"
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["pre_publish_llm_test"].endswith("pre-publish-llm-test.json")


def test_pre_publish_flag_false_skips_call(project_root, monkeypatch) -> None:
    config_path = project_root / "config.yaml"
    raw_config = yaml.safe_load(config_path.read_text())
    raw_config["pipeline"]["pre_publish_llm_test"] = False
    config_path.write_text(yaml.safe_dump(raw_config, sort_keys=False))
    _stub_successful_pipeline(monkeypatch)

    def fail_pre_publish(topic):
        raise AssertionError("pre-publish should be skipped")

    monkeypatch.setattr(pipeline, "run_pre_publish_llm_test", fail_pre_publish)
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])

    assert pipeline.main() == 0
    run_dir = next((project_root / "logs" / "runs").iterdir())
    assert not (run_dir / "pre-publish-llm-test.json").exists()
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["pre_publish_llm_test"] is None
