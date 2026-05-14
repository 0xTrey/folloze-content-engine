from __future__ import annotations
from __future__ import annotations
from config import Config
from content_calendar import Topic
from generator import GeneratedContent
from optimizer import optimize


def test_optimize_adds_table_head_and_json_ld(project_root) -> None:
    topic = Topic(
        "Folloze vs Mutiny",
        "comparison",
        "folloze-vs-mutiny",
        ["folloze vs mutiny"],
        5,
        "pending",
    )
    generated = GeneratedContent(
        topic=topic,
        title="Folloze vs Mutiny",
        meta_description="desc",
        body_html="<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table><h3>FAQ</h3><p>Answer.</p>",
        sections=[],
        word_count=1000,
        content_type="comparison",
        primary_keyword="folloze vs mutiny",
    )
    optimized = optimize(generated, Config.load())
    assert "<thead>" in optimized.body_html
    assert "\"@context\": \"https://schema.org\"" in optimized.json_ld


def test_optimize_blog_uses_blogposting_schema_graph(project_root) -> None:
    topic = Topic(
        "Why AI Marketing Orchestration Needs Governance",
        "blog",
        "why-ai-marketing-orchestration-needs-governance",
        ["ai marketing orchestration", "marketing governance"],
        3,
        "pending",
    )
    generated = GeneratedContent(
        topic=topic,
        title="Why AI Marketing Orchestration Needs Governance",
        meta_description="Why governance matters for AI marketing orchestration.",
        body_html="<p>AI marketing orchestration is the discipline of coordinating campaigns, signals, and approvals.</p>",
        sections=[],
        word_count=900,
        content_type="blog",
        primary_keyword="ai marketing orchestration",
    )
    optimized = optimize(generated, Config.load())
    assert '"@graph"' in optimized.json_ld
    assert '"@type": "BlogPosting"' in optimized.json_ld
    assert '"publisher"' in optimized.json_ld
    assert '"isPartOf"' in optimized.json_ld
