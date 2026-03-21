#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from content_calendar import slugify  # noqa: E402
from runtime_secrets import get_secret  # noqa: E402

SITEMAPS = {
    "mutiny": "https://www.mutinyhq.com/sitemap.xml",
    "userled": "https://userled.io/sitemap.xml",
    "pathfactory": "https://pathfactory.com/sitemap.xml",
}
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed content/calendar.yaml from competitor sitemaps"
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    calendar_path = ROOT / "content" / "calendar.yaml"
    raw_calendar = yaml.safe_load(calendar_path.read_text()) or {"topics": []}
    existing_slugs = {
        item.get("slug") or slugify(item["title"])
        for item in raw_calendar.get("topics", [])
    }
    candidates: list[dict[str, object]] = []
    config = Config.load(ROOT / "config.yaml")

    for competitor, sitemap_url in SITEMAPS.items():
        try:
            for title in _titles_from_sitemap(sitemap_url):
                slug = slugify(title)
                if slug in existing_slugs:
                    continue
                priority, content_type = _classify_topic(title, config)
                candidates.append(
                    {
                        "title": title,
                        "content_type": content_type,
                        "slug": slug,
                        "keywords": [title.lower()],
                        "priority": priority,
                        "status": "pending",
                        "notes": (
                            f"Seeded from {competitor} sitemap on "
                            f"{datetime.now().date().isoformat()}"
                        ),
                    }
                )
        except requests.RequestException:
            continue

    candidates.sort(key=lambda item: (-int(item["priority"]), item["title"]))
    raw_calendar.setdefault("topics", []).extend(candidates[: args.limit])
    calendar_path.write_text(yaml.safe_dump(raw_calendar, sort_keys=False))
    return 0


def _titles_from_sitemap(url: str) -> list[str]:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    titles: list[str] = []
    for loc in root.findall(".//{*}loc"):
        slug = Path(loc.text or "").name
        if not slug or slug in {"blog", "resources"}:
            continue
        cleaned = re.sub(r"[-_]+", " ", slug).strip()
        if cleaned:
            titles.append(cleaned.title())
    return titles[:25]


def _classify_topic(title: str, config: Config) -> tuple[int, str]:
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return _fallback_classification(title)
    prompt = (
        "Classify this topic for Folloze content. Return JSON with priority (1-5) and "
        "content_type (comparison, guide, faq, glossary, blog): "
        f"{title}"
    )
    endpoint = f"{GEMINI_BASE}/{config.llm.generation_model}:generateContent?key={api_key}"
    response = requests.post(
        endpoint,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    response.raise_for_status()
    text = "\n".join(
        part.get("text", "")
        for part in response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    )
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return _fallback_classification(title)
    payload = json.loads(text[start : end + 1])
    return int(payload.get("priority", 3)), str(payload.get("content_type", "guide"))


def _fallback_classification(title: str) -> tuple[int, str]:
    lowered = title.lower()
    if "vs" in lowered:
        return 4, "comparison"
    if "what is" in lowered:
        return 3, "glossary"
    if "faq" in lowered or "questions" in lowered:
        return 3, "faq"
    if any(term in lowered for term in ("why ", "power of", "future of", "individual-level")):
        return 4, "blog"
    return 3, "guide"


if __name__ == "__main__":
    raise SystemExit(main())
