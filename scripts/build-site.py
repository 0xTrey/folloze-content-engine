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


def _reading_time(body_html: str) -> str:
    words = len(BeautifulSoup(body_html, "html.parser").get_text(" ").split())
    minutes = max(1, round(words / 225))
    return f"{minutes} min read"


def _render_homepage(entries: list[dict[str, str]], config: Config) -> str:
    sorted_entries = sorted(entries, key=lambda item: item["published_date"], reverse=True)

    cards = "\n".join(
        f"""
        <article class="post-card">
          <p class="post-card__meta">{entry["content_type"]} &middot; {entry["published_date"]}</p>
          <h3><a href="{entry["route"]}">{entry["title"]}</a></h3>
          <p>{entry["excerpt"]}</p>
          <a class="post-card__cta" href="{entry["route"]}">Read &rarr;</a>
        </article>
        """
        for entry in sorted_entries
    )

    latest = sorted_entries[0] if sorted_entries else None
    if latest:
        hero_aside = f"""
        <aside class="hero__panel">
          <p class="section-label">Latest</p>
          <p class="hero__panel-type">{latest["content_type"].upper()}</p>
          <h3 class="hero__panel-title"><a href="{latest["route"]}">{latest["title"]}</a></h3>
          <p class="hero__panel-excerpt">{latest["excerpt"][:120].rstrip()}...</p>
          <a class="post-card__cta" href="{latest["route"]}">Read &rarr;</a>
        </aside>"""
    else:
        hero_aside = """
        <aside class="hero__panel">
          <p class="section-label">By the numbers</p>
          <dl class="proof-list">
            <div><dt>98%</dt><dd>Target account engagement (RingCentral, 60 days)</dd></div>
            <div><dt>$6.3M</dt><dd>Attributed pipeline (Conga, 6 campaigns)</dd></div>
            <div><dt>5x</dt><dd>Faster campaign creation with Campaign Agent</dd></div>
          </dl>
        </aside>"""

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Folloze Insights | AI Orchestration for B2B Marketing</title>
    <meta
      name="description"
      content="Research, glossary pages, and guides on AI orchestration, account-based marketing, and B2B campaign execution from the team at Folloze."
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
          <a href="#latest">Articles</a>
          <a href="https://www.folloze.com" rel="noreferrer">Folloze.com</a>
          <a class="nav__cta" href="https://www.folloze.com/request-demo" rel="noreferrer">Book a demo</a>
        </nav>
      </div>
    </header>
    <main class="shell">
      <section class="hero">
        <div class="hero__card">
          <p class="hero__kicker">AI Orchestration &middot; ABM &middot; Pipeline</p>
          <h1>B2B marketing intelligence, built for the AI era.</h1>
          <p class="hero__lede">
            Practical research, glossary pages, and guides for demand gen and ABM leaders
            running AI-powered go-to-market programs. Every post is structured for AI search visibility.
          </p>
          <a class="hero__cta" href="#latest">Read the latest &darr;</a>
        </div>
        {hero_aside}
      </section>
      <section class="section" id="latest">
        <div class="section-head">
          <div>
            <p class="section-label">From the engine</p>
            <h2>Latest intelligence</h2>
          </div>
        </div>
        <div class="post-grid">{cards}</div>
      </section>
      <section class="cta-band">
        <div class="shell cta-band__inner">
          <p class="cta-band__label">See it in action</p>
          <p class="cta-band__heading">One marketer. Enterprise-scale campaigns.</p>
          <a class="cta-band__btn" href="https://www.folloze.com/request-demo" rel="noreferrer">Book a demo</a>
        </div>
      </section>
    </main>
    <footer class="site-footer">
      <div class="shell site-footer__inner">
        <p>&copy; 2026 <a href="https://www.folloze.com" rel="noreferrer">Folloze</a> &mdash; AI Orchestration Platform for B2B Teams</p>
        <nav class="footer-nav">
          <a href="https://www.folloze.com/platform/overview" rel="noreferrer">Platform</a>
          <a href="https://www.folloze.com/customers" rel="noreferrer">Customers</a>
          <a href="https://www.folloze.com/request-demo" rel="noreferrer">Book a demo</a>
          <a href="https://www.folloze.com/privacy-policy" rel="noreferrer">Privacy</a>
        </nav>
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
