from __future__ import annotations

import json
import re

import pytest
import responses

from config import Config
from content_calendar import Topic
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


def _gemini_payload(body_html: str) -> dict:
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
                                    "sections": [{"heading": "Intro", "html": "<p>Intro</p>"}],
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
            "candidates": [
                {"content": {"parts": [{"text": "I cannot assist with that request."}]}}
            ]
        },
        status=200,
    )
    topic = Topic("Hello", "guide", "hello", ["hello"], 5, "pending")
    with pytest.raises(Exception):
        generate(topic, _research_context(topic), config)
