#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from email.utils import format_datetime
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact  # noqa: E402
from config import Config  # noqa: E402
from site_rendering import (  # noqa: E402
    absolute_url,
    author_profile,
    build_article_json_ld,
    build_author_page_json_ld,
    build_generic_page_json_ld,
    extract_takeaways,
    normalize_article_body,
    publisher_profile_dict,
    retarget_release_artifact,
)


def build_site() -> int:
    published_dir = ROOT / "site" / "published"
    output_dir = ROOT / "site" / "dist"
    assets_dir = ROOT / "site" / "assets"
    templates_dir = ROOT / "site" / "templates"
    index_path = published_dir / "index.json"
    config = Config.load(ROOT / "config.yaml")
    environment = _environment(templates_dir)

    manifest = json.loads(index_path.read_text()) if index_path.exists() else {"artifacts": []}
    entries = _load_entries(manifest.get("artifacts", []), published_dir, config)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _copy_social_briefs(published_dir, output_dir)

    for entry in entries:
        related_posts = _related_posts(entry, entries)
        _write_route(
            output_dir,
            entry["route"],
            _render_template(
                environment,
                "insight.html",
                artifact=entry["artifact"],
                author=entry["author"],
                body_html=entry["body_html"],
                takeaways=entry["takeaways"],
                related_posts=related_posts,
                reading_time=entry["reading_time"],
                page_title=entry["artifact"].meta_title,
                meta_description=entry["artifact"].meta_description,
                canonical_url=entry["artifact"].canonical_url,
                json_ld_blocks=[build_article_json_ld(entry["artifact"], config)],
                body_class="article-page",
                main_class="shell shell--article",
            ),
        )

    featured_post = entries[0] if entries else None
    recent_posts = entries[:3]
    _write_route(
        output_dir,
        "/",
        _render_template(
            environment,
            "home.html",
            featured_post=featured_post,
            recent_posts=recent_posts,
            topic_cards=_topic_cards(entries),
            page_title="Folloze Insights | AI Orchestration for B2B Marketing",
            meta_description=(
                "Research, comparisons, and practical guides on AI orchestration, "
                "buyer signals, and B2B campaign execution from Folloze Insights."
            ),
            canonical_url=config.site.origin.rstrip("/") + "/",
            json_ld_blocks=[
                build_generic_page_json_ld(
                    config=config,
                    page_type="WebPage",
                    name="Folloze Insights",
                    description=(
                        "Research, comparisons, and practical guides on AI orchestration, "
                        "buyer signals, and B2B campaign execution from Folloze Insights."
                    ),
                    route="/",
                    breadcrumb_pairs=[("Home", "/")],
                )
            ],
            body_class="site-page",
            main_class="shell",
        ),
    )

    _write_route(
        output_dir,
        "/blog",
        _render_template(
            environment,
            "archive.html",
            posts=entries,
            filters=_archive_filters(entries),
            page_title="Blog Archive | Folloze Insights",
            meta_description=(
                "Browse the full Folloze Insights archive of B2B marketing articles, "
                "comparisons, guides, and glossary pages."
            ),
            canonical_url=absolute_url(config.site.origin, "/blog"),
            json_ld_blocks=[
                build_generic_page_json_ld(
                    config=config,
                    page_type="CollectionPage",
                    name="Folloze Insights Blog Archive",
                    description=(
                        "Browse the full Folloze Insights archive of B2B marketing articles, "
                        "comparisons, guides, and glossary pages."
                    ),
                    route="/blog",
                    breadcrumb_pairs=[("Home", "/"), ("Blog", "/blog")],
                )
            ],
            body_class="site-page",
            main_class="shell",
        ),
    )

    author = author_profile(config)
    _write_route(
        output_dir,
        f"/authors/{author['slug']}",
        _render_template(
            environment,
            "author.html",
            author=author,
            posts=entries,
            page_title=f"{author['name']} | Folloze Insights",
            meta_description=author["short_bio"],
            canonical_url=author["url"],
            json_ld_blocks=[build_author_page_json_ld(config, entries)],
            body_class="site-page",
            main_class="shell",
        ),
    )

    static_pages = _static_pages(config)
    for page in static_pages:
        _write_route(
            output_dir,
            page["route"],
            _render_template(
                environment,
                "page.html",
                page_label=page["label"],
                heading=page["heading"],
                lede=page["lede"],
                body_html=page["body_html"],
                page_title=page["page_title"],
                meta_description=page["meta_description"],
                canonical_url=absolute_url(config.site.origin, page["route"]),
                json_ld_blocks=[page["json_ld"]],
                body_class="site-page",
                main_class="shell",
            ),
        )

    (output_dir / "404.html").write_text(_render_not_found())

    _copy_assets(assets_dir, output_dir)
    _write_robots_txt(output_dir, config)
    _write_sitemaps(output_dir, config, entries, static_pages, author["url"])
    _write_rss(output_dir, config, entries)
    _write_deployment_manifest(output_dir, config, entries, static_pages)
    return 0


def _environment(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _load_entries(
    manifest_entries: list[dict[str, str]],
    published_dir: Path,
    config: Config,
) -> list[dict[str, object]]:
    author = author_profile(config)
    entries: list[dict[str, object]] = []
    for manifest_entry in manifest_entries:
        artifact_path = published_dir / manifest_entry["path"]
        artifact = retarget_release_artifact(load_release_artifact(artifact_path), config)
        body_html = normalize_article_body(artifact.body_html)
        entries.append(
            {
                "slug": artifact.slug,
                "title": artifact.title,
                "route": artifact.route,
                "content_type": artifact.content_type.title(),
                "content_type_key": artifact.content_type,
                "published_date": artifact.published_date,
                "excerpt": _extract_excerpt(body_html),
                "canonical_url": artifact.canonical_url,
                "source_run_id": artifact.source_run_id,
                "primary_keyword": artifact.target_keywords[0] if artifact.target_keywords else "",
                "target_keywords": artifact.target_keywords,
                "artifact": artifact,
                "body_html": body_html,
                "takeaways": extract_takeaways(body_html),
                "reading_time": _reading_time(body_html),
                "author": author,
            }
        )
    return sorted(entries, key=lambda item: item["published_date"], reverse=True)


def _render_template(environment: Environment, template_name: str, **context: object) -> str:
    template = environment.get_template(template_name)
    return template.render(**context)


def _write_route(output_dir: Path, route: str, html: str) -> None:
    normalized = route.strip("/")
    if not normalized:
        target = output_dir / "index.html"
    else:
        target = output_dir / normalized / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)


def _reading_time(body_html: str) -> str:
    words = len(BeautifulSoup(body_html, "html.parser").get_text(" ").split())
    minutes = max(1, round(words / 225))
    return f"{minutes} min read"


def _extract_excerpt(body_html: str) -> str:
    soup = BeautifulSoup(body_html, "html.parser")
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text:
            return text[:180].rstrip() + ("..." if len(text) > 180 else "")
    text = soup.get_text(" ", strip=True)
    return text[:180].rstrip() + ("..." if len(text) > 180 else "")


def _related_posts(
    current_entry: dict[str, object],
    entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    def score(other: dict[str, object]) -> tuple[int, str]:
        current_keywords = set(current_entry["target_keywords"])
        other_keywords = set(other["target_keywords"])
        overlap = len(current_keywords & other_keywords)
        same_type = int(current_entry["content_type_key"] == other["content_type_key"])
        return (same_type * 10 + overlap, other["published_date"])

    candidates = [
        other
        for other in entries
        if other["slug"] != current_entry["slug"]
    ]
    return sorted(candidates, key=score, reverse=True)[:3]


def _topic_cards(entries: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {
            "label": "Category",
            "title": "AI orchestration for B2B teams",
            "copy": (
                "Clear definitions, buyer education, and practical use cases for "
                "how Folloze positions AI orchestration."
            ),
            "href": _route_for_slug(entries, "what-is-ai-orchestration-for-b2b-go-to-market-teams"),
            "cta": "Read the explainer",
        },
        {
            "label": "Signal activation",
            "title": "Individual-level engagement and buying-group signals",
            "copy": (
                "Posts focused on person-level intent, engagement scoring, and the "
                "difference between account selection and next-best action."
            ),
            "href": _route_for_slug(entries, "account-engagement-signals-every-b2b-marketer-should-track"),
            "cta": "See the signal guide",
        },
        {
            "label": "Buyer evaluation",
            "title": "Competitive comparisons and alternatives",
            "copy": (
                "Decision-stage content built for marketers evaluating Folloze "
                "against adjacent products and legacy workflows."
            ),
            "href": _route_for_slug(entries, "folloze-vs-mutiny"),
            "cta": "Read the comparison",
        },
    ]


def _route_for_slug(entries: list[dict[str, object]], slug: str) -> str:
    for entry in entries:
        if entry["slug"] == slug:
            return str(entry["route"])
    return "/blog"


def _archive_filters(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for entry in entries:
        label = str(entry["content_type"])
        counts[label] = counts.get(label, 0) + 1
    filters = [{"label": "All Posts", "count": len(entries)}]
    filters.extend(
        {"label": label, "count": count}
        for label, count in sorted(counts.items())
    )
    return filters


def _static_pages(config: Config) -> list[dict[str, str]]:
    return [
        {
            "route": "/about",
            "label": "About",
            "heading": "About Folloze Insights",
            "lede": (
                "Folloze Insights is the editorial home for research, comparisons, "
                "and guides on AI orchestration for B2B marketing and revenue teams."
            ),
            "page_title": "About | Folloze Insights",
            "meta_description": (
                "Learn what Folloze Insights publishes, why it exists, and how it "
                "supports B2B marketers navigating AI-native go-to-market changes."
            ),
            "body_html": """
            <h2>What we publish</h2>
            <p>Folloze Insights focuses on the operating questions that matter to modern B2B teams: how to activate buyer signals, how to scale campaign execution without adding headcount, and how to connect marketing activity to pipeline outcomes.</p>
            <p>The site publishes comparisons, guides, glossary pages, and practical articles designed to be useful for both human buyers and AI answer engines.</p>
            <h2>Why this site exists</h2>
            <p>Buyers increasingly begin research in ChatGPT, Gemini, and Perplexity before they ever fill out a form. That shifts the job of a content property from simple traffic capture to answer quality, source clarity, and trust.</p>
            <p>Folloze Insights exists to make Folloze's category narrative legible: Folloze is an AI orchestration platform for B2B go-to-market teams, not a generic landing-page tool or static content hub.</p>
            <h2>What readers should expect</h2>
            <ul>
              <li>Clear definitions and direct answers near the top of each page.</li>
              <li>Named authorship and visible publisher information.</li>
              <li>Source-backed claims wherever possible.</li>
              <li>Internal links between related topics so readers can go deeper.</li>
            </ul>
            """,
            "json_ld": build_generic_page_json_ld(
                config=config,
                page_type="AboutPage",
                name="About Folloze Insights",
                description=(
                    "Learn what Folloze Insights publishes, why it exists, and how it "
                    "supports B2B marketers navigating AI-native go-to-market changes."
                ),
                route="/about",
                breadcrumb_pairs=[("Home", "/"), ("About", "/about")],
            ),
        },
        {
            "route": "/editorial-policy",
            "label": "Trust",
            "heading": "Editorial policy",
            "lede": (
                "How Folloze Insights handles sourcing, AI-assisted drafting, human review, "
                "and post-publication updates."
            ),
            "page_title": "Editorial Policy | Folloze Insights",
            "meta_description": (
                "Read the editorial policy for Folloze Insights, including sourcing "
                "standards, AI assistance, human review, and update practices."
            ),
            "body_html": """
            <h2>Sourcing and proof</h2>
            <p>We prioritize primary documentation, product pages, company materials, and attributable external research. Comparative and category pages are expected to cite evidence directly in the article and to avoid unsupported claims.</p>
            <h2>AI-assisted drafting</h2>
            <p>Folloze Insights uses AI tools to assist with research synthesis, drafting, structure, and formatting. AI assistance does not replace editorial judgment. Human review is required before publication.</p>
            <h2>Human review</h2>
            <p>Every published page is reviewed for factual clarity, brand alignment, link accuracy, and on-page structure. This includes checks for canonical URLs, structured data, source coverage, and article readability.</p>
            <h2>Updates and corrections</h2>
            <p>Pages are updated when product positioning changes, links break, or evidence becomes outdated. Material edits should preserve the page's usefulness and improve accuracy rather than simply refresh timestamps.</p>
            <h2>Commercial relationship</h2>
            <p>Folloze Insights is published by Folloze and exists to support education and category understanding around Folloze's market. Commercial intent should be visible, but content should still answer the reader's question directly and honestly.</p>
            """,
            "json_ld": build_generic_page_json_ld(
                config=config,
                page_type="WebPage",
                name="Editorial Policy",
                description=(
                    "Read the editorial policy for Folloze Insights, including sourcing "
                    "standards, AI assistance, human review, and update practices."
                ),
                route="/editorial-policy",
                breadcrumb_pairs=[("Home", "/"), ("Editorial Policy", "/editorial-policy")],
            ),
        },
    ]


def _copy_assets(assets_dir: Path, output_dir: Path) -> None:
    if not assets_dir.exists():
        return
    for source in assets_dir.rglob("*"):
        if source.is_dir():
            continue
        target = output_dir / source.relative_to(assets_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _copy_social_briefs(published_dir: Path, output_dir: Path) -> None:
    social_briefs_dir = published_dir / "social-briefs"
    if not social_briefs_dir.exists():
        return
    for source in social_briefs_dir.rglob("*.json"):
        target = output_dir / "social-briefs" / source.relative_to(social_briefs_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _write_robots_txt(output_dir: Path, config: Config) -> None:
    robots = f"""User-agent: *
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: GPTBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: Claude-User
Allow: /

User-agent: anthropic-ai
Allow: /

Sitemap: {config.site.origin}/sitemap.xml
Sitemap: {config.site.origin}/insights-sitemap.xml
"""
    (output_dir / "robots.txt").write_text(robots)


def _write_sitemaps(
    output_dir: Path,
    config: Config,
    entries: list[dict[str, object]],
    static_pages: list[dict[str, str]],
    author_url: str,
) -> None:
    article_urls = "\n".join(
        f"""  <url>
    <loc>{entry["canonical_url"]}</loc>
    <lastmod>{entry["published_date"]}</lastmod>
  </url>"""
        for entry in entries
    )
    insights_sitemap = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{article_urls}\n"
        "</urlset>\n"
    )
    (output_dir / "insights-sitemap.xml").write_text(insights_sitemap)

    page_entries = [
        (config.site.origin.rstrip("/") + "/", dt.date.today().isoformat()),
        (absolute_url(config.site.origin, "/blog"), dt.date.today().isoformat()),
        (author_url, dt.date.today().isoformat()),
    ]
    page_entries.extend(
        (absolute_url(config.site.origin, page["route"]), dt.date.today().isoformat())
        for page in static_pages
    )
    page_entries.extend((entry["canonical_url"], entry["published_date"]) for entry in entries)
    all_urls = "\n".join(
        f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
  </url>"""
        for url, lastmod in page_entries
    )
    sitemap = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{all_urls}\n"
        "</urlset>\n"
    )
    (output_dir / "sitemap.xml").write_text(sitemap)


def _write_rss(output_dir: Path, config: Config, entries: list[dict[str, object]]) -> None:
    items = []
    for entry in entries:
        published_dt = dt.datetime.fromisoformat(f"{entry['published_date']}T12:00:00+00:00")
        item = f"""
    <item>
      <title>{_xml_escape(str(entry["title"]))}</title>
      <link>{entry["canonical_url"]}</link>
      <guid>{entry["canonical_url"]}</guid>
      <pubDate>{format_datetime(published_dt)}</pubDate>
      <description><![CDATA[{entry["excerpt"]}]]></description>
      <content:encoded><![CDATA[{entry["body_html"]}]]></content:encoded>
    </item>"""
        items.append(item)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Folloze Insights</title>
    <link>{config.site.origin}</link>
    <description>Research, comparisons, and practical guides on AI orchestration for B2B teams.</description>
    <language>en-us</language>
    <lastBuildDate>{format_datetime(dt.datetime.now(dt.UTC))}</lastBuildDate>
    <atom:link href="{config.site.origin}/rss.xml" rel="self" type="application/rss+xml" />
{''.join(items)}
  </channel>
</rss>
"""
    (output_dir / "rss.xml").write_text(rss)


def _write_deployment_manifest(
    output_dir: Path,
    config: Config,
    entries: list[dict[str, object]],
    static_pages: list[dict[str, str]],
) -> None:
    latest_social_brief = next(
        (
            {
                "slug": entry["slug"],
                "title": entry["title"],
                "url": f"{config.site.origin}/social-briefs/{entry['slug']}.json",
                "published_date": entry["published_date"],
            }
            for entry in entries
        ),
        None,
    )
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "artifact_count": len(entries),
        "site_origin": config.site.origin,
        "preview_url": config.delivery.preview_url,
        "production_url": config.delivery.production_url,
        "latest_social_brief": latest_social_brief,
        "routes": [
            {
                "slug": entry["slug"],
                "title": entry["title"],
                "route": entry["route"],
                "canonical_url": entry["canonical_url"],
                "published_date": entry["published_date"],
                "social_brief_url": f"{config.site.origin}/social-briefs/{entry['slug']}.json",
            }
            for entry in entries
        ],
        "static_pages": [
            {"route": "/"},
            {"route": "/blog"},
            {"route": f"/authors/{author_profile(config)['slug']}"},
            *({"route": page["route"]} for page in static_pages),
        ],
    }
    (output_dir / "deployment-manifest.json").write_text(json.dumps(payload, indent=2))


def _render_not_found() -> str:
    return """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Not Found | Folloze Insights</title>
    <meta name="description" content="The requested Folloze Insights page could not be found.">
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body class="site-page">
    <main class="shell shell--article">
      <section class="page-hero">
        <p class="section-label">404</p>
        <h1>Page not found</h1>
        <p class="page-hero__lede">The page you requested is not in the current release bundle.</p>
        <a class="hero__cta" href="/blog">Back to the archive</a>
      </section>
    </main>
  </body>
</html>
"""


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


if __name__ == "__main__":
    raise SystemExit(build_site())
