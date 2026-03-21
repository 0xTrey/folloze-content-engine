from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from config import Config
from generator import GeneratedContent
from optimizer import OptimizedContent

NUMBER_RE = re.compile(r"\b\d+(?:[%$]|(?:\.\d+)?\s?(?:K|M|B|x))\b")
ATTRIBUTION_RE = re.compile(r"\b(according to|per |found that|reported by)\b", re.IGNORECASE)
FOLLOZE_LINK_RE = re.compile(r'href=["\']https?://(?:www\.)?folloze\.com[^"\']*["\']', re.IGNORECASE)
BANNED_TERMS = [
    "buyer experience platform",
    "revolutionary",
    "cutting-edge",
    "set it and forget it",
    "generator ai",
    "abm platform",
]
PROOF_POINTS = ["$6.3M", "$10M", "98%", "$750K", "5x faster", "478 MQLs"]


@dataclass(slots=True)
class QualityResult:
    passed: bool
    score: int
    reasons: list[str]
    failures: list[str]


def gate(content: OptimizedContent, config: Config, brand_context: str) -> QualityResult:
    min_words = config.content.min_words_by_type[content.generated.content_type]
    checks = [
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

    score = 0
    reasons: list[str] = []
    failures: list[str] = []
    for points, label, failure in checks:
        score += points
        reasons.append(f"{label}: {'pass' if failure is None else 'fail'}")
        if failure:
            failures.append(failure)

    brand_failures = _brand_failures(content.generated, content.body_html)
    failures.extend(brand_failures)
    passed = score >= config.pipeline.quality_threshold and not brand_failures
    return QualityResult(passed=passed, score=score, reasons=reasons, failures=failures)


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
        None if valid else f"Primary keyword density {density:.1%} exceeds 3% ({appearances} occurrences)",
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
    if "—" in text:
        failures.append("Contains em dash")
    if re.search(r"[\U0001F300-\U0001FAFF]", text):
        failures.append("Contains emoji")
    if "folloze" not in lowered:
        failures.append("Missing Folloze mention")
    lowered_proof_points = [point.lower() for point in PROOF_POINTS]
    if not any(proof_point in lowered for proof_point in lowered_proof_points):
        failures.append("Missing approved proof point")
    return failures


def _first_words(html: str, count: int) -> str:
    return " ".join(_body_text(html).split()[:count])


def _body_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ")
