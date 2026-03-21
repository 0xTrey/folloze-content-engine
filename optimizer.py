from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from config import Config
from exceptions import SchemaValidationError
from generator import GeneratedContent


@dataclass(slots=True)
class OptimizedContent:
    generated: GeneratedContent
    body_html: str
    json_ld: str
    schema_type: str


def optimize(content: GeneratedContent, config: Config) -> OptimizedContent:
    body_html = _enhance_html(content.body_html)
    json_ld = _render_json_ld(content, config, body_html)
    _validate_json_ld(json_ld)
    return OptimizedContent(
        generated=content,
        body_html=body_html,
        json_ld=json_ld,
        schema_type=_schema_type_for(content.content_type),
    )


def _enhance_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        if table.find("thead"):
            continue
        first_row = table.find("tr")
        if first_row:
            thead = soup.new_tag("thead")
            cloned_row = BeautifulSoup(str(first_row), "html.parser").find("tr")
            if cloned_row:
                for cell in cloned_row.find_all(["td", "th"]):
                    cell.name = "th"
                thead.append(cloned_row)
                table.insert(0, thead)
                first_row.decompose()
    return str(soup)


def _render_json_ld(content: GeneratedContent, config: Config, body_html: str) -> str:
    environment = Environment(
        loader=FileSystemLoader("schema"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(f"{content.content_type}.json")
    slug = content.topic.slug
    route = f"{config.site.insights_path}/{slug}".replace("//", "/")
    rendered = template.render(
        title=content.title,
        meta_description=content.meta_description,
        date_published=date.today().isoformat(),
        slug=slug,
        keywords_csv=", ".join(content.topic.keywords),
        faq_items_json=json.dumps(_extract_faq_items(body_html)),
        canonical_url=f"{config.site.origin}{route}",
    )
    return json.dumps(json.loads(rendered), indent=2)


def _extract_faq_items(body_html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(body_html, "html.parser")
    items: list[dict[str, object]] = []
    headings = soup.find_all("h3")
    for heading in headings:
        question = heading.get_text(" ", strip=True)
        answer = _next_paragraph_text(heading)
        if not answer:
            continue
        items.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    return items[:10]


def _next_paragraph_text(tag: Tag) -> str:
    current = tag.next_sibling
    while current:
        if isinstance(current, Tag) and current.name == "p":
            return current.get_text(" ", strip=True)
        current = current.next_sibling
    return ""


def _validate_json_ld(json_ld: str) -> None:
    payload = json.loads(json_ld)
    if "@context" not in payload:
        raise SchemaValidationError("JSON-LD missing @context")
    if "@type" not in payload and "@graph" not in payload:
        raise SchemaValidationError("JSON-LD missing @type or @graph")


def _schema_type_for(content_type: str) -> str:
    mapping = {
        "comparison": "Article",
        "guide": "HowTo",
        "faq": "FAQPage",
        "glossary": "DefinedTerm",
        "blog": "Article",
    }
    return mapping[content_type]
