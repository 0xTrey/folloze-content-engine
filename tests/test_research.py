from __future__ import annotations

import re

import responses

import research
from config import Config
from content_calendar import Topic
from exceptions import ProviderUnavailableError
from research import BRAVE_ENDPOINT, PERPLEXITY_ENDPOINT, enrich


@responses.activate
def test_research_success(project_root, monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "perplexity")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")

    responses.add(
        responses.GET,
        BRAVE_ENDPOINT,
        json={"web": {"results": [{"title": "A", "url": "https://a.test", "description": "desc"}]}},
        status=200,
    )
    responses.add(
        responses.POST,
        PERPLEXITY_ENDPOINT,
        json={"choices": [{"message": {"content": "Perplexity summary"}}]},
        status=200,
    )
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json={"candidates": [{"content": {"parts": [{"text": "Research brief"}]}}]},
        status=200,
    )

    topic = Topic(
        "Folloze vs Mutiny",
        "comparison",
        "folloze-vs-mutiny",
        ["folloze vs mutiny"],
        5,
        "pending",
    )
    context = enrich(topic, Config.load())

    assert context.gemini_brief == "Research brief"
    assert context.degraded is False
    assert context.brave_results[0]["title"] == "A"


@responses.activate
def test_research_degrades_when_search_providers_fail(project_root, monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "perplexity")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")

    responses.add(responses.GET, BRAVE_ENDPOINT, status=500)
    responses.add(responses.POST, PERPLEXITY_ENDPOINT, status=500)
    responses.add(
        responses.POST,
        re.compile(r"https://generativelanguage\.googleapis\.com/.*"),
        json={"candidates": [{"content": {"parts": [{"text": "Brand-only brief"}]}}]},
        status=200,
    )

    topic = Topic(
        "Folloze vs Mutiny",
        "comparison",
        "folloze-vs-mutiny",
        ["folloze vs mutiny"],
        5,
        "pending",
    )
    context = enrich(topic, Config.load())

    assert context.degraded is True
    assert "Brave degraded" in context.degradation_reason
    assert context.gemini_brief == "Brand-only brief"


def test_research_uses_gateway_fallback_when_gemini_fails(project_root, monkeypatch) -> None:
    topic = Topic(
        "Folloze vs Mutiny",
        "comparison",
        "folloze-vs-mutiny",
        ["folloze vs mutiny"],
        5,
        "pending",
    )
    monkeypatch.setattr(
        research,
        "_call_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProviderUnavailableError("Gemini research call failed: Gemini rate limit")
        ),
    )
    seen_profiles: list[str] = []

    def fake_gateway(prompt: str, profile: str) -> str:
        seen_profiles.append(profile)
        if profile == "openai":
            return "Gateway research brief"
        raise AssertionError(f"Unexpected profile {profile}")

    monkeypatch.setattr(research, "_call_gateway", fake_gateway)
    context = enrich(topic, Config.load())
    assert context.gemini_brief == "Gateway research brief"
    assert seen_profiles == ["workhorse", "openai"]
