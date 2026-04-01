from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from llm_gateway import LLMGateway

from citation_monitor.storage import get_cached_variants, upsert_variant
from runtime_secrets import hydrate_provider_env

LOGGER = logging.getLogger("content_engine.citation_monitor")

PROMPT_LIBRARY_PATH = Path("prompts/prompt_library.json")
VARIANT_CACHE_DAYS = 7

# Deterministic fallback templates when LLM is unavailable.
VARIANT_TEMPLATES = [
    "What is the best {keyword} for B2B companies?",
    "Which {keyword} tools do enterprise teams use?",
    "How does {keyword} work for marketing teams?",
    "{keyword} comparison for B2B",
    "Top {keyword} platforms in 2026",
]


def load_prompt_library(path: Path = PROMPT_LIBRARY_PATH) -> list[dict]:
    if not path.exists():
        LOGGER.warning("Prompt library not found at %s", path)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("prompts", [])


def get_variants_for_prompt(
    conn: sqlite3.Connection,
    prompt: dict,
    max_variants: int = 5,
) -> list[str]:
    prompt_id = prompt["prompt_id"]
    canonical = prompt["canonical_text"]

    # Always include the canonical prompt
    variants = [canonical]

    # Check cache
    cached = get_cached_variants(conn, prompt_id, max_age_days=VARIANT_CACHE_DAYS)
    if cached:
        for v in cached:
            if v not in variants and len(variants) < max_variants:
                variants.append(v)
        if len(variants) >= max_variants:
            return variants[:max_variants]

    # Generate via LLM
    target_count = max_variants - len(variants)
    if target_count > 0:
        generated = _generate_variants_llm(canonical, prompt, target_count)
        generation_method = "llm"
        if not generated:
            generated = _generate_variants_template(prompt, target_count)
            generation_method = "template"
        for v in generated:
            if v not in variants:
                variants.append(v)
                upsert_variant(conn, prompt_id, v, generation_method)

    return variants[:max_variants]


def _generate_variants_llm(
    canonical: str,
    prompt: dict,
    count: int,
) -> list[str]:
    try:
        hydrate_provider_env()
        gw = LLMGateway(profile="workhorse")
        system_msg = (
            "Generate variant phrasings of a search query. "
            "Rules: preserve the original intent, do not broaden scope, "
            "cover buyer-voice questions, comparison phrasing, "
            "pain-point framing, and tool discovery angles. "
            f"Return exactly {count} variants, one per line. "
            "No numbering, no quotes, no explanation."
        )
        user_msg = (
            f"Original query: {canonical}\n"
            f"Intent type: {prompt.get('intent_type', 'general')}\n"
            f"Keywords: {', '.join(prompt.get('keywords', []))}\n"
            f"Generate {count} variant phrasings:"
        )
        response = gw.chat(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=512,
            temperature=0.7,
            timeout=30,
        )
        lines = [
            line.strip()
            for line in response.strip().split("\n")
            if line.strip() and line.strip() != canonical
        ]
        return lines[:count]
    except Exception as exc:
        LOGGER.warning("LLM variant generation failed: %s", exc)
        return []


def _generate_variants_template(prompt: dict, count: int) -> list[str]:
    keywords = prompt.get("keywords", [])
    keyword = keywords[0] if keywords else prompt.get("canonical_text", "topic")
    variants = [template.format(keyword=keyword) for template in VARIANT_TEMPLATES]
    return variants[:count]
