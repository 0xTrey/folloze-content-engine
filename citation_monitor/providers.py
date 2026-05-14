from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests
from llm_gateway import LLMGateway

from runtime_secrets import get_secret, hydrate_provider_env

LOGGER = logging.getLogger("content_engine.citation_monitor")

FOLLOZE_RE = re.compile(r"\bfolloze\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
COMPETITOR_PATTERNS = {
    "mutiny": re.compile(r"\bmutiny\b", re.IGNORECASE),
    "userled": re.compile(r"\buserled\b", re.IGNORECASE),
    "pathfactory": re.compile(r"\bpathfactory\b", re.IGNORECASE),
    "prismic": re.compile(r"\bprismic\b", re.IGNORECASE),
    "demandbase": re.compile(r"\bdemandbase\b", re.IGNORECASE),
    "terminus": re.compile(r"\bterminus\b", re.IGNORECASE),
    "6sense": re.compile(r"\b6sense\b", re.IGNORECASE),
}

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT = 30
INTER_REQUEST_SLEEP = 1.0
MAX_RETRIES = 2
BACKOFF_BASE = 2.0


@dataclass(slots=True)
class ProviderResult:
    provider: str
    response_text: str
    folloze_mentioned: bool
    folloze_cited: bool
    folloze_citation_position: int | None
    competitors_mentioned: list[str]
    confidence_flag: str
    sentiment_label: str
    source_urls: list[str]


def query_perplexity(prompt_text: str) -> ProviderResult:
    api_key = get_secret("PERPLEXITY_API_KEY")
    if not api_key:
        raise AuthError("PERPLEXITY_API_KEY not available")

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(
                PERPLEXITY_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar-pro",
                    "messages": [{"role": "user", "content": prompt_text}],
                },
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 429:
                wait = BACKOFF_BASE ** (attempt + 1)
                LOGGER.warning(
                    "Perplexity 429, backing off %.1fs (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    MAX_RETRIES + 1,
                )
                time.sleep(wait)
                continue
            if response.status_code == 401:
                raise AuthError("Perplexity API key invalid or expired")
            response.raise_for_status()

            try:
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderError(f"Perplexity returned malformed JSON: {exc}") from exc
            return _analyze_response("perplexity", text)

        except AuthError:
            raise
        except ProviderError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE**attempt)

    raise ProviderError(f"Perplexity failed after {MAX_RETRIES + 1} attempts: {last_error}")


def query_openai_gateway(prompt_text: str) -> ProviderResult:
    hydrate_provider_env()
    try:
        gw = LLMGateway(profile="openai")
        text = gw.chat(
            [{"role": "user", "content": prompt_text}],
            max_tokens=4096,
            temperature=0.3,
            timeout=REQUEST_TIMEOUT,
        )
        return _analyze_response("openai", text)
    except Exception as exc:
        raise ProviderError(f"OpenAI gateway failed: {exc}") from exc


PROVIDERS = {
    "perplexity": query_perplexity,
    "openai": query_openai_gateway,
}


def _analyze_response(provider: str, text: str) -> ProviderResult:
    folloze_mentioned = bool(FOLLOZE_RE.search(text))

    citation_position = None
    if folloze_mentioned:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            if FOLLOZE_RE.search(para):
                citation_position = i + 1
                break

    source_urls = list(dict.fromkeys(URL_RE.findall(text)))
    folloze_cited = folloze_mentioned and (citation_position is not None or bool(source_urls))
    competitors = [name for name, pattern in COMPETITOR_PATTERNS.items() if pattern.search(text)]

    confidence = "normal"
    lowered = text.lower()
    if len(text) < 50:
        confidence = "low"
    elif any(phrase in lowered for phrase in ("i'm not sure", "i don't have", "unable to")):
        confidence = "low"

    return ProviderResult(
        provider=provider,
        response_text=text,
        folloze_mentioned=folloze_mentioned,
        folloze_cited=folloze_cited,
        folloze_citation_position=citation_position,
        competitors_mentioned=competitors,
        confidence_flag=confidence,
        sentiment_label=_classify_sentiment(lowered, folloze_mentioned),
        source_urls=source_urls,
    )


def _classify_sentiment(lowered_text: str, folloze_mentioned: bool) -> str:
    if not folloze_mentioned:
        return "neutral"

    negative_markers = (
        "poor fit",
        "not recommended",
        "weak",
        "limited",
        "expensive",
        "difficult",
        "lacks",
        "not ideal",
        "negative",
        "bad",
    )
    positive_markers = (
        "best",
        "strong",
        "recommended",
        "leading",
        "excellent",
        "good fit",
        "great fit",
        "top choice",
        "well suited",
        "ideal",
    )

    if any(marker in lowered_text for marker in negative_markers):
        return "negative"
    if any(marker in lowered_text for marker in positive_markers):
        return "positive"
    return "neutral"


class ProviderError(Exception):
    pass


class AuthError(ProviderError):
    pass
