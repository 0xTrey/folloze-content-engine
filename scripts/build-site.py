#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact, render_preview_html  # noqa: E402
from config import Config  # noqa: E402


def build_site() -> int:
    published_dir = ROOT / "site" / "published"
    output_dir = ROOT / "site" / "dist"
    assets_dir = ROOT / "site" / "assets"
    index_path = published_dir / "index.json"
    config = Config.load(ROOT / "config.yaml")

    manifest = json.loads(index_path.read_text()) if index_path.exists() else {"artifacts": []}
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    insights_dir = output_dir / "insights"
    insights_dir.mkdir(exist_ok=True)

    homepage_entries: list[dict[str, str]] = []
    deployment_entries: list[dict[str, str]] = []
    for entry in manifest.get("artifacts", []):
        artifact_path = published_dir / entry["path"]
        artifact = load_release_artifact(artifact_path)
        html = render_preview_html(artifact, ROOT / "site" / "templates")
        target_dir = insights_dir / artifact.slug
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(html)
        card = {
            "slug": artifact.slug,
            "title": artifact.title,
            "route": artifact.route,
            "content_type": artifact.content_type,
            "published_date": artifact.published_date,
            "excerpt": _extract_excerpt(artifact.body_html),
            "canonical_url": artifact.canonical_url,
            "source_run_id": artifact.source_run_id,
        }
        homepage_entries.append(card)
        deployment_entries.append(card)

    (output_dir / "index.html").write_text(_render_homepage(homepage_entries, config))
    (output_dir / "404.html").write_text(_render_not_found())
    _copy_assets(assets_dir, output_dir)
    _write_robots_txt(output_dir, config)
    _write_sitemap(output_dir, config, homepage_entries)
    _write_deployment_manifest(output_dir, config, deployment_entries)
    return 0


def _render_homepage(entries: list[dict[str, str]], config: Config) -> str:
    cards = "\n".join(
        f"""
        <article class="post-card">
          <p class="post-card__meta">{entry["content_type"]} · {entry["published_date"]}</p>
          <h3><a href="{entry["route"]}">{entry["title"]}</a></h3>
          <p>{entry["excerpt"]}</p>
          <a class="post-card__cta" href="{entry["route"]}">Read post</a>
        </article>
        """
        for entry in sorted(entries, key=lambda item: item["published_date"], reverse=True)
    )
    if not cards:
        cards = """
        <article class="empty-state">
          <p class="section-label">No posts yet</p>
          <h3>The Vercel test shell is live.</h3>
          <p>Promote the first release artifact and rebuild the site to populate this blog.</p>
        </article>
        """
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Folloze Insights | Simple V1 Blog</title>
    <meta
      name="description"
      content="A simple V1 Folloze blog running on Vercel for release testing."
    >
    <link rel="canonical" href="{config.site.origin}/">
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <header class="site-header">
      <div class="shell site-header__inner">
        <a class="brand" href="/">
          <span class="brand__mark">Folloze</span>
          <span class="brand__sub">Insights</span>
        </a>
        <nav class="site-nav">
          <a href="#latest">Latest</a>
          <a href="https://www.folloze.com" rel="noreferrer">Folloze</a>
        </nav>
      </div>
    </header>
    <main class="shell">
      <section class="hero">
        <div class="hero__card">
          <p class="hero__kicker">V1 test blog</p>
          <h1>Simple Folloze publishing on Vercel.</h1>
          <p class="hero__lede">
            This lightweight blog is the first live delivery target for the content engine.
            It is intentionally small, fast, and easy for the web team to take over later.
          </p>
        </div>
        <aside class="hero__panel">
          <p class="section-label">Release shape</p>
          <ul>
            <li>Gemini-only content pipeline</li>
            <li>Static bundle for Vercel</li>
            <li>Manual promotion before publish</li>
            <li>Webflow migration in v2</li>
          </ul>
        </aside>
      </section>
      <section class="section" id="latest">
        <div class="section-head">
          <div>
            <p class="section-label">Latest</p>
            <h2>Folloze blog posts</h2>
          </div>
        </div>
        <div class="post-grid">{cards}</div>
      </section>
    </main>
    <footer class="site-footer">
      <div class="shell site-footer__inner">
        <p>Preview URL: {config.delivery.preview_url}</p>
      </div>
    </footer>
  </body>
</html>
"""


def _render_not_found() -> str:
    return """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Not Found | Folloze Insights</title>
    <meta name="description" content="The requested Folloze insight could not be found.">
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <main class="shell">
      <h1>Insight not found</h1>
      <p>The page you requested is not in the current release bundle.</p>
      <p><a href="/">Back to Folloze Insights</a></p>
    </main>
  </body>
</html>
"""


def _extract_excerpt(body_html: str) -> str:
    soup = BeautifulSoup(body_html, "html.parser")
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text:
            return text[:180].rstrip() + ("..." if len(text) > 180 else "")
    text = soup.get_text(" ", strip=True)
    return text[:180].rstrip() + ("..." if len(text) > 180 else "")


def _copy_assets(assets_dir: Path, output_dir: Path) -> None:
    if not assets_dir.exists():
        return
    for source in assets_dir.rglob("*"):
        if source.is_dir():
            continue
        target = output_dir / source.relative_to(assets_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _write_robots_txt(output_dir: Path, config: Config) -> None:
    robots = f"""User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

Sitemap: {config.site.origin}/insights-sitemap.xml
"""
    (output_dir / "robots.txt").write_text(robots)


def _write_sitemap(output_dir: Path, config: Config, entries: list[dict[str, str]]) -> None:
    urls = "\n".join(
        f"""  <url>
    <loc>{config.site.origin.rstrip('/')}{entry["route"]}</loc>
    <lastmod>{entry["published_date"]}</lastmod>
  </url>"""
        for entry in entries
    )
    sitemap = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{urls}\n"
        "</urlset>\n"
    )
    (output_dir / "insights-sitemap.xml").write_text(sitemap)


def _write_deployment_manifest(
    output_dir: Path,
    config: Config,
    entries: list[dict[str, str]],
) -> None:
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "artifact_count": len(entries),
        "site_origin": config.site.origin,
        "preview_url": config.delivery.preview_url,
        "production_url": config.delivery.production_url,
        "routes": sorted(entries, key=lambda item: item["slug"]),
    }
    (output_dir / "deployment-manifest.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    raise SystemExit(build_site())
