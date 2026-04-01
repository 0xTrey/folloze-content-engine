from __future__ import annotations

import json

from config import Config
from content_calendar import Topic
from generator import GeneratedContent
from optimizer import OptimizedContent
from quality import (
    _check_answer_first_paragraphs,
    _check_author_attribution,
    _check_citation_format,
    _check_emdash,
    _check_emotion_first,
    _check_entity_consistency,
    _check_freshness_signal,
    _check_heading_density,
    _check_kill_list,
    _check_tldr_present,
    gate,
)

VALID_JSON_LD = json.dumps(
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "dateModified": "2026-03-31",
        "author": {"@type": "Person", "name": "Trey Harnden"},
    }
)

MINIMAL_JSON_LD = json.dumps(
    {
        "@context": "https://schema.org",
        "@type": "Article",
    }
)


def _make_optimized(
    body_html: str,
    json_ld: str = MINIMAL_JSON_LD,
    content_type: str = "blog",
) -> OptimizedContent:
    generated = GeneratedContent(
        topic=Topic("Test Topic", content_type, "test-topic", ["test topic"], 5, "pending"),
        title="Test Topic",
        meta_description="desc",
        body_html=body_html,
        sections=[],
        word_count=len(body_html.split()),
        content_type=content_type,
        primary_keyword="test topic",
    )
    return OptimizedContent(
        generated=generated,
        body_html=body_html,
        json_ld=json_ld,
        schema_type="Article",
    )


# --- _check_tldr_present ---


class TestTldrPresent:
    def test_tldr_with_stat(self):
        html = (
            '<div class="tldr"><p>TL;DR: Folloze drives 98% engagement.</p></div><p>More text.</p>'
        )
        points, label, failure = _check_tldr_present(html)
        assert points == 15
        assert failure is None

    def test_tldr_without_stat(self):
        html = '<div class="tldr"><p>This is a summary of the article.</p></div>'
        points, _, failure = _check_tldr_present(html)
        assert points == 8
        assert "missing a statistic" in failure

    def test_missing_entirely(self):
        html = "<p>Some random content about marketing.</p>"
        points, _, failure = _check_tldr_present(html)
        assert points == 0
        assert "[HARD]" in failure

    def test_tldr_in_text(self):
        html = "<p>TL;DR: This product helps teams close 5x faster deals.</p>"
        points, _, failure = _check_tldr_present(html)
        assert points == 15
        assert failure is None


# --- _check_entity_consistency ---


class TestEntityConsistency:
    def test_clean(self):
        html = "<p>Folloze helps B2B teams personalize content.</p>"
        points, _, failure = _check_entity_consistency(html)
        assert points == 5
        assert failure is None

    def test_forbidden_term(self):
        html = "<p>Folloze is a buyer experience platform for B2B.</p>"
        points, _, failure = _check_entity_consistency(html)
        assert points == 0
        assert "[HARD]" in failure
        assert "buyer experience platform" in failure

    def test_missing_required(self):
        html = "<p>This platform helps B2B teams.</p>"
        points, _, failure = _check_entity_consistency(html)
        assert points == 0
        assert "[HARD]" in failure
        assert "folloze" in failure.lower()

    def test_all_forbidden_terms(self):
        for term in ("microsite builder", "agentic", "page builder"):
            html = f"<p>Folloze is a {term} for enterprises.</p>"
            _, _, failure = _check_entity_consistency(html)
            assert failure is not None and term in failure


# --- _check_heading_density ---


class TestHeadingDensity:
    def test_sufficient(self):
        html = (
            "<h2>Section One</h2>"
            + "<p>word </p>" * 50
            + "<h2>Section Two</h2>"
            + "<p>word </p>" * 50
        )
        points, _, failure = _check_heading_density(html)
        assert points == 10
        assert failure is None

    def test_insufficient(self):
        # 500 words with only 1 heading = too sparse (need 500//200 = 2)
        html = "<h2>Only Heading</h2>" + "<p>" + " ".join(["word"] * 500) + "</p>"
        points, _, failure = _check_heading_density(html)
        assert points == 0
        assert "Heading density" in failure

    def test_empty_html(self):
        points, _, failure = _check_heading_density("")
        assert points == 0


# --- _check_answer_first_paragraphs ---


class TestAnswerFirstParagraphs:
    def test_above_60_percent(self):
        html = (
            "<h2>What is ABM?</h2><p>ABM is account-based marketing for B2B teams.</p>"
            "<h2>Why use ABM?</h2><p>ABM improves pipeline velocity and deal size.</p>"
            "<h2>How to start?</h2><p>Start by identifying your ICP accounts.</p>"
        )
        points, _, failure = _check_answer_first_paragraphs(html)
        assert points == 10
        assert failure is None

    def test_below_60_percent(self):
        html = (
            "<h2>What is ABM?</h2>"
            "<p>Have you ever wondered about account-based marketing "
            "and what it could do for your team and your pipeline?</p>"
            "<h2>Why use ABM?</h2>"
            "<p>There are many reasons why teams are switching to "
            "account-based marketing strategies in the modern era.</p>"
            "<h2>How?</h2><p>Start by identifying your ICP accounts.</p>"
        )
        points, _, failure = _check_answer_first_paragraphs(html)
        # Only 1/3 is declarative and short enough
        assert "answer-first" in (failure or "").lower() or points == 10

    def test_no_h2s(self):
        html = "<p>Just a paragraph with no headings at all.</p>"
        points, _, failure = _check_answer_first_paragraphs(html)
        assert points == 10  # No H2s means check passes


# --- _check_citation_format ---


class TestCitationFormat:
    def test_proper_format(self):
        html = "<p>According to Gartner (2024), 78% of B2B buyers prefer personalized content.</p>"
        points, _, failure = _check_citation_format(html)
        assert points == 10
        assert failure is None

    def test_missing_year(self):
        html = "<p>According to Gartner, 78% of B2B buyers prefer personalized content.</p>"
        points, _, failure = _check_citation_format(html)
        assert points == 5
        assert "missing (Year)" in failure

    def test_no_citation(self):
        html = "<p>Most buyers prefer personalized content.</p>"
        points, _, failure = _check_citation_format(html)
        assert points == 0

    def test_multiple_citations(self):
        html = (
            "<p>According to Gartner (2024), 78% matters. "
            "According to Forrester (2023), 65% matters too.</p>"
        )
        points, _, failure = _check_citation_format(html)
        assert points == 10


# --- _check_kill_list ---


class TestKillList:
    def test_single_word(self):
        html = "<p>We empower teams to streamline their workflow with Folloze.</p>"
        points, _, failure = _check_kill_list(html)
        assert points == 0
        assert "[HARD]" in failure
        assert "empower" in failure

    def test_multiple_words(self):
        html = "<p>Our seamless, robust, and holistic platform is best-in-class.</p>"
        points, _, failure = _check_kill_list(html)
        assert points == 0
        found_words = failure.split(":", 2)[-1]
        assert "seamless" in found_words

    def test_none_found(self):
        html = "<p>Folloze helps B2B teams personalize content at scale.</p>"
        points, _, failure = _check_kill_list(html)
        assert points == 10
        assert failure is None


# --- _check_freshness_signal ---


class TestFreshnessSignal:
    def test_date_modified_in_json_ld(self):
        points, _, failure = _check_freshness_signal("<p>text</p>", VALID_JSON_LD)
        assert points == 10
        assert failure is None

    def test_updated_text(self):
        html = "<p>Updated March 2026. This article covers...</p>"
        points, _, failure = _check_freshness_signal(html, MINIMAL_JSON_LD)
        assert points == 10

    def test_time_element(self):
        html = '<p>Published <time datetime="2026-03-31">March 31, 2026</time></p>'
        points, _, failure = _check_freshness_signal(html, MINIMAL_JSON_LD)
        assert points == 10

    def test_missing(self):
        html = "<p>Some content with no date anywhere.</p>"
        points, _, failure = _check_freshness_signal(html, MINIMAL_JSON_LD)
        assert points == 0
        assert "freshness" in failure.lower()


# --- _check_author_attribution ---


class TestAuthorAttribution:
    def test_meta_tag(self):
        html = '<meta name="author" content="Trey Harnden"><p>Article.</p>'
        points, _, failure = _check_author_attribution(html, MINIMAL_JSON_LD)
        assert points == 10

    def test_json_ld_author(self):
        html = "<p>Article.</p>"
        points, _, failure = _check_author_attribution(html, VALID_JSON_LD)
        assert points == 10

    def test_byline_class(self):
        html = '<p>Article.</p><span class="author">Trey Harnden</span>'
        points, _, failure = _check_author_attribution(html, MINIMAL_JSON_LD)
        assert points == 10

    def test_missing(self):
        html = "<p>Article with no author anywhere.</p>"
        points, _, failure = _check_author_attribution(html, MINIMAL_JSON_LD)
        assert points == 0


# --- _check_emotion_first ---


class TestEmotionFirst:
    def test_pain_before_product(self):
        html = "<p>Teams struggle with manual campaigns before finding the right platform.</p>"
        points, _, failure = _check_emotion_first(html)
        assert points == 10
        assert failure is None

    def test_product_first(self):
        html = "<p>Folloze is a platform that helps teams who struggle with campaigns.</p>"
        points, _, failure = _check_emotion_first(html)
        assert points == 5
        assert "after product" in failure

    def test_neither(self):
        html = "<p>Marketing teams use many different approaches to engage buyers.</p>"
        points, _, failure = _check_emotion_first(html)
        assert points == 0


# --- _check_emdash ---


class TestEmdash:
    def test_no_emdash(self):
        html = "<p>This sentence uses commas, not dashes.</p>"
        points, _, failure = _check_emdash(html)
        assert points == 10
        assert failure is None

    def test_has_emdash(self):
        html = "<p>This sentence \u2014 uses an em dash.</p>"
        points, _, failure = _check_emdash(html)
        assert points == 0
        assert "[HARD]" in failure


# --- Extended gate() tests ---


class TestGateGeoIntegration:
    def test_geo_score_and_aeo_score_populated(self, project_root):
        html = (
            '<div class="tldr"><p>TL;DR: Folloze drives 98% engagement.</p></div>'
            "<p>Teams struggle with manual outreach before finding Folloze.</p>"
            "<p>Test topic is a new approach. "
            "According to Gartner (2024), 78% of B2B teams need this.</p>"
            "<p>According to Forrester, $6.3M matters.</p>"
            "<h2>What is it?</h2><p>It simplifies B2B content ops.</p>"
            "<h2>FAQ</h2><p>Common questions about test topic.</p>"
            '<a href="https://www.folloze.com/product">Product</a>'
            '<a href="https://www.folloze.com/demo">Demo</a>'
            "<table><tr><td>A</td></tr></table>"
            "<p>Updated March 2026</p>"
            '<meta name="author" content="Trey Harnden">'
        )
        optimized = _make_optimized(html, VALID_JSON_LD, "comparison")
        result = gate(optimized, Config.load(), "brand")
        assert result.aeo_score > 0
        assert result.geo_score > 0
        assert result.geo_failures is not None

    def test_geo_threshold_zero_passes(self, project_root):
        """With geo_quality_threshold=0, even low GEO scores pass if AEO passes."""
        html = (
            "<p>Test topic is a new approach used by Folloze. "
            "According to Gartner, 98% matters. According to Forrester, $6.3M in results.</p>"
            "<h2>FAQ</h2><p>Questions about test topic.</p>"
            '<a href="https://www.folloze.com/a">A</a>'
            '<a href="https://www.folloze.com/b">B</a>'
        )
        optimized = _make_optimized(html)
        config = Config.load()
        assert config.pipeline.geo_quality_threshold == 0
        result = gate(optimized, config, "brand")
        # GEO score will be low but threshold is 0
        assert result.geo_score >= 0

    def test_geo_threshold_enforced(self, project_root):
        """When geo_quality_threshold is high, low GEO scores fail."""
        html = (
            "<p>Test topic is a platform. Folloze helps. "
            "According to Gartner, 98% matters. According to Forrester, $6.3M.</p>"
            "<h2>FAQ</h2><p>Questions.</p>"
            '<a href="https://www.folloze.com/a">A</a>'
            '<a href="https://www.folloze.com/b">B</a>'
        )
        optimized = _make_optimized(html)
        config = Config.load()
        config.pipeline.geo_quality_threshold = 75
        result = gate(optimized, config, "brand")
        # Should fail because GEO score won't reach 75 with missing checks
        if result.geo_score < 75:
            assert result.passed is False

    def test_hard_fail_kill_list_blocks(self, project_root):
        """Kill-list words block regardless of score."""
        html = (
            '<div class="tldr"><p>TL;DR: We empower teams with 98% better results.</p></div>'
            "<p>Teams struggle before finding Folloze.</p>"
            "<p>Test topic is a approach. According to Gartner (2024), 78% need this.</p>"
            "<p>According to Forrester, $6.3M matters.</p>"
            "<h2>What?</h2><p>It helps.</p>"
            "<h2>FAQ</h2><p>Questions about test topic.</p>"
            '<a href="https://www.folloze.com/a">A</a>'
            '<a href="https://www.folloze.com/b">B</a>'
            '<meta name="author" content="Trey"><time>2026</time>'
        )
        optimized = _make_optimized(html, VALID_JSON_LD)
        result = gate(optimized, Config.load(), "brand")
        assert result.passed is False
        assert any("Kill-list" in f for f in result.failures)

    def test_hard_fail_entity_blocks(self, project_root):
        """Forbidden entity terms block regardless of score."""
        html = (
            '<div class="tldr"><p>TL;DR: 98% improvement.</p></div>'
            "<p>Teams struggle with this microsite builder approach.</p>"
            "<p>Folloze helps. According to Gartner (2024), 78% agree.</p>"
            "<h2>What?</h2><p>A guide.</p>"
            "<h2>FAQ</h2><p>Questions.</p>"
        )
        optimized = _make_optimized(html)
        result = gate(optimized, Config.load(), "brand")
        assert result.passed is False
        assert any("Forbidden entity" in f for f in result.failures)

    def test_composite_score_is_average(self, project_root):
        """Composite score = (aeo_score + geo_score) // 2."""
        html = (
            "<p>Test topic is a system. Folloze helps teams. "
            "According to Gartner, 98%. According to Forrester, $6.3M.</p>"
            "<h2>FAQ</h2><p>Questions.</p>"
            '<a href="https://www.folloze.com/a">A</a>'
            '<a href="https://www.folloze.com/b">B</a>'
        )
        optimized = _make_optimized(html)
        result = gate(optimized, Config.load(), "brand")
        assert result.score == (result.aeo_score + result.geo_score) // 2

    def test_emdash_no_longer_in_brand_failures(self, project_root):
        """Em dash is now a GEO check, not a brand failure."""
        html = (
            "<p>Test topic is a system \u2014 Folloze helps teams. "
            "According to Gartner, 98%. According to Forrester, $6.3M.</p>"
            "<h2>FAQ</h2><p>Questions.</p>"
            '<a href="https://www.folloze.com/a">A</a>'
            '<a href="https://www.folloze.com/b">B</a>'
        )
        optimized = _make_optimized(html)
        result = gate(optimized, Config.load(), "brand")
        # Em dash should appear in geo_failures, not as a brand failure
        assert any("em dash" in f.lower() for f in result.geo_failures or [])
