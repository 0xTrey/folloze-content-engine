from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from brand_rules import BANNED_TERMS, PROOF_POINTS
from content_calendar import Topic
from site_rendering import extract_takeaways

if TYPE_CHECKING:
    from artifacts import ReleaseArtifact


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_METRIC_RE = re.compile(r"(\$\d[\d.,]*[MK]?|\d+(?:\.\d+)?%|\d+x|\d+\s+MQLs?)", re.IGNORECASE)
_SPECIFIC_TITLE_TOKENS = (
    " vs ",
    "folloze",
    "competitor",
    "comparison",
    "6sense",
    "demandbase",
    "mutiny",
    "pathfactory",
    "userled",
)


@dataclass(slots=True)
class SocialBrief:
    title: str
    slug: str
    published_date: str
    canonical_url: str
    source_run_id: str
    content_type: str
    theme: str
    thesis: str
    summary: str
    target_keywords: list[str]
    key_takeaways: list[str]
    proof_points: list[str]
    brand_posture: str
    role_angle_suggestions: dict[str, str]
    generated_at: str


def build_social_brief(topic: Topic, artifact: "ReleaseArtifact") -> SocialBrief:
    soup = BeautifulSoup(artifact.body_html, "html.parser")
    theme = topic.title or artifact.title
    tldr = _extract_tldr(soup)
    summary = _extract_summary(soup, artifact.meta_description)
    thesis = tldr or _first_sentence(summary) or artifact.meta_description
    takeaways = extract_takeaways(artifact.body_html, limit=5)
    proof_points = _extract_proof_points(soup.get_text(" ", strip=True), takeaways)
    posture = _brand_posture(topic, artifact)
    return SocialBrief(
        title=artifact.title,
        slug=artifact.slug,
        published_date=artifact.published_date,
        canonical_url=artifact.canonical_url,
        source_run_id=artifact.source_run_id,
        content_type=artifact.content_type,
        theme=theme,
        thesis=thesis,
        summary=summary,
        target_keywords=artifact.target_keywords,
        key_takeaways=takeaways,
        proof_points=proof_points,
        brand_posture=posture,
        role_angle_suggestions=_role_angle_suggestions(theme, thesis, proof_points),
        generated_at=dt.datetime.now(dt.UTC).isoformat(),
    )


def social_brief_payload(brief: SocialBrief) -> dict[str, object]:
    return asdict(brief)


def _extract_tldr(soup: BeautifulSoup) -> str:
    tldr = soup.select_one(".tldr p")
    if not tldr:
        return ""
    text = _clean_text(tldr.get_text(" ", strip=True))
    return text.removeprefix("TL;DR: ").strip()


def _extract_summary(soup: BeautifulSoup, fallback: str) -> str:
    paragraphs: list[str] = []
    for paragraph in soup.find_all("p"):
        parent_classes = paragraph.parent.get("class", []) if paragraph.parent else []
        if "tldr" in parent_classes:
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if len(text) < 50:
            continue
        paragraphs.append(text)
        if len(paragraphs) == 2:
            break

    if not paragraphs:
        return fallback

    summary = " ".join(paragraphs)
    if len(summary) <= 420:
        return summary

    sentences = _SENTENCE_RE.split(summary)
    trimmed: list[str] = []
    current = 0
    for sentence in sentences:
        if not sentence:
            continue
        next_length = current + len(sentence) + (1 if trimmed else 0)
        if next_length > 420 and trimmed:
            break
        trimmed.append(sentence.strip())
        current = next_length
    return " ".join(trimmed).strip() or fallback


def _first_sentence(text: str) -> str:
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.split(text) if sentence.strip()]
    return sentences[0] if sentences else text


def _extract_proof_points(text: str, takeaways: list[str]) -> list[str]:
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.split(_clean_text(text)) if sentence.strip()]
    proof_points: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if (
            any(point.lower() in lowered for point in PROOF_POINTS)
            or _METRIC_RE.search(sentence)
            or any(name in sentence for name in ("Conga", "RingCentral", "Check Point", "Qlik", "Microsoft"))
        ):
            candidate = sentence[:220].rstrip()
            if candidate not in proof_points:
                proof_points.append(candidate)
        if len(proof_points) == 4:
            break

    if proof_points:
        return proof_points
    return takeaways[:3]


def _brand_posture(topic: Topic, artifact: "ReleaseArtifact") -> str:
    normalized = f"{topic.title} {artifact.title} {artifact.slug}".lower()
    if any(token in normalized for token in _SPECIFIC_TITLE_TOKENS):
        return "specific_folloze_branded_ok"
    return "personal_thought_leadership_rooted_in_blog"


def _role_angle_suggestions(theme: str, thesis: str, proof_points: list[str]) -> dict[str, str]:
    proof = proof_points[0] if proof_points else thesis
    return {
        "sales": (
            f"Frame '{theme}' around pipeline risk, deal velocity, or revenue accountability. "
            f"Use proof like {proof!r} only when it sharpens the commercial point."
        ),
        "customer_success": (
            f"Translate '{theme}' into adoption, retention, expansion, and customer outcomes. "
            "Favor operator language over campaign jargon."
        ),
        "marketing": (
            f"Use '{theme}' to talk about campaign execution, team leverage, signal activation, "
            "and measurable impact. Keep the takeaway practical."
        ),
        "revops": (
            f"Anchor '{theme}' in process quality, attribution, handoff clarity, and signal trust. "
            "Make the system implication explicit."
        ),
        "leadership": (
            f"Present '{theme}' as a market shift or operating-model insight. "
            "Emphasize control, governance, and revenue visibility."
        ),
    }


def _clean_text(value: str) -> str:
    collapsed = " ".join(value.split())
    for term in BANNED_TERMS:
        collapsed = collapsed.replace(term.title(), term)
    return collapsed.strip()
