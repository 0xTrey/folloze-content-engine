from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from config import Config

if TYPE_CHECKING:
    from artifacts import ReleaseArtifact


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class AuthorProfile:
    name: str
    slug: str
    role: str
    short_bio: str
    long_bio: str
    linkedin_url: str
    x_url: str
    image_path: str


@dataclass(frozen=True, slots=True)
class PublisherProfile:
    name: str
    description: str
    site_url: str
    logo_path: str
    linkedin_url: str
    x_url: str


AUTHOR = AuthorProfile(
    name="Trey Harnden",
    slug="trey-harnden",
    role="Account Executive at Folloze",
    short_bio=(
        "Trey Harnden writes about AI orchestration, buyer committee signals, "
        "ABM personalization, and how lean teams run enterprise campaigns."
    ),
    long_bio=(
        "Trey Harnden works at Folloze across pipeline generation, go-to-market "
        "experiments, and AI-assisted content systems. His coverage focuses on "
        "how B2B marketing and revenue teams scale signal activation, content "
        "orchestration, and revenue visibility without adding headcount."
    ),
    linkedin_url="https://www.linkedin.com/in/treyharnden/",
    x_url="https://x.com/Trey_Harnden",
    image_path="/authors/trey-harnden.jpg",
)


def publisher_profile(config: Config) -> PublisherProfile:
    return PublisherProfile(
        name="Folloze",
        description=(
            "Folloze is an AI orchestration platform for B2B go-to-market teams, "
            "built to help marketers scale campaigns, activate buyer signals, and "
            "connect engagement to pipeline."
        ),
        site_url="https://www.folloze.com",
        logo_path="/folloze-logo.png",
        linkedin_url="https://www.linkedin.com/company/folloze/",
        x_url="https://twitter.com/folloze",
    )


def author_profile(config: Config) -> dict[str, Any]:
    author_url = absolute_url(config.site.origin, f"/authors/{AUTHOR.slug}")
    image_url = absolute_url(config.site.origin, AUTHOR.image_path)
    return {
        "name": AUTHOR.name,
        "slug": AUTHOR.slug,
        "role": AUTHOR.role,
        "short_bio": AUTHOR.short_bio,
        "long_bio": AUTHOR.long_bio,
        "linkedin_url": AUTHOR.linkedin_url,
        "x_url": AUTHOR.x_url,
        "image_path": AUTHOR.image_path,
        "image_url": image_url,
        "url": author_url,
        "same_as": [AUTHOR.linkedin_url, AUTHOR.x_url],
    }


def publisher_profile_dict(config: Config) -> dict[str, Any]:
    publisher = publisher_profile(config)
    return {
        "name": publisher.name,
        "description": publisher.description,
        "site_url": publisher.site_url,
        "logo_path": publisher.logo_path,
        "logo_url": absolute_url(config.site.origin, publisher.logo_path),
        "linkedin_url": publisher.linkedin_url,
        "x_url": publisher.x_url,
        "same_as": [publisher.site_url, publisher.linkedin_url, publisher.x_url],
    }


def absolute_url(origin: str, route: str) -> str:
    base = origin.rstrip("/")
    path = route if route.startswith("/") else f"/{route}"
    return f"{base}{path}"


def canonical_url_for_route(config: Config, route: str) -> str:
    return absolute_url(config.site.origin, route)


def retarget_release_artifact(artifact: "ReleaseArtifact", config: Config) -> "ReleaseArtifact":
    canonical_url = canonical_url_for_route(config, artifact.route)
    json_ld = artifact.json_ld
    if artifact.canonical_url and artifact.canonical_url != canonical_url:
        json_ld = json_ld.replace(artifact.canonical_url, canonical_url)
    return replace(artifact, canonical_url=canonical_url, json_ld=json_ld)


def normalize_article_body(body_html: str) -> str:
    soup = BeautifulSoup(body_html, "html.parser")
    for heading in soup.find_all("h1"):
        heading.name = "h2"
    for table in soup.find_all("table"):
        _normalize_table(table, soup)
    return str(soup)


def extract_takeaways(body_html: str, limit: int = 4) -> list[str]:
    soup = BeautifulSoup(body_html, "html.parser")
    takeaways = _takeaways_from_table(soup, limit)
    if len(takeaways) >= limit:
        return takeaways[:limit]

    for paragraph in soup.find_all("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if len(text) < 60:
            continue
        sentence = _SENTENCE_RE.split(text)[0].strip()
        if not sentence:
            continue
        if len(sentence) > 220:
            sentence = sentence[:217].rstrip() + "..."
        sentence = sentence.rstrip(".") + "."
        if sentence not in takeaways:
            takeaways.append(sentence)
        if len(takeaways) == limit:
            break
    return takeaways[:limit]


def build_article_json_ld(artifact: "ReleaseArtifact", config: Config) -> str:
    author = author_profile(config)
    publisher = publisher_profile_dict(config)
    graph = _load_json_ld_nodes(artifact.json_ld)
    normalized_graph: list[dict[str, Any]] = []
    found_primary = False

    for node in graph:
        if not isinstance(node, dict):
            continue
        current = copy.deepcopy(node)
        node_type = current.get("@type")
        node_types = node_type if isinstance(node_type, list) else [node_type]
        node_types = [value for value in node_types if isinstance(value, str)]
        if any(value in {"Article", "BlogPosting", "TechArticle", "HowTo"} for value in node_types):
            found_primary = True
            current["headline"] = artifact.title
            current["name"] = current.get("name") or artifact.title
            current["description"] = artifact.meta_description
            current["author"] = _person_ref(author)
            current["publisher"] = _organization_ref(publisher)
            current["mainEntityOfPage"] = {"@type": "WebPage", "@id": artifact.canonical_url}
            current["url"] = artifact.canonical_url
            current["datePublished"] = artifact.published_date
            current["dateModified"] = artifact.published_date
        if any(value == "FAQPage" for value in node_types):
            current["mainEntityOfPage"] = {"@type": "WebPage", "@id": artifact.canonical_url}
        normalized_graph.append(current)

    if not found_primary:
        normalized_graph.insert(
            0,
            {
                "@type": "Article",
                "headline": artifact.title,
                "description": artifact.meta_description,
                "author": _person_ref(author),
                "publisher": _organization_ref(publisher),
                "mainEntityOfPage": {"@type": "WebPage", "@id": artifact.canonical_url},
                "url": artifact.canonical_url,
                "datePublished": artifact.published_date,
                "dateModified": artifact.published_date,
                "keywords": ", ".join(artifact.target_keywords),
            },
        )

    normalized_graph.extend(
        [
            _organization_node(publisher),
            _person_node(author),
            _web_page_node(
                name=artifact.title,
                description=artifact.meta_description,
                url=artifact.canonical_url,
            ),
            _breadcrumb_node(
                [
                    ("Home", "/"),
                    ("Blog", "/blog"),
                    (artifact.title, artifact.route),
                ],
                config,
            ),
        ]
    )
    return json.dumps({"@context": "https://schema.org", "@graph": normalized_graph}, indent=2)


def build_generic_page_json_ld(
    *,
    config: Config,
    page_type: str,
    name: str,
    description: str,
    route: str,
    breadcrumb_pairs: list[tuple[str, str]],
) -> str:
    publisher = publisher_profile_dict(config)
    page_url = absolute_url(config.site.origin, route)
    graph: list[dict[str, Any]] = [
        _organization_node(publisher),
        {
            "@type": page_type,
            "name": name,
            "headline": name,
            "description": description,
            "url": page_url,
            "mainEntityOfPage": page_url,
            "publisher": _organization_ref(publisher),
        },
        _web_page_node(name=name, description=description, url=page_url),
        _breadcrumb_node(breadcrumb_pairs, config),
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2)


def build_author_page_json_ld(config: Config, posts: list[dict[str, Any]]) -> str:
    author = author_profile(config)
    publisher = publisher_profile_dict(config)
    page_url = author["url"]
    graph: list[dict[str, Any]] = [
        _organization_node(publisher),
        _person_node(author),
        {
            "@type": "ProfilePage",
            "name": author["name"],
            "headline": author["name"],
            "description": author["short_bio"],
            "url": page_url,
            "mainEntity": _person_ref(author),
            "publisher": _organization_ref(publisher),
            "hasPart": [
                {
                    "@type": "Article",
                    "headline": post["title"],
                    "url": post["canonical_url"],
                }
                for post in posts
            ],
        },
        _breadcrumb_node(
            [
                ("Home", "/"),
                ("Author", "/authors/trey-harnden"),
                (author["name"], "/authors/trey-harnden"),
            ],
            config,
        ),
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2)


def _load_json_ld_nodes(raw_json_ld: str) -> list[Any]:
    try:
        payload = json.loads(raw_json_ld)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        return payload["@graph"]
    if isinstance(payload, dict):
        return [payload]
    return []


def _person_ref(author: dict[str, Any]) -> dict[str, str]:
    return {"@type": "Person", "@id": author["url"], "name": author["name"]}


def _organization_ref(publisher: dict[str, Any]) -> dict[str, str]:
    return {"@type": "Organization", "@id": publisher["site_url"], "name": publisher["name"]}


def _organization_node(publisher: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "Organization",
        "@id": publisher["site_url"],
        "name": publisher["name"],
        "url": publisher["site_url"],
        "description": publisher["description"],
        "logo": {
            "@type": "ImageObject",
            "url": publisher["logo_url"],
        },
        "sameAs": publisher["same_as"],
    }


def _person_node(author: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "Person",
        "@id": author["url"],
        "name": author["name"],
        "description": author["long_bio"],
        "jobTitle": author["role"],
        "url": author["url"],
        "worksFor": {"@type": "Organization", "@id": "https://www.folloze.com"},
        "image": {
            "@type": "ImageObject",
            "url": author["image_url"],
        },
        "sameAs": author["same_as"],
    }


def _web_page_node(*, name: str, description: str, url: str) -> dict[str, Any]:
    return {
        "@type": "WebPage",
        "@id": url,
        "name": name,
        "description": description,
        "url": url,
    }


def _breadcrumb_node(
    breadcrumb_pairs: list[tuple[str, str]],
    config: Config,
) -> dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": label,
                "item": absolute_url(config.site.origin, route),
            }
            for index, (label, route) in enumerate(breadcrumb_pairs, start=1)
        ],
    }


def _normalize_table(table: Tag, soup: BeautifulSoup) -> None:
    direct_rows = [child for child in table.children if isinstance(child, Tag) and child.name == "tr"]
    if direct_rows:
        header_row = direct_rows[0] if direct_rows[0].find("th") else None
        if header_row and table.find("thead") is None:
            thead = soup.new_tag("thead")
            thead.append(header_row.extract())
            table.insert(0, thead)
        body_rows = [row for row in direct_rows if row.parent == table]
        if body_rows:
            tbody = table.find("tbody")
            if tbody is None:
                tbody = soup.new_tag("tbody")
                table.append(tbody)
            for row in body_rows:
                tbody.append(row.extract())
    elif table.find("tbody") is None and table.find("thead") is not None:
        tbody = soup.new_tag("tbody")
        for sibling in list(table.children):
            if isinstance(sibling, Tag) and sibling.name == "tr":
                tbody.append(sibling.extract())
        if tbody.contents:
            table.append(tbody)


def _takeaways_from_table(soup: BeautifulSoup, limit: int) -> list[str]:
    table = soup.find("table")
    if not table:
        return []
    rows = table.find_all("tr")
    if not rows:
        return []
    takeaways: list[str] = []
    headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
    for row in rows[1:]:
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) < 3:
            continue
        left_label = headers[1] if len(headers) > 1 else "Option 1"
        right_label = headers[2] if len(headers) > 2 else "Option 2"
        takeaways.append(
            f"{cells[0]}: {left_label} {cells[1]}, while {right_label} {cells[2]}."
        )
        if len(takeaways) == limit:
            break
    return takeaways


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
