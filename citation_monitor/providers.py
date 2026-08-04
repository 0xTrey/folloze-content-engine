from __future__ import annotations

import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from llm_gateway import LLMGateway

from citation_monitor.contracts import (
    NativeCitation,
    build_evidence_payload,
    extract_perplexity_citations,
    load_configured_owned_domains,
)
from runtime_secrets import get_secret, hydrate_provider_env

TRACKER_COLLECTOR_ROOT = Path("/Users/treyharnden/Projects/api-tracker/collector")
if TRACKER_COLLECTOR_ROOT.exists() and str(TRACKER_COLLECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACKER_COLLECTOR_ROOT))

try:
    from api_tracker.telemetry import append_error_event, append_event, build_perplexity_usage
except Exception:

    def append_event(event: dict[str, Any] | None) -> None:
        return None

    def append_error_event(**kwargs: Any) -> None:
        return None

    def build_perplexity_usage(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        return None

LOGGER = logging.getLogger("content_engine.citation_monitor")

FOLLOZE_RE = re.compile(r"\bfolloze\b", re.IGNORECASE)
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
PERPLEXITY_MODEL = "sonar"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
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
    native_citations: list[dict[str, Any]] = field(default_factory=list)
    raw_evidence: dict[str, Any] = field(default_factory=dict)
    evidence_checksum: str | None = None
    grounded_response: bool = False


def query_perplexity(prompt_text: str) -> ProviderResult:
    api_key = get_secret("PERPLEXITY_API_KEY")
    if not api_key:
        raise AuthError("PERPLEXITY_API_KEY not available")

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            request_payload = {
                "model": PERPLEXITY_MODEL,
                "messages": [{"role": "user", "content": prompt_text}],
            }
            response = requests.post(
                PERPLEXITY_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
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
                _track_perplexity_error(
                    message="Perplexity rate limited citation monitor request",
                    error_type="rate_limit",
                    status="limited",
                )
                time.sleep(wait)
                continue
            if response.status_code == 401:
                _track_perplexity_error(
                    message="Perplexity API key invalid or expired",
                    error_type="auth",
                    status="broken",
                )
                raise AuthError("Perplexity API key invalid or expired")
            response.raise_for_status()

            try:
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderError(f"Perplexity returned malformed JSON: {exc}") from exc
            native_citations = extract_perplexity_citations(
                payload,
                owned_domains=load_configured_owned_domains(),
            )
            _track_perplexity_usage(payload)
            return _analyze_response(
                "perplexity",
                text,
                native_citations=native_citations,
            )

        except AuthError:
            raise
        except ProviderError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE**attempt)

    raise ProviderError(f"Perplexity failed after {MAX_RETRIES + 1} attempts: {last_error}")


def _track_perplexity_usage(payload: dict[str, Any]) -> None:
    try:
        event = build_perplexity_usage(
            payload,
            source="content_engine_citation_monitor",
        )
        append_event(event)
        if event:
            LOGGER.info(
                "Tracked Perplexity citation-monitor usage model=%s unit=%s used_increment=%s",
                event.get("model"),
                event.get("unit"),
                event.get("used_increment"),
            )
        else:
            LOGGER.info(
                "Perplexity citation-monitor call completed without usage payload model=%s",
                payload.get("model", PERPLEXITY_MODEL),
            )
    except Exception:
        LOGGER.exception("Failed to track Perplexity citation-monitor usage")


def _track_perplexity_error(*, message: str, error_type: str, status: str) -> None:
    try:
        append_error_event(
            provider_slug="perplexity",
            bucket_key="perplexity",
            source="content_engine_citation_monitor",
            message=message,
            status=status,
            model=PERPLEXITY_MODEL,
            error_type=error_type,
        )
    except Exception:
        LOGGER.exception("Failed to track Perplexity citation-monitor error")


def query_gateway_profile(prompt_text: str, *, profile: str, provider_name: str) -> ProviderResult:
    hydrate_provider_env()
    try:
        gw = LLMGateway(profile=profile)
        text = gw.chat(
            [{"role": "user", "content": prompt_text}],
            max_tokens=4096,
            temperature=0.3,
            timeout=REQUEST_TIMEOUT,
        )
        return _analyze_response(provider_name, text)
    except Exception as exc:
        if _is_auth_exception(exc):
            raise AuthError(f"{provider_name} gateway auth failed: {exc}") from exc
        raise ProviderError(f"{provider_name} gateway failed: {exc}") from exc


def query_openai_gateway(prompt_text: str) -> ProviderResult:
    return query_gateway_profile(prompt_text, profile="openai", provider_name="openai")


def query_claude(prompt_text: str) -> ProviderResult:
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise AuthError("ANTHROPIC_API_KEY not available")

    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4096,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt_text}],
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 401:
            raise AuthError("Anthropic API key invalid or expired")
        response.raise_for_status()
        payload = response.json()
        parts = payload.get("content") or []
        text = "\n".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
        if not text:
            raise ProviderError("Anthropic returned no text content")
        return _analyze_response("claude", text)
    except AuthError:
        raise
    except ProviderError:
        raise
    except requests.RequestException as exc:
        raise ProviderError(f"Anthropic failed: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise ProviderError(f"Anthropic returned malformed JSON: {exc}") from exc


def query_claude_gateway(prompt_text: str) -> ProviderResult:
    return query_claude(prompt_text)


def query_gemini_gateway(prompt_text: str) -> ProviderResult:
    return query_gateway_profile(prompt_text, profile="gemini", provider_name="gemini")


PROVIDERS = {
    "perplexity": query_perplexity,
    "openai": query_openai_gateway,
    "claude": query_claude_gateway,
    "gemini": query_gemini_gateway,
}


def _analyze_response(
    provider: str,
    text: str,
    *,
    native_citations: list[NativeCitation] | None = None,
) -> ProviderResult:
    folloze_mentioned = bool(FOLLOZE_RE.search(text))
    citations = native_citations or []
    owned_citations = [citation for citation in citations if citation.owned]
    folloze_cited = bool(owned_citations)
    citation_position = owned_citations[0].position if owned_citations else None
    source_urls = [citation.url for citation in citations]
    raw_evidence, evidence_checksum = build_evidence_payload(
        provider=provider,
        citations=citations,
    )
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
        native_citations=[citation.to_dict() for citation in citations],
        raw_evidence=raw_evidence,
        evidence_checksum=evidence_checksum,
        grounded_response=bool(citations),
    )


def _is_auth_exception(exc: Exception) -> bool:
    if isinstance(exc, KeyError):
        return True
    message = str(exc).lower()
    auth_markers = (
        "api key",
        "apikey",
        "unauthorized",
        "401",
        "403",
        "forbidden",
        "invalid key",
        "missing key",
        "permission denied",
    )
    return any(marker in message for marker in auth_markers)


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
