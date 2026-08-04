from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

NATIVE_SEMANTICS_VERSION = "provider-native-v2"
LEGACY_SEMANTICS_VERSION = "legacy-mention-proxy-v1"


@dataclass(frozen=True, slots=True)
class NativeCitation:
    """Provider-native source metadata captured without inferring links from prose."""

    url: str
    title: str | None = None
    snippet: str | None = None
    position: int | None = None
    owned: bool = False
    provider_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def load_configured_owned_domains(config_path: Path = Path("config.yaml")) -> set[str]:
    """Load controlled citation domains from config, falling back to site.origin.

    An optional top-level ``citation_monitor.owned_domains`` list can extend the
    registry. The configured site's apex and www host are treated as aliases.
    """

    raw: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded

    candidates: list[str] = []
    origin = (raw.get("site") or {}).get("origin")
    if isinstance(origin, str):
        candidates.append(origin)

    configured = (raw.get("citation_monitor") or {}).get("owned_domains", [])
    if isinstance(configured, list):
        candidates.extend(str(value) for value in configured)

    domains: set[str] = set()
    for candidate in candidates:
        hostname = _hostname(candidate)
        if not hostname:
            continue
        domains.add(hostname)
        if hostname.startswith("www."):
            domains.add(hostname[4:])
        else:
            domains.add(f"www.{hostname}")
    return domains


def is_owned_url(url: str, owned_domains: set[str]) -> bool:
    hostname = _hostname(url)
    return bool(hostname and hostname in owned_domains)


def extract_perplexity_citations(
    payload: dict[str, Any],
    *,
    owned_domains: set[str],
) -> list[NativeCitation]:
    """Parse Perplexity's native ``search_results``/``citations`` fields.

    Text URLs are intentionally ignored. Exact provider URLs are retained.
    """

    citations: list[NativeCitation] = []
    seen: set[str] = set()

    search_results = payload.get("search_results") or []
    if isinstance(search_results, list):
        for item in search_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            exact_url = url.strip()
            if exact_url in seen:
                continue
            seen.add(exact_url)
            citations.append(
                NativeCitation(
                    url=exact_url,
                    title=_optional_text(item.get("title")),
                    snippet=_optional_text(item.get("snippet")),
                    position=len(citations) + 1,
                    owned=is_owned_url(exact_url, owned_domains),
                    provider_payload=_json_safe_dict(item),
                )
            )

    citation_urls = payload.get("citations") or []
    if isinstance(citation_urls, list):
        for value in citation_urls:
            if isinstance(value, dict):
                url = value.get("url")
                raw = value
            else:
                url = value
                raw = {"url": value}
            if not isinstance(url, str) or not url.strip():
                continue
            exact_url = url.strip()
            if exact_url in seen:
                continue
            seen.add(exact_url)
            citations.append(
                NativeCitation(
                    url=exact_url,
                    position=len(citations) + 1,
                    owned=is_owned_url(exact_url, owned_domains),
                    provider_payload=_json_safe_dict(raw),
                )
            )

    return citations


def build_evidence_payload(
    *,
    provider: str,
    citations: list[NativeCitation],
) -> tuple[dict[str, Any], str]:
    evidence = {
        "provider": provider,
        "native_citations": [citation.to_dict() for citation in citations],
    }
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return evidence, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hostname(value: str) -> str | None:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname.lower().rstrip(".") if parsed.hostname else None


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _json_safe_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return json.loads(json.dumps(value, default=str))
