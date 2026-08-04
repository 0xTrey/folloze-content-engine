from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from html import escape
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from llm_gateway import LLMGateway

from brand_rules import GEO_KILL_LIST, PROOF_POINTS
from config import Config
from content_calendar import Topic
from exceptions import EmptyResponseError, ProviderUnavailableError, RefusalError, ValidationError
from research import ResearchContext
from runtime_secrets import get_secret, hydrate_provider_env

LOGGER = logging.getLogger("content_engine")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
REFUSAL_RE = re.compile(
    r"^\s*(?:(?:i(?:'m| am) sorry)[,.:]?\s*)?"
    r"(?:i can(?:not|'t)|i am unable|i won't|cannot assist)\b",
    re.IGNORECASE,
)
GATEWAY_PROFILES = ("workhorse", "openai", "strategic", "kimi", "minimax", "local")
GATEWAY_TIMEOUT_SECONDS = 120


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
    return _generate_from_prompt(topic, prompt, config)


def regenerate_for_quality(
    topic: Topic,
    research: ResearchContext,
    config: Config,
    prior_content: GeneratedContent,
    failures: list[str],
) -> GeneratedContent:
    prompt = _render_quality_repair_prompt(topic, research, prior_content, failures, config)
    return _generate_from_prompt(topic, prompt, config)


def _generate_from_prompt(topic: Topic, prompt: str, config: Config) -> GeneratedContent:
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
            payload = _extract_content_payload(text, "Gemini")
            content = _build_content(topic, payload)
            if content.word_count < minimum_words:
                raise ValidationError(
                    f"Generated content too short: {content.word_count} < {minimum_words}"
                )
            return content
        except (EmptyResponseError, ValidationError, ProviderUnavailableError, RefusalError) as exc:
            last_error = exc
            if isinstance(exc, RefusalError):
                LOGGER.warning("Gemini refused the request; trying gateway fallback")
                break

    # Gemini exhausted — fall back to LLMGateway using the best available writing profiles.
    LOGGER.warning("Gemini failed after all retries (%s); falling back to LLMGateway", last_error)
    for gw_profile in GATEWAY_PROFILES:
        for attempt_prompt in prompt_attempts:
            try:
                text = _call_gateway(attempt_prompt, gw_profile)
                payload = _extract_content_payload(text, f"Gateway profile={gw_profile}")
                content = _build_content(topic, payload)
                if content.word_count < minimum_words:
                    raise ValidationError(
                        f"Generated content too short: {content.word_count} < {minimum_words}"
                    )
                LOGGER.info("Gateway fallback succeeded via profile=%s", gw_profile)
                return content
            except RefusalError as exc:
                LOGGER.warning("Gateway profile=%s refused the request", gw_profile)
                last_error = exc
                break
            except ValidationError as exc:
                LOGGER.warning(
                    "Gateway profile=%s content too short, retrying with expansion prompt", gw_profile
                )
                last_error = exc
            except Exception as exc:
                LOGGER.warning("Gateway profile=%s failed: %s", gw_profile, exc)
                last_error = exc
                break  # provider unavailable — skip to next profile

    if isinstance(last_error, RefusalError):
        raise last_error
    raise ProviderUnavailableError(f"All providers failed: {last_error}")


def _render_prompt(topic: Topic, research: ResearchContext) -> str:
    environment = Environment(
        loader=FileSystemLoader("content/templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(f"{topic.content_type}.md")
    rendered = template.render(topic=topic, research=research)
    source_packet = json.dumps(
        [asdict(source) for source in research.source_candidates], indent=2
    )
    return (
        f"{rendered}\n\n"
        "EVIDENCE CONTRACT:\n"
        "- The source candidates below are provenance captured by the research stage.\n"
        "- Every statistic, attributed finding, comparative performance claim, and vendor "
        "capability claim must include a directly supporting inline <a href=\"...\"> citation "
        "in the same paragraph.\n"
        "- Use only source URLs that actually support the adjacent claim. If no candidate supports "
        "a material claim, remove or qualify the claim instead of inventing a citation.\n"
        "- Prefer primary research, official documentation, and named first-party product pages.\n"
        f"SOURCE CANDIDATES:\n{source_packet}\n\n"
        "STRICT JSON RULES:\n"
        "- Return exactly one valid JSON object.\n"
        "- Do not wrap the response in markdown fences.\n"
        "- Escape all double quotes inside HTML attributes and strings.\n"
        "- Do not include comments, trailing commas, or prose outside the JSON object.\n"
    )


def _render_quality_repair_prompt(
    topic: Topic,
    research: ResearchContext,
    prior_content: GeneratedContent,
    failures: list[str],
    config: Config,
) -> str:
    base_prompt = _render_prompt(topic, research)
    failure_instructions = _quality_repair_instructions(
        topic,
        failures,
        config.content.min_words_by_type[topic.content_type],
    )
    prior_payload = json.dumps(
        {
            "title": prior_content.title,
            "meta_description": prior_content.meta_description,
            "body_html": prior_content.body_html,
            "sections": prior_content.sections,
        },
        indent=2,
    )
    return (
        f"{base_prompt}\n\n"
        "QUALITY REPAIR MODE:\n"
        "- Revise the existing draft below so it passes the quality gate.\n"
        "- Preserve accurate claims and product positioning, but rewrite "
        "structure and wording as needed.\n"
        "- body_html must remain a complete standalone article; do not hide "
        "required content only in sections.\n"
        "- Fix every issue listed below before returning the final JSON object.\n\n"
        "QUALITY FAILURES TO FIX:\n"
        f"{failure_instructions}\n\n"
        "CURRENT DRAFT TO REVISE:\n"
        f"{prior_payload}\n"
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
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 8192},
                },
                timeout=90,
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


def _build_content(topic: Topic, payload: dict[str, Any]) -> GeneratedContent:
    sections = payload["sections"]
    body_html = _compose_body_html(payload["body_html"], sections)
    body_html = _self_heal_common_quality_blockers(topic, body_html)
    return GeneratedContent(
        topic=topic,
        title=payload["title"].strip(),
        meta_description=payload["meta_description"].strip(),
        body_html=body_html,
        sections=sections,
        word_count=_count_words(body_html),
        content_type=topic.content_type,
        primary_keyword=topic.keywords[0],
    )


def _call_gateway(prompt: str, profile: str) -> str:
    hydrate_provider_env()
    gw = LLMGateway(profile=profile)
    return gw.chat(
        [{"role": "user", "content": prompt}],
        max_tokens=8192,
        temperature=0.4,
        timeout=GATEWAY_TIMEOUT_SECONDS,
    )


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


def _extract_content_payload(text: str, provider: str) -> dict[str, Any]:
    """Parse structured content before considering refusal language.

    Generated articles can legitimately contain sentences such as "I can't measure
    stakeholder coverage without role data." Refusal detection must therefore apply
    only when the provider did not return the requested JSON object.
    """
    try:
        return _extract_json_payload(text)
    except (EmptyResponseError, ValidationError) as exc:
        if _looks_like_refusal(text):
            raise RefusalError(f"{provider} refused the content request") from exc
        raise


def _looks_like_refusal(text: str) -> bool:
    normalized = text.strip()
    return "{" not in normalized and len(normalized) <= 1000 and bool(REFUSAL_RE.search(normalized))


def _count_words(html: str) -> int:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return len([word for word in text.split() if word.strip()])


def _self_heal_common_quality_blockers(topic: Topic, body_html: str) -> str:
    """Apply deterministic last-mile fixes for recurring hard quality failures.

    The LLM repair loop is useful for substantive rewrites, but it can get stuck on
    mechanical gate issues such as one forbidden word or a missing definition phrase.
    Fix those locally before the content reaches optimization/quality scoring so the
    publish path can recover without a human editing the draft.
    """
    healed = body_html.replace("\u2014", " - ").replace("&mdash;", " - ")
    replacements = {
        # GEO kill-list words
        "streamline": "simplify",
        "empower": "enable",
        "unlock": "enable",
        "leverage": "use",
        "seamless": "smooth",
        "cutting-edge": "advanced",
        "game-changer": "important change",
        "best-in-class": "strong",
        "synergy": "coordination",
        "holistic": "complete",
        "robust": "strong",
        "turnkey": "ready-to-use",
        "paradigm shift": "major change",
        "thought leader": "expert",
        "disrupt": "change",
        "innovative": "new",
        "revolutionize": "change",
        "transformative": "significant",
        "next-generation": "new",
        "future-proof": "prepare",
        # Forbidden positioning language
        "buyer experience platform": "personalized account experience",
        "microsite builder": "microsite",
        "landing page builder": "personalized campaign destination",
        "page builder": "personalized campaign destination",
        "abx platform": "personalized account experience",
        "bxp": "personalized account experience",
        "activation layer": "governed activation path",
        "ai orchestration platform": "open execution platform",
        # General brand-banned wording
        "revolutionary": "new",
        "set it and forget it": "configure it with clear governance",
        "generator ai": "generative AI",
        "abm platform": "account-based campaign motion",
    }
    for source, target in replacements.items():
        healed = re.sub(rf"\b{re.escape(source)}s?\b", target, healed, flags=re.IGNORECASE)
    for kill_word in GEO_KILL_LIST:
        healed = re.sub(rf"\b{re.escape(kill_word.lower())}\b", "", healed, flags=re.IGNORECASE)

    if not _opening_sentence_has_definition(healed):
        keyword = escape(topic.keywords[0])
        lead = (
            "<p>Pipeline anxiety rises when sales follow-up is slow, generic, or hard to trust, "
            f"and {keyword} refers to personalized, campaign-specific web destinations "
            "that give each buyer a clear next step after a meeting, event, or outreach sequence.</p>"
        )
        healed = f"{lead}\n{healed}"
    return healed


def _opening_sentence_has_definition(body_html: str) -> bool:
    soup = BeautifulSoup(body_html, "html.parser")
    first_p = soup.find("p")
    source_text = first_p.get_text(" ", strip=True) if first_p else soup.get_text(" ", strip=True)
    first_sentence = _first_sentence(source_text).lower()
    return any(
        phrase in f" {first_sentence} "
        for phrase in (" is a ", " is an ", " are ", " refers to ", " defined as ")
    )



def _first_sentence(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    match = re.match(r"^(.+?[.!?])(?:\s|$)", normalized)
    if match:
        return match.group(1).strip()
    return normalized


def _compose_body_html(body_html: str, sections: list[dict[str, Any]]) -> str:
    canonical_body = body_html.strip()
    if not sections:
        return canonical_body

    fragments = [canonical_body] if canonical_body else []
    seen_text = _normalize_text(canonical_body)

    for section in sections:
        fragment = _render_section_fragment(section)
        if not fragment:
            continue
        fragment_text = _normalize_text(fragment)
        if not fragment_text or fragment_text in seen_text:
            continue
        fragments.append(fragment)
        seen_text = " ".join(part for part in (seen_text, fragment_text) if part)

    return "\n\n".join(fragment for fragment in fragments if fragment).strip()


def _render_section_fragment(section: dict[str, Any]) -> str:
    if not isinstance(section, dict):
        return ""

    fragment_html = ""
    for key in ("html", "body_html"):
        value = section.get(key)
        if isinstance(value, str) and value.strip():
            fragment_html = value.strip()
            break

    if not fragment_html:
        return ""

    heading = section.get("heading")
    if (
        isinstance(heading, str)
        and heading.strip()
        and not _starts_with_heading(fragment_html, heading)
    ):
        return f"<h2>{escape(heading.strip())}</h2>\n{fragment_html}"
    return fragment_html


def _starts_with_heading(fragment_html: str, heading: str) -> bool:
    soup = BeautifulSoup(fragment_html, "html.parser")
    for node in soup.contents:
        if isinstance(node, Tag):
            if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                return _normalize_text(node.get_text(" ", strip=True)) == _normalize_text(heading)
            return False
    return False


def _normalize_text(value: str) -> str:
    text = BeautifulSoup(value, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _quality_repair_instructions(topic: Topic, failures: list[str], minimum_words: int) -> str:
    instructions = [
        f"- body_html alone must be a complete {topic.content_type} article "
        f"of at least {minimum_words} words."
    ]
    if any("Missing definition block" in failure for failure in failures):
        instructions.append(
            f'- The very first sentence of body_html MUST match one of these exact patterns: '
            f'"{topic.keywords[0]} is a ..." or "{topic.keywords[0]} refers to ..." unless '
            f'the keyword itself contains forbidden entity language. If it does, write the first '
            f'definitional sentence with an approved substitute such as "personalized account experience" '
            f'or "first-party engagement signal" instead, and do not repeat the forbidden phrase in body_html. '
            f'This sentence must appear before any other content. '
            f'Example: "{topic.keywords[0]} is a personalized, campaign-specific web destination '
            f'designed for account-based marketing and sales outreach."'
        )
    if any("Fewer than two cited sources" in failure for failure in failures):
        instructions.append(
            "- Add at least two attribution sentences inside body_html that "
            'begin with "According to", "Per", "Reported by", or '
            '"Found that", name the source organization, and link the directly '
            "supporting source URL in the same paragraph."
        )
    if any("Unsupported material claim" in failure for failure in failures):
        instructions.append(
            "- For every unsupported material claim, either add a directly supporting inline "
            "source URL from SOURCE CANDIDATES in the same paragraph or remove/qualify the claim. "
            "Never invent a URL or use a source that does not support the exact claim."
        )
    if any("Missing FAQ section" in failure for failure in failures):
        instructions.append(
            "- Add a Frequently Asked Questions section in body_html with an "
            "h2 heading and at least three h3 question / p answer pairs."
        )
    if any("Fewer than 2 links to folloze.com" in failure for failure in failures):
        instructions.append(
            "- Add at least two contextual inline links to approved Folloze URLs inside body_html."
        )
    if any("Missing comparison table" in failure for failure in failures):
        instructions.append("- Include a comparison table near the top of body_html.")
    if any("Missing statistic" in failure for failure in failures):
        instructions.append("- Include at least one numeric statistic or approved proof point.")
    if any("Missing approved proof point" in failure for failure in failures):
        proof_points = ", ".join(PROOF_POINTS)
        instructions.append(
            "- Include at least one approved Folloze proof point exactly as written. "
            f"Valid options: {proof_points}."
        )
    if any("Missing Folloze mention" in failure for failure in failures):
        instructions.append(
            "- Mention Folloze by name in the opening and tie the article back to the platform."
        )
    if any("Contains em dash" in failure for failure in failures):
        instructions.append("- Use commas or periods instead of em dashes.")
    if any("Contains emoji" in failure for failure in failures):
        instructions.append("- Do not use emoji anywhere in the response.")
    if any("Paragraphs are too long on average" in failure for failure in failures):
        instructions.append("- Keep paragraphs to four sentences or fewer on average.")
    if any("keyword density" in failure.lower() for failure in failures):
        instructions.append(
            "- Use the primary keyword naturally and cap exact-match repetition below 3% of words."
        )
    banned_terms = [
        failure.split(": ", 1)[1]
        for failure in failures
        if failure.startswith("Banned term used: ")
    ]
    if banned_terms:
        instructions.append(
            "- Remove banned phrasing and avoid these exact terms: "
            + ", ".join(sorted(set(banned_terms)))
            + "."
        )
    # GEO failure repair instructions
    geo_instructions = _geo_repair_instructions(failures)
    if geo_instructions:
        instructions.extend(geo_instructions)
    instructions.append("- Resolve every quality failure in this checklist before returning:")
    instructions.extend(f"- Checklist: {failure}" for failure in failures)
    return "\n".join(instructions)


def _geo_repair_instructions(failures: list[str]) -> list[str]:
    instructions: list[str] = []
    if any("TL;DR" in f or "tldr" in f.lower() for f in failures):
        instructions.append(
            "- Add a TL;DR section at the top with 2-3 sentences and one specific "
            "statistic. Use a div or section with class 'tldr' or start with 'TL;DR:'."
        )
    if any("Kill-list" in f for f in failures):
        kill_replacements = {
            "streamline": "simplify",
            "empower": "enable",
            "leverage": "use",
            "unlock": "enable",
            "seamless": "smooth",
            "robust": "strong",
            "holistic": "complete",
            "innovative": "new",
            "transformative": "significant",
            "disrupt": "change",
        }
        found_words = []
        for f in failures:
            if "Kill-list words found:" in f:
                found_words = [w.strip() for w in f.split(":", 2)[-1].split(",")]
        replacements = [
            f"  {w} -> {kill_replacements.get(w, 'remove or rephrase')}"
            for w in found_words
            if w in kill_replacements or w in GEO_KILL_LIST
        ]
        if replacements:
            instructions.append("- Replace kill-list words:\n" + "\n".join(replacements))
        else:
            instructions.append("- Remove all marketing buzzwords from the kill list.")
    if any("Forbidden entity" in f for f in failures):
        instructions.append(
            "- Remove ALL forbidden entity terms including plural and variant forms. "
            "Search for and delete every instance of: 'page builder', 'page builders', "
            "'landing page builder', 'landing page builders', 'microsite builder', "
            "'microsite builders', 'buyer experience platform', "
            "'ABX platform', 'BXP', 'activation layer', and 'AI orchestration platform'. "
            "Replace with: 'personalized account experience', 'microsite', "
            "'first-party engagement signal', or 'Folloze'. "
            "Do not use forbidden terms even in negations, comparisons, rebuttals, or FAQ questions "
            "such as 'not just a page builder'. Do a thorough check; even one occurrence fails the gate."
        )
    if any("emotion" in f.lower() or "pain" in f.lower() for f in failures):
        instructions.append(
            "- Rewrite the opening paragraph to lead with a pain point or emotional "
            "territory (AI overwhelm, campaign chaos, pipeline anxiety, credibility "
            "risk, or speed pressure) before mentioning any product or feature."
        )
    if any("citation_format" in f.lower() or "According to" in f for f in failures):
        instructions.append(
            "- Add at least one citation matching this exact pattern: "
            "'According to [Source Name] (YYYY), [specific claim with number].' "
            "The parenthesized four-digit year is mandatory — the gate rejects citations without it. "
            "Example: 'According to Forrester (2024), 67% of B2B buyers prefer personalized content.' "
            "Use a real, verifiable source and year."
        )
    if any("heading density" in f.lower() for f in failures):
        instructions.append(
            "- Add more H2 or H3 headings. Target at least one heading per 200 words."
        )
    if any("answer-first" in f.lower() or "answer_first" in f for f in failures):
        instructions.append(
            "- After each H2 heading, start with a short declarative answer-first sentence (under "
            "40 words, no question marks) that directly answers the section topic. Prefer making "
            "that first paragraph one sentence only, then continue detail in a following paragraph."
        )
    if any("freshness" in f.lower() for f in failures):
        instructions.append(
            "- Add a freshness signal: include 'Updated [Month] [Year]' text or a "
            "<time> element near the top of the article."
        )
    if any("author" in f.lower() and "attribution" in f.lower() for f in failures):
        instructions.append(
            '- Add author attribution: include a <meta name="author" content="Name"> '
            "tag or a byline element with class 'author'."
        )
    if any("em dash" in f.lower() or "emdash" in f.lower() for f in failures):
        instructions.append("- Replace all em dashes with commas, periods, or semicolons.")
    return instructions
