from __future__ import annotations

import json
import os
import re

import pytest
import responses

import generator
from config import Config
from content_calendar import Topic
from exceptions import ProviderUnavailableError
from generator import generate
from research import ResearchContext


def _research_context(topic: Topic) -> ResearchContext:
    return ResearchContext(
        topic=topic,
        brave_results=[],
        perplexity_summary="summary",
        gemini_brief="brief",
        brand_context="Folloze proof $6.3M",
    )


def _gemini_payload(body_html: str, sections: list[dict[str, str]] | None = None) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "title": "Example Title",
                                    "meta_description": "Example description",
                                    "body_html": body_html,
                                    "sections": sections
                                    or [{"heading": "Intro", "html": "<p>Intro</p>"}],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }


@responses.activate
def test_generate_all_five_content_types(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    config = Config.load()
    for content_type in ("comparison", "guide", "faq", "glossary", "blog"):
        responses.reset()
        body = "<p>" + "word " * (config.content.min_words_by_type[content_type] + 20) + "</p>"
        responses.add(
            responses.POST,
            re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
            json=_gemini_payload(body),
            status=200,
        )
        topic = Topic("Hello", content_type, "hello", ["hello"], 5, "pending")
        content = generate(topic, _research_context(topic), config)
        assert content.content_type == content_type
        assert content.word_count >= config.content.min_words_by_type[content_type]


@responses.activate
def test_generate_retries_on_short_content(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    config = Config.load()
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json=_gemini_payload("<p>short content</p>"),
        status=200,
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json=_gemini_payload("<p>" + "word " * 1200 + "</p>"),
        status=200,
    )
    topic = Topic("Hello", "guide", "hello", ["hello"], 5, "pending")
    content = generate(topic, _research_context(topic), config)
    assert content.word_count >= config.content.min_words_by_type["guide"]


@responses.activate
def test_generate_retries_on_invalid_json(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    config = Config.load()
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json={"candidates": [{"content": {"parts": [{"text": '{"title": "Bad"'}]}}]},
        status=200,
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json=_gemini_payload("<p>" + "word " * 600 + "</p>"),
        status=200,
    )
    topic = Topic("Hello", "blog", "hello", ["hello"], 5, "pending")
    content = generate(topic, _research_context(topic), config)
    assert content.word_count >= config.content.min_words_by_type["blog"]


@responses.activate
def test_generate_raises_on_empty_response(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    monkeypatch.setattr(
        generator,
        "_call_gateway",
        lambda *args, **kwargs: (_ for _ in ()).throw(ProviderUnavailableError("down")),
    )
    config = Config.load()
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json={"candidates": [{"content": {"parts": [{"text": ""}]}}]},
        status=200,
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        status=500,
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        status=500,
    )
    topic = Topic("Hello", "guide", "hello", ["hello"], 5, "pending")
    with pytest.raises(Exception):
        generate(topic, _research_context(topic), config)


@responses.activate
def test_generate_raises_on_refusal(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    config = Config.load()
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json={
            "candidates": [{"content": {"parts": [{"text": "I cannot assist with that request."}]}}]
        },
        status=200,
    )
    topic = Topic("Hello", "guide", "hello", ["hello"], 5, "pending")
    with pytest.raises(Exception):
        generate(topic, _research_context(topic), config)


@responses.activate
def test_generate_merges_substantive_sections_into_body_html(project_root, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    config = Config.load()
    section_html = (
        "<p>According to Gartner, 98% of B2B buyers expect relevant digital "
        "experiences.</p>"
        "<p>According to Forrester, revenue teams need measurable orchestration "
        "to prove pipeline impact.</p>"
        '<p>Folloze supports that model through <a href="https://www.folloze.com/'
        'platform/overview">platform orchestration</a> and '
        '<a href="https://www.folloze.com/folloze-ai">AI agents</a>, which '
        "helped Conga generate $6.3M in attributed pipeline.</p>"
        "<h2>Frequently Asked Questions</h2>"
        "<h3>What is the difference?</h3><p>Folloze orchestrates campaigns "
        "beyond the website.</p>" + "<p>" + "word " * 950 + "</p>"
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json=_gemini_payload(
            "<p>Short intro only.</p>",
            [{"heading": "Deep Dive", "html": section_html}],
        ),
        status=200,
    )
    topic = Topic("Hello", "comparison", "hello", ["hello"], 5, "pending")
    content = generate(topic, _research_context(topic), config)
    assert "<h2>Deep Dive</h2>" in content.body_html
    assert "Frequently Asked Questions" in content.body_html
    assert 'href="https://www.folloze.com/platform/overview"' in content.body_html
    assert content.word_count >= config.content.min_words_by_type["comparison"]


def test_generate_tries_multiple_gateway_profiles_after_gemini_failure(
    project_root, monkeypatch
) -> None:
    config = Config.load()
    monkeypatch.setattr(
        generator,
        "_call_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(ProviderUnavailableError("gemini down")),
    )
    seen_profiles: list[str] = []

    def fake_gateway(prompt: str, profile: str) -> str:
        seen_profiles.append(profile)
        if profile == "workhorse":
            raise ProviderUnavailableError("workhorse down")
        if profile == "openai":
            raise ProviderUnavailableError("openai down")
        if profile == "strategic":
            return json.dumps(
                {
                    "title": "Example Title",
                    "meta_description": "Example description",
                    "body_html": "<p>" + "word " * 950 + "</p>",
                    "sections": [],
                }
            )
        raise AssertionError(f"Unexpected profile {profile}")

    monkeypatch.setattr(generator, "_call_gateway", fake_gateway)
    topic = Topic("Hello", "comparison", "hello", ["hello"], 5, "pending")
    content = generate(topic, _research_context(topic), config)
    assert content.word_count >= config.content.min_words_by_type["comparison"]
    assert seen_profiles == ["workhorse", "openai", "strategic"]


def test_call_gateway_hydrates_provider_env_before_constructing_gateway(monkeypatch) -> None:
    monkeypatch.delenv("AI_OPENAI_KEY", raising=False)

    def fake_hydrate() -> None:
        os.environ["AI_OPENAI_KEY"] = "from-keychain"

    class FakeGateway:
        def __init__(self, profile: str):
            assert profile == "openai"
            assert os.environ["AI_OPENAI_KEY"] == "from-keychain"

        def chat(self, messages, **kwargs) -> str:
            return "ok"

    monkeypatch.setattr(generator, "hydrate_provider_env", fake_hydrate)
    monkeypatch.setattr(generator, "LLMGateway", FakeGateway)

    assert generator._call_gateway("prompt", "openai") == "ok"


def test_quality_repair_instructions_cover_brand_and_style_failures() -> None:
    topic = Topic(
        "How to Activate 6sense and Folloze Together",
        "guide",
        "how-to-activate-6sense-and-folloze-together",
        ["6sense and folloze"],
        4,
        "pending",
    )
    instructions = generator._quality_repair_instructions(
        topic,
        [
            "Missing approved proof point",
            "Contains em dash",
            "Paragraphs are too long on average",
            "Primary keyword density 3.5% exceeds 3% (28 occurrences)",
            "Banned term used: buyer experience platform",
        ],
        700,
    )
    assert "$6.3M" in instructions
    assert "478 MQLs" in instructions
    assert "Use commas or periods instead of em dashes." in instructions
    assert "Keep paragraphs to four sentences or fewer on average." in instructions
    assert "cap exact-match repetition below 3% of words" in instructions
    assert "buyer experience platform" in instructions
    assert "Checklist: Missing approved proof point" in instructions


def test_blog_prompt_contract_emphasizes_tldr_faq_quotability_and_caveats() -> None:
    topic = Topic(
        "Why AI Marketing Orchestration Needs Governance",
        "blog",
        "why-ai-marketing-orchestration-needs-governance",
        ["ai marketing orchestration", "marketing governance"],
        3,
        "pending",
        notes="Point-of-view post with practical guidance.",
    )
    prompt = generator._render_prompt(topic, _research_context(topic))

    assert "Target 700 to 1000 words" in prompt
    assert "TL;DR or Key Takeaways block" in prompt
    assert "3 to 5 FAQ pairs" in prompt
    assert "quote-worthy declarative lines" in prompt
    assert 'trade-off, caveat, or "where this breaks down"' in prompt
    assert "concrete workflow, example, or scenario" in prompt
    assert "both searchable and citable" in prompt
    assert "first 100 words clearly relevant" in prompt
    assert "40 and 60 words" in prompt
    assert "mirror natural search/query phrasing" in prompt


def test_glossary_prompt_contract_handles_tldr_and_forbidden_search_intent_terms() -> None:
    topic = Topic(
        "What Is a B2B Buyer Experience Platform?",
        "glossary",
        "what-is-a-b2b-buyer-experience-platform",
        ["abx platform", "ai orchestration platform for b2b"],
        4,
        "pending",
        notes=(
            "Treat the title as search-intent framing only. Use approved language in the body "
            "and never repeat forbidden entity terms."
        ),
    )
    prompt = generator._render_prompt(topic, _research_context(topic))

    assert "Start body_html with a short TL;DR or Key Takeaways block" in prompt
    assert "search-intent input only" in prompt
    assert "Do not repeat forbidden phrases anywhere in body_html" in prompt
    assert "If the exact phrase contains forbidden entity language, use it 0 times in body_html" in prompt
    assert "Updated [Month] [Year]" in prompt or "<time>" in prompt
    assert "meta name=\"author\"" in prompt or "byline" in prompt
    assert "According to [Source] (Year)" in prompt or "According to [Source] (YYYY)" in prompt
    assert "pain point or emotional territory before mentioning Folloze" in prompt
    assert "avoid kill-list words" in prompt or "Do not use kill-list marketing words" in prompt


def test_guide_prompt_contract_handles_emotion_first_answer_first_and_forbidden_comparisons() -> None:
    topic = Topic(
        "Outreach + Folloze for Personalized Sales Experiences",
        "guide",
        "outreach-plus-folloze-for-personalized-sales-experiences",
        ["outreach digital sales room", "outreach personalized landing pages"],
        4,
        "pending",
        notes="Emotional territory: pipeline anxiety. Integration page for sales-facing personalization.",
    )
    prompt = generator._render_prompt(topic, _research_context(topic))

    assert "Start body_html with a short TL;DR or Key Takeaways block" in prompt
    assert "buyer pain or emotional territory" in prompt
    assert "before mentioning Folloze, product, platform, solution, or feature language" in prompt
    assert "very first sentence immediately under the H2 must be a short declarative answer-first sentence under 40 words" in prompt
    assert "FAQ must appear inside body_html" in prompt
    assert "Put a short overview paragraph directly under that FAQ H2" in prompt
    assert "According to [Source] (Year)" in prompt
    assert "concrete workflow, example, or scenario" in prompt
    assert "quote-worthy declarative lines" in prompt
    assert "Never use \"microsite builder,\" \"buyer experience platform,\" \"agentic,\" or \"page builder,\" even in comparisons, negations, or FAQ questions" in prompt
