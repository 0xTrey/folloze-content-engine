from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

NUMBER_CLAIM_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s?(?:%|x|times|million|billion|[KMB])(?=\W|$)|[$€£]\s?\d)",
    re.IGNORECASE,
)
ATTRIBUTION_CLAIM_RE = re.compile(
    r"\b(?:according to|reported by|research (?:from|by)|a study (?:from|by)|found that)\b",
    re.IGNORECASE,
)
COMPARATIVE_CLAIM_RE = re.compile(
    r"\b(?:best|leading|only|higher|lower|faster|slower|outperform(?:s|ed)?|"
    r"increase(?:s|d)?|decrease(?:s|d)?|reduce(?:s|d)?|improve(?:s|d)?)\b",
    re.IGNORECASE,
)
VENDOR_CAPABILITY_RE = re.compile(
    r"\b(?:Folloze|Adobe|Marketo|HubSpot|Salesforce|Seismic|Showpad|Uberflip|Mutiny|Ceros)\b"
    r".{0,80}\b(?:supports?|provides?|offers?|integrates?|connects?|tracks?|personalizes?|"
    r"routes?|activates?|delivers?)\b",
    re.IGNORECASE,
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(slots=True)
class SourceCandidate:
    title: str
    url: str
    publisher: str
    origin: str
    description: str = ""
    published_at: str = ""


@dataclass(slots=True)
class EvidencePlanItem:
    claim_id: str
    claim: str
    material: bool
    source_urls: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(slots=True)
class ClaimEvidence:
    claim_id: str
    claim: str
    material: bool
    source_urls: list[str]
    status: str
    rationale: str


@dataclass(slots=True)
class EvidenceReport:
    status: str
    score: int
    claim_source_matrix: list[ClaimEvidence]
    source_candidates: list[SourceCandidate]
    evidence_plan: list[EvidencePlanItem]
    unsupported_material_claims: list[str]
    invalid_urls: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_source_url(url: str) -> tuple[bool, str]:
    """Validate source URL structure without making a flaky network request."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False, "URL could not be parsed"
    if parsed.scheme not in {"http", "https"}:
        return False, "URL must use http or https"
    host = (parsed.hostname or "").lower()
    if not host or "." not in host:
        return False, "URL must include a public hostname"
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.endswith(".local"):
        return False, "URL must not point to a local host"
    if parsed.username or parsed.password:
        return False, "URL must not contain credentials"
    return True, ""


def source_candidate_from_result(
    *, title: str, url: str, origin: str, description: str = "", published_at: str = ""
) -> SourceCandidate | None:
    valid, _ = validate_source_url(url)
    if not valid:
        return None
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    publisher = hostname.split(".")[0].replace("-", " ").title()
    return SourceCandidate(
        title=title.strip() or hostname,
        url=url.strip(),
        publisher=publisher,
        origin=origin,
        description=description.strip(),
        published_at=published_at.strip(),
    )


def deduplicate_sources(sources: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    unique: dict[str, SourceCandidate] = {}
    for source in sources:
        normalized = source.url.rstrip("/")
        current = unique.get(normalized)
        if current is None or _source_richness(source) > _source_richness(current):
            unique[normalized] = source
    return [unique[url] for url in sorted(unique)]


def build_evidence_report(
    html: str,
    source_candidates: Iterable[SourceCandidate | dict[str, str]] = (),
) -> EvidenceReport:
    raw_sources = list(source_candidates)
    invalid_urls: set[str] = {
        str(source.url if isinstance(source, SourceCandidate) else source.get("url", ""))
        for source in raw_sources
        if not validate_source_url(
            str(source.url if isinstance(source, SourceCandidate) else source.get("url", ""))
        )[0]
    }
    invalid_urls.discard("")
    candidates = deduplicate_sources(_coerce_sources(raw_sources))
    candidate_by_url = {source.url.rstrip("/"): source for source in candidates}
    candidate_publishers = {
        source.publisher.lower(): source for source in candidates if source.publisher.strip()
    }
    matrix: list[ClaimEvidence] = []
    soup = BeautifulSoup(html, "html.parser")
    for block in soup.find_all(["p", "li", "td"]):
        block_text = block.get_text(" ", strip=True)
        if not block_text:
            continue
        block_links = _block_links(block, invalid_urls)
        for sentence in SENTENCE_RE.split(block_text):
            claim = sentence.strip()
            if not claim or not _is_material_claim(claim):
                continue
            claim_urls = sorted(
                {
                    url
                    for anchor_text, url in block_links
                    if anchor_text and anchor_text.lower() in claim.lower()
                }
            )
            mapping = "direct inline source link"
            if not claim_urls:
                mentioned = [
                    source.url
                    for publisher, source in candidate_publishers.items()
                    if publisher and publisher in claim.lower()
                ]
                claim_urls = sorted(set(mentioned))
                mapping = "publisher mention matched to a research source candidate"

            known = [url for url in claim_urls if url.rstrip("/") in candidate_by_url]
            if known:
                status = "ready"
                rationale = f"{mapping}; URL is present in the captured research provenance"
            elif claim_urls:
                status = "weak_support"
                rationale = f"{mapping}; URL was not captured in the research provenance"
            else:
                status = "unsupported"
                rationale = "material factual claim has no directly mapped source URL"

            matrix.append(
                ClaimEvidence(
                    claim_id=_claim_id(claim),
                    claim=claim,
                    material=True,
                    source_urls=claim_urls,
                    status=status,
                    rationale=rationale,
                )
            )

    matrix = _deduplicate_claims(matrix)
    unsupported = [item.claim for item in matrix if item.status == "unsupported"]
    weak_count = sum(item.status == "weak_support" for item in matrix)
    if unsupported:
        status = "unsupported"
    elif weak_count:
        status = "weak_support"
    else:
        status = "ready"

    score = max(
        0,
        min(100, 100 - (35 * len(unsupported)) - (10 * weak_count) - (5 * len(invalid_urls))),
    )
    plan = [
        EvidencePlanItem(
            claim_id=item.claim_id,
            claim=item.claim,
            material=item.material,
            source_urls=list(item.source_urls),
            rationale=(
                "Keep the mapped citation adjacent to the claim."
                if item.status == "ready"
                else "Add a directly supporting source URL adjacent to this claim before release."
            ),
        )
        for item in matrix
    ]
    return EvidenceReport(
        status=status,
        score=score,
        claim_source_matrix=matrix,
        source_candidates=candidates,
        evidence_plan=plan,
        unsupported_material_claims=unsupported,
        invalid_urls=sorted(invalid_urls),
    )


def _coerce_sources(
    sources: Iterable[SourceCandidate | dict[str, str]],
) -> list[SourceCandidate]:
    coerced: list[SourceCandidate] = []
    for source in sources:
        if isinstance(source, SourceCandidate):
            candidate = source
        else:
            candidate = source_candidate_from_result(
                title=str(source.get("title", "")),
                url=str(source.get("url", "")),
                origin=str(source.get("origin", "unknown")),
                description=str(source.get("description", "")),
                published_at=str(source.get("published_at", "")),
            )
            if candidate is None:
                continue
        valid, _ = validate_source_url(candidate.url)
        if valid:
            coerced.append(candidate)
    return coerced


def _block_links(block: Tag, invalid_urls: set[str]) -> list[tuple[str, str]]:
    links: set[tuple[str, str]] = set()
    for anchor in block.find_all("a", href=True):
        url = str(anchor.get("href", "")).strip()
        valid, _ = validate_source_url(url)
        if valid:
            links.add((anchor.get_text(" ", strip=True), url))
        elif url:
            invalid_urls.add(url)
    return sorted(links)


def _is_material_claim(sentence: str) -> bool:
    if sentence.endswith("?"):
        return False
    return bool(
        NUMBER_CLAIM_RE.search(sentence)
        or ATTRIBUTION_CLAIM_RE.search(sentence)
        or COMPARATIVE_CLAIM_RE.search(sentence)
        or VENDOR_CAPABILITY_RE.search(sentence)
    )


def _claim_id(claim: str) -> str:
    normalized = re.sub(r"\s+", " ", claim.strip().lower())
    return f"claim-{hashlib.sha256(normalized.encode()).hexdigest()[:12]}"


def _source_richness(source: SourceCandidate) -> tuple[int, int, int]:
    return (
        int(bool(source.description.strip())),
        int(bool(source.published_at.strip())),
        len(source.title.strip()),
    )


def _deduplicate_claims(claims: list[ClaimEvidence]) -> list[ClaimEvidence]:
    unique: dict[str, ClaimEvidence] = {}
    for claim in claims:
        unique.setdefault(claim.claim_id, claim)
    return [unique[claim_id] for claim_id in sorted(unique)]
