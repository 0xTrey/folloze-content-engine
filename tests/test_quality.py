from __future__ import annotations

from config import Config
from content_calendar import Topic
from evidence import build_evidence_report
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
    assert result.score <= 100
    assert result.aeo_score <= 100
    assert result.geo_score <= 100


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


def test_gate_includes_seo_warnings_without_blocking_pass(project_root) -> None:
    generated = GeneratedContent(
        topic=Topic(
            "AI Marketing Orchestration Governance",
            "blog",
            "ai-marketing-orchestration-governance",
            ["marketing orchestration"],
            5,
            "pending",
        ),
        title="AI Marketing Orchestration Governance Guide",
        meta_description=(
            "Marketing orchestration guide for enterprise teams that need stronger approvals, "
            "governance, and execution discipline across campaigns."
        ),
        body_html=(
            '<div class="tldr"><p>TL;DR: Marketing orchestration improves campaign control by 98%.</p></div>'
            "<p>Teams struggle with slow approvals before using marketing orchestration to simplify campaign execution. "
            "According to Gartner (2024), 98% matters. According to Forrester, $6.3M matters.</p>"
            "<h2>What is marketing orchestration?</h2><p>Marketing orchestration is the discipline of coordinating campaign execution, approvals, and signals.</p>"
            "<h2>FAQ</h2><p>Questions about marketing orchestration.</p><p>Folloze proof $6.3M.</p>"
            '<a href="https://www.folloze.com/product">Product</a>'
            '<a href="https://www.folloze.com/demo">Demo</a>'
            "<p>Updated March 2026</p>"
            '<meta name="author" content="Trey Harnden">'
        ),
        sections=[],
        word_count=1000,
        content_type="blog",
        primary_keyword="marketing orchestration",
    )
    optimized = OptimizedContent(
        generated=generated,
        body_html=generated.body_html,
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        schema_type="Article",
    )
    result = gate(optimized, Config.load(), "brand")
    assert result.seo_warnings is not None
    assert any("meta description" in warning.lower() for warning in result.seo_warnings)


def test_gate_blocks_unsupported_material_claim(project_root) -> None:
    generated = GeneratedContent(
        topic=Topic("Evidence", "guide", "evidence", ["evidence"], 5, "pending"),
        title="Evidence",
        meta_description="Evidence guidance for B2B campaign teams.",
        body_html="<p>Teams improved conversion by 25%.</p>",
        sections=[],
        word_count=1000,
        content_type="guide",
        primary_keyword="evidence",
    )
    optimized = OptimizedContent(
        generated=generated,
        body_html=generated.body_html,
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        schema_type="Article",
    )
    result = gate(
        optimized,
        Config.load(),
        "brand",
        evidence_report=build_evidence_report(generated.body_html),
    )
    assert result.passed is False
    assert result.evidence_status == "unsupported"
    assert result.score <= 100
    assert any("Unsupported material claim" in failure for failure in result.failures)


def test_gate_blocks_unapproved_weak_source(project_root) -> None:
    html = (
        '<p>Teams improved conversion by 25% in the '
        '<a href="https://unknown.example/report">benchmark report</a>.</p>'
    )
    generated = GeneratedContent(
        topic=Topic("Evidence", "guide", "evidence", ["evidence"], 5, "pending"),
        title="Evidence",
        meta_description="Evidence guidance for B2B campaign teams.",
        body_html=html,
        sections=[],
        word_count=1000,
        content_type="guide",
        primary_keyword="evidence",
    )
    optimized = OptimizedContent(
        generated=generated,
        body_html=generated.body_html,
        json_ld='{"@context":"https://schema.org","@type":"Article"}',
        schema_type="Article",
    )
    result = gate(
        optimized,
        Config.load(),
        "brand",
        evidence_report=build_evidence_report(html),
    )
    assert result.evidence_status == "weak_support"
    assert result.passed is False
    assert any("approved research pack" in failure for failure in result.failures)
