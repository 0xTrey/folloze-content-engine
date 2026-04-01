from __future__ import annotations

from config import Config
from content_calendar import Topic
from generator import GeneratedContent
from optimizer import OptimizedContent
from quality import gate


def test_gate_passes_with_score_above_threshold(project_root) -> None:
    generated = GeneratedContent(
        topic=Topic(
            "Folloze vs Mutiny",
            "comparison",
            "folloze-vs-mutiny",
            ["folloze vs mutiny"],
            5,
            "pending",
        ),
        title="Folloze vs Mutiny",
        meta_description="desc",
        body_html=(
            '<div class="tldr">'
            "<p>TL;DR: Folloze drives 98% better pipeline.</p></div>"
            "<p>Teams struggle with slow campaigns before finding Folloze. "
            "Folloze is a platform. According to Gartner (2024), 98% matters. "
            "According to Forrester, $6.3M matters.</p>"
            "<table><thead><tr><th>A</th></tr></thead><tr><td>B</td></tr></table>"
            "<h2>FAQ</h2><p>Questions about folloze vs mutiny.</p><p>Folloze proof $6.3M.</p>"
            '<a href="https://www.folloze.com/product">Product</a>'
            '<a href="https://www.folloze.com/demo">Demo</a>'
            "<p>Updated March 2026</p>"
            '<meta name="author" content="Trey Harnden">'
        ),
        sections=[],
        word_count=1000,
        content_type="comparison",
        primary_keyword="folloze vs mutiny",
    )
    optimized = OptimizedContent(
        generated=generated,
        body_html=generated.body_html,
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        schema_type="Article",
    )
    result = gate(optimized, Config.load(), "brand")
    assert result.passed is True
    assert result.score >= 70


def test_gate_fails_banned_term_and_missing_proof(project_root) -> None:
    generated = GeneratedContent(
        topic=Topic("Hello", "guide", "hello", ["hello"], 5, "pending"),
        title="Hello",
        meta_description="desc",
        body_html="<p>Hello is a revolutionary system. FAQ.</p>",
        sections=[],
        word_count=1000,
        content_type="guide",
        primary_keyword="hello",
    )
    optimized = OptimizedContent(
        generated=generated,
        body_html=generated.body_html,
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        schema_type="Article",
    )
    result = gate(optimized, Config.load(), "brand")
    assert result.passed is False
    assert any("Banned term" in failure for failure in result.failures)
