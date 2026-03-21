from __future__ import annotations

import re

import responses

from config import Config
from content_calendar import Topic
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
