#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "content/review-only/persistent-gap-evidence-packs-2026-08.yaml"
EXPECTED = {
    "t1-001": ("new", "2026-08-05", "best-ai-marketing-platforms-for-b2b"),
    "t1-003": (
        "refresh",
        "2026-08-07",
        "how-to-personalize-content-for-different-accounts-without-hiring-more-people",
    ),
    "t2-001": (
        "new",
        "2026-08-10",
        "what-is-individual-level-personalization-in-b2b-marketing",
    ),
    "t1-006": ("refresh", "2026-08-16", "digital-sales-rooms-for-b2b-revenue-teams"),
    "t1-007": (
        "refresh",
        "2026-08-22",
        "best-digital-sales-room-software-for-enterprise-revenue-teams",
    ),
    "t3-001": (
        "refresh",
        "2026-08-08",
        "how-one-marketer-can-run-enterprise-campaigns-with-folloze",
    ),
}
ALLOWED_SUPPORT = {"supported", "qualified"}
ALLOWED_SOURCE_TYPES = {
    "official_customer_story",
    "official_help_documentation",
    "official_product_page",
    "official_vendor_guide",
}


def validate_pack(path: Path, *, check_urls: bool = False) -> list[str]:
    payload = yaml.safe_load(path.read_text()) or {}
    errors: list[str] = []

    if payload.get("overall_status") != "review_only":
        errors.append("top-level overall_status must be review_only")
    if payload.get("calendar_action") != "none":
        errors.append("top-level calendar_action must be none")
    if payload.get("publication_action") != "none":
        errors.append("top-level publication_action must be none")

    packages = payload.get("packages") or []
    prompt_ids = [package.get("prompt_id") for package in packages]
    if len(prompt_ids) != len(set(prompt_ids)):
        errors.append("prompt_id values must be unique")
    if set(prompt_ids) != set(EXPECTED):
        errors.append(
            f"prompt_id set must be {sorted(EXPECTED)}; found {sorted(str(value) for value in prompt_ids)}"
        )

    checked_urls: set[str] = set()
    for package in packages:
        prompt_id = str(package.get("prompt_id"))
        prefix = f"{prompt_id}: "
        if prompt_id not in EXPECTED:
            continue

        expected_action, expected_date, expected_slug = EXPECTED[prompt_id]
        if package.get("status") != "review_only":
            errors.append(prefix + "status must be review_only")
        if package.get("canonical_action") != expected_action:
            errors.append(prefix + f"canonical_action must be {expected_action}")
        if str(package.get("intended_slot")) != expected_date:
            errors.append(prefix + f"intended_slot must be {expected_date}")
        if package.get("slug") != expected_slug:
            errors.append(prefix + f"slug must be {expected_slug}")

        canonical_url = str(package.get("canonical_url") or "")
        parsed_canonical = urlparse(canonical_url)
        if parsed_canonical.scheme != "https" or parsed_canonical.netloc != "www.folloze-blog.com":
            errors.append(prefix + "canonical_url must use https://www.folloze-blog.com")
        if not parsed_canonical.path.endswith("/" + expected_slug):
            errors.append(prefix + "canonical_url must end with the package slug")

        answer_words = str(package.get("answer_first_block") or "").split()
        if not 40 <= len(answer_words) <= 60:
            errors.append(prefix + f"answer_first_block must be 40-60 words; found {len(answer_words)}")
        if len(package.get("outline") or []) < 6:
            errors.append(prefix + "outline must contain at least six sections")

        artifact_path = ROOT / "site/published" / f"{expected_slug}.json"
        configured_artifact = package.get("existing_artifact_path")
        if expected_action == "refresh":
            if configured_artifact != str(artifact_path.relative_to(ROOT)):
                errors.append(prefix + "existing_artifact_path does not match the refresh slug")
            if not artifact_path.exists():
                errors.append(prefix + f"refresh artifact does not exist: {artifact_path}")
            else:
                artifact = json.loads(artifact_path.read_text())
                if artifact.get("slug") != expected_slug:
                    errors.append(prefix + "existing artifact slug mismatch")
                if artifact.get("canonical_url") != canonical_url:
                    errors.append(prefix + "existing artifact canonical_url mismatch")
        else:
            if configured_artifact is not None:
                errors.append(prefix + "new pages must have null existing_artifact_path")
            if artifact_path.exists():
                errors.append(prefix + f"new-page slug already exists: {artifact_path}")

        sources = package.get("sources") or []
        if len(sources) < 2:
            errors.append(prefix + "at least two sources are required")
        source_ids = [source.get("source_id") for source in sources]
        if len(source_ids) != len(set(source_ids)):
            errors.append(prefix + "source_id values must be unique within a package")
        for source in sources:
            source_id = str(source.get("source_id") or "")
            source_prefix = prefix + f"source {source_id}: "
            if source.get("source_type") not in ALLOWED_SOURCE_TYPES:
                errors.append(source_prefix + "source_type is not an approved primary-source type")
            if str(source.get("checked_at")) != "2026-08-04":
                errors.append(source_prefix + "checked_at must be 2026-08-04")
            url = str(source.get("url") or "")
            if urlparse(url).scheme != "https" or not urlparse(url).netloc:
                errors.append(source_prefix + "url must be an absolute HTTPS URL")
            if not str(source.get("rationale") or "").strip():
                errors.append(source_prefix + "rationale is required")
            if check_urls and url and url not in checked_urls:
                checked_urls.add(url)
                try:
                    response = requests.get(
                        url,
                        timeout=20,
                        allow_redirects=True,
                        headers={"User-Agent": "Folloze evidence-pack validator/1.0"},
                    )
                    if response.status_code in {401, 403}:
                        print(
                            source_prefix
                            + f"WARNING: live URL returned HTTP {response.status_code}; "
                            "the official site blocks automated retrieval and requires browser review"
                        )
                    elif response.status_code >= 400:
                        errors.append(source_prefix + f"live URL returned HTTP {response.status_code}")
                except requests.RequestException as exc:
                    errors.append(source_prefix + f"live URL check failed: {exc}")

        claims = package.get("claim_source_matrix") or []
        if not claims:
            errors.append(prefix + "claim_source_matrix is required")
        claim_ids = [claim.get("claim_id") for claim in claims]
        if len(claim_ids) != len(set(claim_ids)):
            errors.append(prefix + "claim_id values must be unique within a package")
        valid_source_ids = set(source_ids)
        for claim in claims:
            claim_id = str(claim.get("claim_id") or "")
            claim_prefix = prefix + f"claim {claim_id}: "
            mapped = set(claim.get("source_ids") or [])
            if not mapped:
                errors.append(claim_prefix + "at least one source_id is required")
            unknown = mapped - valid_source_ids
            if unknown:
                errors.append(claim_prefix + f"unknown source_ids: {sorted(unknown)}")
            if claim.get("support_level") not in ALLOWED_SUPPORT:
                errors.append(claim_prefix + "support_level must be supported or qualified")
            if not str(claim.get("caveat") or "").strip():
                errors.append(claim_prefix + "caveat is required")

        internal_links = package.get("internal_links") or []
        if len(internal_links) < 3:
            errors.append(prefix + "at least three internal links are required")
        for internal_link in internal_links:
            linked_slug = str(internal_link.get("slug") or "")
            if not (ROOT / "site/published" / f"{linked_slug}.json").exists():
                errors.append(prefix + f"internal-link artifact does not exist: {linked_slug}")

        if len(package.get("review_gates") or []) < 3:
            errors.append(prefix + "at least three review gates are required")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review-only persistent-gap evidence packs")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--check-urls", action="store_true", help="Also verify live source URLs")
    args = parser.parse_args()

    errors = validate_pack(args.path, check_urls=args.check_urls)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated 6 review-only evidence packs: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
