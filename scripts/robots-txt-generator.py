#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402

AGENTS = [
    "GPTBot",
    "ChatGPT-User",
    "ClaudeBot",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
    "Bingbot",
    "Bytespider",
    "Applebot-Extended",
    "cohere-ai",
    "CCBot",
    "ia_archiver",
]


def main() -> int:
    config = Config.load(ROOT / "config.yaml")
    assets_dir = ROOT / "site" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    robots_lines = ["User-agent: *", "Allow: /", ""]
    for agent in AGENTS:
        robots_lines.extend([f"User-agent: {agent}", "Allow: /", ""])
    robots_lines.extend(
        [
            f"Sitemap: {config.site.origin}/insights-sitemap.xml",
            f"Sitemap: {config.site.origin}/sitemap.xml",
        ]
    )
    (assets_dir / "robots.txt").write_text("\n".join(robots_lines) + "\n")

    manifest_path = ROOT / "site" / "published" / "index.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {"artifacts": []}
    urls = [
        f"  <url><loc>{config.site.origin}{config.site.insights_path}/{entry['slug']}</loc></url>"
        for entry in manifest.get("artifacts", [])
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (assets_dir / "insights-sitemap.xml").write_text(sitemap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
