from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from config import Config
from content_calendar import Topic
from exceptions import EmptyResponseError, ProviderUnavailableError, RefusalError, ValidationError
from research import ResearchContext
from runtime_secrets import get_secret

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
REFUSAL_RE = re.compile(r"\b(i can(?:not|'t)|i am unable|i won't|cannot assist)\b", re.IGNORECASE)


@dataclass(slots=True)
class GeneratedContent:
    topic: Topic
    title: str
    meta_description: str
    body_html: str
    sections: list[dict[str, str]]
    word_count: int
    content_type: str
    primary_keyword: str


def generate(topic: Topic, research: ResearchContext, config: Config) -> GeneratedContent:
    prompt = _render_prompt(topic, research)
    minimum_words = config.content.min_words_by_type[topic.content_type]
    prompt_attempts = [
        prompt,
        f"{prompt}\n\nExpand the body_html to exceed the minimum word count.",
    ]
    last_error: Exception | None = None

    for attempt_prompt in prompt_attempts:
        try:
            text = _call_gemini(
                attempt_prompt,
                config.llm.generation_model,
                config.pipeline.max_retries_llm,
            )
            if REFUSAL_RE.search(text):
                raise RefusalError("Gemini refused the content request")

            payload = _extract_json_payload(text)
            content = GeneratedContent(
                topic=topic,
                title=payload["title"].strip(),
                meta_description=payload["meta_description"].strip(),
                body_html=payload["body_html"].strip(),
                sections=payload["sections"],
                word_count=_count_words(payload["body_html"]),
                content_type=topic.content_type,
                primary_keyword=topic.keywords[0],
            )
            if content.word_count < minimum_words:
                raise ValidationError(
                    f"Generated content too short: {content.word_count} < {minimum_words}"
                )
            return content
        except (EmptyResponseError, ValidationError, ProviderUnavailableError, RefusalError) as exc:
            last_error = exc
            if isinstance(exc, RefusalError):
                raise

    if isinstance(last_error, ValidationError):
        raise last_error
    if isinstance(last_error, EmptyResponseError | ProviderUnavailableError):
        raise ProviderUnavailableError(str(last_error))
    raise ProviderUnavailableError(f"Generation failed: {last_error}")


def _render_prompt(topic: Topic, research: ResearchContext) -> str:
    environment = Environment(
        loader=FileSystemLoader("content/templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(f"{topic.content_type}.md")
    rendered = template.render(topic=topic, research=research)
    return (
        f"{rendered}\n\n"
        "STRICT JSON RULES:\n"
        "- Return exactly one valid JSON object.\n"
        "- Do not wrap the response in markdown fences.\n"
        "- Escape all double quotes inside HTML attributes and strings.\n"
        "- Do not include comments, trailing commas, or prose outside the JSON object.\n"
    )


def _call_gemini(prompt: str, model: str, max_retries: int) -> str:
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ProviderUnavailableError("GEMINI_API_KEY not set")

    endpoint = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            response = requests.post(
                endpoint,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=45,
            )
            if response.status_code == 429:
                raise ProviderUnavailableError("Gemini rate limit")
            response.raise_for_status()
            text = _extract_gemini_text(response.json())
            if not text.strip():
                raise EmptyResponseError("Gemini returned empty content")
            return text
        except (requests.RequestException, EmptyResponseError, ProviderUnavailableError) as exc:
            last_error = exc
    raise ProviderUnavailableError(f"Gemini request failed: {last_error}")


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "\n".join(part.get("text", "") for part in parts)


def _extract_json_payload(text: str) -> dict[str, Any]:
    normalized = text.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.partition("\n")[2]
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start == -1 or end == -1:
        raise EmptyResponseError("Gemini response did not contain a JSON object")
    try:
        payload = json.loads(normalized[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Gemini returned invalid JSON: {exc}") from exc
    for field in ("title", "meta_description", "body_html", "sections"):
        if field not in payload:
            raise ValidationError(f"Gemini payload missing '{field}'")
    return payload


def _count_words(html: str) -> int:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return len([word for word in text.split() if word.strip()])
