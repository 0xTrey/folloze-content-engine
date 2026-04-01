from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from brand_rules import (
    BANNED_TERMS,
    ENTITY_FORBIDDEN,
    ENTITY_REQUIRED,
    GEO_KILL_LIST,
    PAIN_SIGNALS,
    PRODUCT_SIGNALS,
    PROOF_POINTS,
)
from config import Config
from generator import GeneratedContent
from optimizer import OptimizedContent

NUMBER_RE = re.compile(r"\b\d+(?:[%$]|(?:\.\d+)?\s?(?:K|M|B|x))\b")
ATTRIBUTION_RE = re.compile(r"\b(according to|per |found that|reported by)\b", re.IGNORECASE)
FOLLOZE_LINK_RE = re.compile(
    r'href=["\']https?://(?:www\.)?folloze\.com[^"\']*["\']', re.IGNORECASE
)


@dataclass(slots=True)
class QualityResult:
    passed: bool
    score: int
    reasons: list[str]
    failures: list[str]
    aeo_score: int = 0
    geo_score: int = 0
    geo_failures: list[str] | None = None


def gate(content: OptimizedContent, config: Config, brand_context: str) -> QualityResult:
    min_words = config.content.min_words_by_type[content.generated.content_type]

    # AEO checks (existing 10, max 100)
    aeo_checks = [
        _check_definition_block(content.body_html),
        _check_comparison_table(content.body_html, content.generated.content_type),
        _check_cited_sources(content.body_html),
        _check_statistics(content.body_html),
        _check_faq_section(content.body_html),
        _check_word_count(content.body_html, min_words),
        _check_json_ld(content.json_ld),
        _check_keyword_density(content.body_html, content.generated.primary_keyword),
        _check_paragraph_length(content.body_html),
        _check_folloze_links(content.body_html),
    ]

    aeo_score = 0
    reasons: list[str] = []
    failures: list[str] = []
    for points, label, failure in aeo_checks:
        aeo_score += points
        reasons.append(f"{label}: {'pass' if failure is None else 'fail'}")
        if failure:
            failures.append(failure)

    # GEO checks (new 10, max 100)
    geo_checks = [
        _check_tldr_present(content.body_html),
        _check_entity_consistency(content.body_html),
        _check_heading_density(content.body_html),
        _check_answer_first_paragraphs(content.body_html),
        _check_citation_format(content.body_html),
        _check_kill_list(content.body_html),
        _check_freshness_signal(content.body_html, content.json_ld),
        _check_author_attribution(content.body_html, content.json_ld),
        _check_emotion_first(content.body_html),
        _check_emdash(content.body_html),
    ]

    geo_score = 0
    geo_failures: list[str] = []
    for points, label, failure in geo_checks:
        geo_score += points
        reasons.append(f"geo_{label}: {'pass' if failure is None else 'fail'}")
        if failure:
            geo_failures.append(failure)

    # Hard GEO failures block regardless of score
    hard_geo_failures = [f for f in geo_failures if any(tag in f for tag in ("[HARD]",))]

    all_failures = failures + geo_failures
    brand_fails = _brand_failures(content.generated, content.body_html)
    all_failures.extend(brand_fails)

    composite = (aeo_score + geo_score) // 2
    passed = (
        aeo_score >= config.pipeline.quality_threshold
        and geo_score >= config.pipeline.geo_quality_threshold
        and not brand_fails
        and not hard_geo_failures
    )
    return QualityResult(
        passed=passed,
        score=composite,
        reasons=reasons,
        failures=all_failures,
        aeo_score=aeo_score,
        geo_score=geo_score,
        geo_failures=geo_failures,
    )


def _check_definition_block(html: str) -> tuple[int, str, str | None]:
    text = _first_words(html, 100).lower()
    valid = any(phrase in text for phrase in (" is a ", " is an ", " refers to ", " defined as "))
    return (15 if valid else 0, "definition_block", None if valid else "Missing definition block")


def _check_comparison_table(html: str, content_type: str) -> tuple[int, str, str | None]:
    if content_type != "comparison":
        return 15, "comparison_table", None
    valid = "<table" in html.lower()
    return (15 if valid else 0, "comparison_table", None if valid else "Missing comparison table")


def _check_cited_sources(html: str) -> tuple[int, str, str | None]:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    matches = len(ATTRIBUTION_RE.findall(text))
    valid = matches >= 2
    return (15 if valid else 0, "cited_sources", None if valid else "Fewer than two cited sources")


def _check_statistics(html: str) -> tuple[int, str, str | None]:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    valid = bool(NUMBER_RE.search(text))
    return (10 if valid else 0, "statistics", None if valid else "Missing statistic")


def _check_faq_section(html: str) -> tuple[int, str, str | None]:
    text = BeautifulSoup(html, "html.parser").get_text(" ").lower()
    valid = any(term in text for term in ("faq", "questions", "frequently asked"))
    return (10 if valid else 0, "faq_section", None if valid else "Missing FAQ section")


def _check_word_count(html: str, min_words: int) -> tuple[int, str, str | None]:
    count = len(_body_text(html).split())
    valid = count >= min_words
    return (10 if valid else 0, "word_count", None if valid else f"Word count below {min_words}")


def _check_json_ld(json_ld_str: str) -> tuple[int, str, str | None]:
    payload = json.loads(json_ld_str)
    valid = "@context" in payload and ("@type" in payload or "@graph" in payload)
    return (10 if valid else 0, "json_ld", None if valid else "Invalid JSON-LD")


def _check_keyword_density(html: str, primary_keyword: str) -> tuple[int, str, str | None]:
    text = _body_text(html).lower()
    appearances = text.count(primary_keyword.lower())
    word_count = max(len(text.split()), 1)
    density = appearances / word_count
    valid = density <= 0.03
    return (
        10 if valid else 0,
        "keyword_density",
        None
        if valid
        else f"Primary keyword density {density:.1%} exceeds 3% ({appearances} occurrences)",
    )


def _check_folloze_links(html: str) -> tuple[int, str, str | None]:
    matches = len(FOLLOZE_LINK_RE.findall(html))
    valid = matches >= 2
    return (
        10 if valid else 0,
        "folloze_links",
        None if valid else f"Fewer than 2 links to folloze.com (found {matches})",
    )


def _check_paragraph_length(html: str) -> tuple[int, str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [paragraph.get_text(" ", strip=True) for paragraph in soup.find_all("p")]
    if not paragraphs:
        return 0, "paragraph_length", "No paragraphs found"
    average = sum(
        len([sentence for sentence in paragraph.split(". ") if sentence])
        for paragraph in paragraphs
    ) / len(paragraphs)
    valid = average <= 4
    return (
        5 if valid else 0,
        "paragraph_length",
        None if valid else "Paragraphs are too long on average",
    )


def _brand_failures(content: GeneratedContent, html: str) -> list[str]:
    failures: list[str] = []
    text = _body_text(html)
    lowered = text.lower()
    for banned in BANNED_TERMS:
        if banned in lowered:
            failures.append(f"Banned term used: {banned}")
    if re.search(r"[\U0001F300-\U0001FAFF]", text):
        failures.append("Contains emoji")
    if "folloze" not in lowered:
        failures.append("Missing Folloze mention")
    lowered_proof_points = [point.lower() for point in PROOF_POINTS]
    if not any(proof_point in lowered for proof_point in lowered_proof_points):
        failures.append("Missing approved proof point")
    return failures


# --- GEO checks (10 checks, max 100 points) ---


def _check_tldr_present(html: str) -> tuple[int, str, str | None]:
    """TL;DR or summary section with a statistic. 15 pts, HARD."""
    soup = BeautifulSoup(html, "html.parser")
    tldr_found = False
    for tag in soup.find_all(["section", "div", "p", "h2", "h3"]):
        class_attr = " ".join(tag.get("class", []))
        tag_text = tag.get_text(" ", strip=True).lower()
        if any(
            marker in (class_attr.lower() + " " + tag_text)
            for marker in ("tldr", "tl;dr", "tl-dr", "summary", "key takeaway")
        ):
            tldr_found = True
            break
    if not tldr_found:
        first_para = _first_words(html, 150).lower()
        if any(marker in first_para for marker in ("tl;dr", "tldr", "in short", "key takeaway")):
            tldr_found = True
    if not tldr_found:
        return 0, "tldr_present", "[HARD] Missing TL;DR or summary section"
    text = _body_text(html)
    has_stat = bool(re.search(r"\b\d+(?:[%$]|(?:\.\d+)?\s?(?:K|M|B|x)\b)", text[:500]))
    if has_stat:
        return 15, "tldr_present", None
    return 8, "tldr_present", "TL;DR present but missing a statistic"


def _check_entity_consistency(html: str) -> tuple[int, str, str | None]:
    """Required entities present, forbidden terms absent. 5 pts, HARD."""
    text = _body_text(html).lower()
    for required in ENTITY_REQUIRED:
        if required.lower() not in text:
            return 0, "entity_consistency", f"[HARD] Missing required entity: {required}"
    for forbidden in ENTITY_FORBIDDEN:
        if forbidden.lower() in text:
            return 0, "entity_consistency", f"[HARD] Forbidden entity term used: {forbidden}"
    return 5, "entity_consistency", None


def _check_heading_density(html: str) -> tuple[int, str, str | None]:
    """At least one H2/H3 per 200 words. 10 pts, soft."""
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.find_all(["h2", "h3"])
    word_count = len(_body_text(html).split())
    if word_count == 0:
        return 0, "heading_density", "No content to evaluate"
    expected = max(1, word_count // 200)
    if len(headings) >= expected:
        return 10, "heading_density", None
    return (
        0,
        "heading_density",
        (
            f"Heading density too low: {len(headings)} headings for {word_count} words "
            f"(need at least {expected})"
        ),
    )


def _check_answer_first_paragraphs(html: str) -> tuple[int, str, str | None]:
    """>=60% of H2s followed by a declarative paragraph. 10 pts, soft."""
    soup = BeautifulSoup(html, "html.parser")
    h2s = soup.find_all("h2")
    if not h2s:
        return 10, "answer_first", None
    declarative_count = 0
    for h2 in h2s:
        next_p = h2.find_next_sibling("p")
        if not next_p:
            continue
        text = next_p.get_text(" ", strip=True)
        words = text.split()
        if len(words) <= 40 and "?" not in text and len(words) >= 3:
            declarative_count += 1
    ratio = declarative_count / len(h2s)
    if ratio >= 0.6:
        return 10, "answer_first", None
    return (
        0,
        "answer_first",
        (
            f"Only {declarative_count}/{len(h2s)} H2s ({ratio:.0%}) have answer-first paragraphs "
            f"(need >=60%)"
        ),
    )


def _check_citation_format(html: str) -> tuple[int, str, str | None]:
    """At least one 'According to [Source] (Year), X%' pattern. 10 pts, soft."""
    text = _body_text(html)
    pattern = re.compile(
        r"according to\s+[A-Z][\w\s&',.-]+\(\d{4}\)",
        re.IGNORECASE,
    )
    if pattern.search(text):
        return 10, "citation_format", None
    if re.search(r"according to\b", text, re.IGNORECASE):
        return 5, "citation_format", "Citation present but missing (Year) format"
    return 0, "citation_format", "No 'According to [Source] (Year)' citation found"


def _check_kill_list(html: str) -> tuple[int, str, str | None]:
    """No kill-list marketing words. 10 pts, HARD."""
    text = _body_text(html).lower()
    found = [word for word in GEO_KILL_LIST if word in text]
    if not found:
        return 10, "kill_list", None
    return 0, "kill_list", f"[HARD] Kill-list words found: {', '.join(found)}"


def _check_freshness_signal(html: str, json_ld_str: str) -> tuple[int, str, str | None]:
    """Freshness marker: dateModified, 'Updated Month Year', or <time>. 10 pts, soft."""
    try:
        payload = json.loads(json_ld_str)
        if payload.get("dateModified"):
            return 10, "freshness_signal", None
    except (json.JSONDecodeError, AttributeError):
        pass
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("time"):
        return 10, "freshness_signal", None
    text = _body_text(html)
    months = (
        r"january|february|march|april|may|june"
        r"|july|august|september|october|november|december"
    )
    if re.search(rf"updated\s+(?:{months})\s+\d{{4}}", text, re.IGNORECASE):
        return 10, "freshness_signal", None
    return 0, "freshness_signal", "No freshness signal (dateModified, Updated date, or <time>)"


def _check_author_attribution(html: str, json_ld_str: str) -> tuple[int, str, str | None]:
    """Named author in meta, JSON-LD, or byline. 10 pts, soft."""
    soup = BeautifulSoup(html, "html.parser")
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content", "").strip():
        return 10, "author_attribution", None
    try:
        payload = json.loads(json_ld_str)
        author = payload.get("author", {})
        if isinstance(author, dict) and author.get("name"):
            return 10, "author_attribution", None
        if isinstance(author, list) and any(a.get("name") for a in author if isinstance(a, dict)):
            return 10, "author_attribution", None
    except (json.JSONDecodeError, AttributeError):
        pass
    for tag in soup.find_all(["span", "p", "div", "a"]):
        class_attr = " ".join(tag.get("class", []))
        if any(marker in class_attr.lower() for marker in ("author", "byline", "writer")):
            if tag.get_text(strip=True):
                return 10, "author_attribution", None
    return 0, "author_attribution", "No author attribution found"


def _check_emotion_first(html: str) -> tuple[int, str, str | None]:
    """First paragraph has pain signal before product signal. 10 pts, soft."""
    soup = BeautifulSoup(html, "html.parser")
    first_p = soup.find("p")
    if not first_p:
        return 0, "emotion_first", "No opening paragraph found"
    text = first_p.get_text(" ", strip=True).lower()
    pain_pos = None
    for signal in PAIN_SIGNALS:
        idx = text.find(signal)
        if idx != -1 and (pain_pos is None or idx < pain_pos):
            pain_pos = idx
    product_pos = None
    for signal in PRODUCT_SIGNALS:
        idx = text.find(signal)
        if idx != -1 and (product_pos is None or idx < product_pos):
            product_pos = idx
    if pain_pos is not None and (product_pos is None or pain_pos < product_pos):
        return 10, "emotion_first", None
    if pain_pos is not None and product_pos is not None:
        return 5, "emotion_first", "Pain signal present but appears after product mention"
    return 0, "emotion_first", "Opening paragraph lacks pain/emotion signal before product mention"


def _check_emdash(html: str) -> tuple[int, str, str | None]:
    """No em dashes in body text. 10 pts, HARD."""
    text = _body_text(html)
    if "—" not in text:
        return 10, "emdash", None
    return 0, "emdash", "[HARD] Contains em dash"


# --- Helpers ---


def _first_words(html: str, count: int) -> str:
    return " ".join(_body_text(html).split()[:count])


def _body_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ")
