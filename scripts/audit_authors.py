#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from authors import AuthorProfile, primary_author_profile  # noqa: E402


TEXT_SUFFIXES = {".html", ".json", ".xml", ".txt"}


def audit_author_registry(root: Path = ROOT) -> tuple[AuthorProfile, list[str]]:
    findings: list[str] = []
    author = primary_author_profile(root / "data" / "authors.json")
    if "enterprise account executive" not in author.role.lower():
        findings.append(
            f"default author role should be Enterprise Account Executive, found: {author.role}"
        )
    return author, findings


def audit_generated_output(root: Path, author: AuthorProfile) -> list[str]:
    findings: list[str] = []
    dist_dir = root / "site" / "dist"
    if not dist_dir.exists():
        findings.append("generated site output is missing: run scripts/build-site.py")
        return findings

    author_page = dist_dir / "authors" / author.slug / "index.html"
    if not author_page.exists():
        findings.append(f"author page is missing: {author_page.relative_to(root)}")
    else:
        html = author_page.read_text()
        if author.role not in html:
            findings.append(
                f"author page does not contain canonical role '{author.role}': "
                f"{author_page.relative_to(root)}"
            )

    insight_pages = sorted((dist_dir / "insights").glob("*/index.html"))
    for path in insight_pages:
        html = path.read_text()
        if author.name in html and author.role not in html:
            findings.append(
                f"insight page contains author name without canonical role '{author.role}': "
                f"{path.relative_to(root)}"
            )

    for bad_value in author.known_bad_roles:
        if bad_value in author.role:
            continue
        for path in _text_files(dist_dir):
            if bad_value in path.read_text(errors="ignore"):
                findings.append(
                    f"stale author value '{bad_value}' found in {path.relative_to(root)}"
                )
    return findings


def run_audit(root: Path = ROOT) -> tuple[dict[str, object], list[str]]:
    author, findings = audit_author_registry(root)
    findings.extend(audit_generated_output(root, author))
    summary = {
        "default_author_id": author.author_id,
        "author": author.name,
        "role_slug": author.role_slug,
        "role": author.role,
        "team": author.team,
    }
    return summary, findings


def main() -> int:
    summary, findings = run_audit(ROOT)
    print(json.dumps(summary, indent=2))
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}", file=sys.stderr)
        return 1
    print("AUTHOR AUDIT PASSED")
    return 0


def _text_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES]


if __name__ == "__main__":
    raise SystemExit(main())
