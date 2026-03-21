#!/usr/bin/env python3
"""
Retroactively inject contextual Folloze.com links into published post artifacts.
Run once to patch existing posts; future posts get links via template requirement.
"""

import json
from pathlib import Path


PATCHES = {
    "what-is-ai-orchestration-for-b2b-go-to-market-teams": [
        (
            "AI orchestration refers to the systematic coordination",
            '<a href="https://www.folloze.com/folloze-ai">AI orchestration</a> refers to the systematic coordination',
        ),
        (
            "Folloze's strategic pillars: Scale, Engage, and Impact.",
            'Folloze\'s <a href="https://www.folloze.com/platform/overview">strategic pillars: Scale, Engage, and Impact</a>.',
        ),
        (
            "RingCentral achieved 98% target account engagement and 50% C-suite engagement in just 60 days",
            '<a href="https://www.folloze.com/customers">RingCentral achieved 98% target account engagement and 50% C-suite engagement in just 60 days</a>',
        ),
        (
            "Conga reported $6.3 million in attributed pipeline",
            '<a href="https://www.folloze.com/customers">Conga reported $6.3 million in attributed pipeline</a>',
        ),
        (
            "request a demo",
            '<a href="https://www.folloze.com/request-demo">request a demo</a>',
        ),
    ],
    "the-power-of-individual-level-engagement-in-folloze": [
        (
            "Folloze, an AI orchestration platform for B2B go-to-market teams, empowers marketers",
            '<a href="https://www.folloze.com/platform/overview">Folloze, an AI orchestration platform for B2B go-to-market teams</a>, empowers marketers',
        ),
        (
            "Folloze's AI orchestration platform directly addresses these challenges by enabling scalable, robust individual-level engagement.",
            'Folloze\'s <a href="https://www.folloze.com/platform/personalization">AI orchestration platform</a> directly addresses these challenges by enabling scalable, robust individual-level engagement.',
        ),
        (
            "RingCentral achieved 98% target account engagement and 50% C-suite engagement in 60 days using Folloze",
            '<a href="https://www.folloze.com/customers">RingCentral achieved 98% target account engagement and 50% C-suite engagement in 60 days</a> using Folloze',
        ),
        (
            "account-based marketing provides a crucial framework",
            '<a href="https://www.folloze.com/solutions/use-cases/abm">account-based marketing</a> provides a crucial framework',
        ),
    ],
    "welcome-to-folloze-insights": [
        (
            "Folloze",
            '<a href="https://www.folloze.com/platform/overview">Folloze</a>',
        ),
    ],
}


def patch_artifact(slug: str, replacements: list[tuple[str, str]]) -> bool:
    path = Path(f"site/published/{slug}.json")
    if not path.exists():
        print(f"  SKIP {slug} — file not found")
        return False

    data = json.loads(path.read_text())
    html = data["body_html"]
    changed = 0

    for old, new in replacements:
        if old in html and new not in html:
            html = html.replace(old, new, 1)
            changed += 1
        elif new in html:
            print(f"  already patched: {old[:50]}...")
        else:
            print(f"  NOT FOUND: {old[:60]}...")

    if changed:
        data["body_html"] = html
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"  {slug}: {changed} link(s) injected")
    else:
        print(f"  {slug}: no changes needed")

    return changed > 0


def main():
    any_changed = False
    for slug, replacements in PATCHES.items():
        print(f"\n{slug}")
        changed = patch_artifact(slug, replacements)
        any_changed = any_changed or changed

    if any_changed:
        print("\nPatches applied. Run build-site.py and export-vercel.py to rebuild.")
    else:
        print("\nNothing to patch.")


if __name__ == "__main__":
    main()
