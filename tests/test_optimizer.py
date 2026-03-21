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
