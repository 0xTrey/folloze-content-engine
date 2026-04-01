from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jsonschema import validate

from config import Config
from content_calendar import Topic
from exceptions import ArtifactSchemaError, ArtifactWriteError
from optimizer import OptimizedContent
from quality import QualityResult
from site_rendering import (
    author_profile,
    build_article_json_ld,
    extract_takeaways,
    normalize_article_body,
    retarget_release_artifact,
)

ARTIFACT_SCHEMA = {
    "type": "object",
    "required": [
        "title",
        "slug",
        "route",
        "content_type",
        "body_html",
        "meta_title",
        "meta_description",
        "json_ld",
        "target_keywords",
        "published_date",
        "citation_score",
        "word_count",
        "canonical_url",
        "source_run_id",
        "status",
        "review_notes",
    ],
    "properties": {
        "title": {"type": "string"},
        "slug": {"type": "string"},
        "route": {"type": "string"},
        "content_type": {"type": "string"},
        "body_html": {"type": "string"},
        "meta_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "json_ld": {"type": "string"},
        "target_keywords": {"type": "array", "items": {"type": "string"}},
        "published_date": {"type": "string"},
        "citation_score": {"type": "integer"},
        "word_count": {"type": "integer"},
        "canonical_url": {"type": "string"},
        "source_run_id": {"type": "string"},
        "status": {"type": "string"},
        "review_notes": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(slots=True)
class ReleaseArtifact:
    title: str
    slug: str
    route: str
    content_type: str
    body_html: str
    meta_title: str
    meta_description: str
    json_ld: str
    target_keywords: list[str]
    published_date: str
    citation_score: int
    word_count: int
    canonical_url: str
    source_run_id: str
    status: str
    review_notes: list[str]


def write_release_artifact(
    topic: Topic,
    content: OptimizedContent,
    quality: QualityResult,
    config: Config,
    run_dir: Path,
    run_id: str,
) -> ReleaseArtifact:
    artifact = ReleaseArtifact(
        title=content.generated.title,
        slug=topic.slug,
        route=f"{config.site.insights_path}/{topic.slug}".replace("//", "/"),
        content_type=topic.content_type,
        body_html=content.body_html,
        meta_title=content.generated.title,
        meta_description=content.generated.meta_description,
        json_ld=content.json_ld,
        target_keywords=topic.keywords,
        published_date=date.today().isoformat(),
        citation_score=quality.score,
        word_count=content.generated.word_count,
        canonical_url=f"{config.site.origin}{config.site.insights_path}/{topic.slug}",
        source_run_id=run_id,
        status="release_ready",
        review_notes=list(quality.failures),
    )
    payload = asdict(artifact)
    try:
        validate(payload, ARTIFACT_SCHEMA)
    except Exception as exc:
        raise ArtifactSchemaError(f"Release artifact validation failed: {exc}") from exc

    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "release-artifact.json"
    preview_path = run_dir / "rendered-preview.html"
    try:
        artifact_path.write_text(json.dumps(payload, indent=2))
        preview_path.write_text(render_preview_html(artifact, Path("site/templates"), config=config))
    except OSError as exc:
        raise ArtifactWriteError(f"Failed to write release artifacts: {exc}") from exc
    return artifact


def render_preview_html(
    artifact: ReleaseArtifact,
    template_dir: Path,
    *,
    config: Config | None = None,
    related_posts: list[dict[str, str]] | None = None,
) -> str:
    config = config or Config.load(template_dir.resolve().parents[1] / "config.yaml")
    artifact = retarget_release_artifact(artifact, config)
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("insight.html")
    normalized_body = normalize_article_body(artifact.body_html)
    return template.render(
        artifact=artifact,
        author=author_profile(config),
        body_html=normalized_body,
        takeaways=extract_takeaways(normalized_body),
        related_posts=related_posts or [],
        page_title=artifact.meta_title,
        meta_description=artifact.meta_description,
        canonical_url=artifact.canonical_url,
        json_ld_blocks=[build_article_json_ld(artifact, config)],
        body_class="article-page",
        main_class="shell shell--article",
    )


def load_release_artifact(path: Path) -> ReleaseArtifact:
    payload = json.loads(path.read_text())
    try:
        validate(payload, ARTIFACT_SCHEMA)
    except Exception as exc:
        raise ArtifactSchemaError(f"Invalid release artifact at {path}: {exc}") from exc
    allowed_fields = set(ReleaseArtifact.__dataclass_fields__)
    normalized = {key: value for key, value in payload.items() if key in allowed_fields}
    return ReleaseArtifact(**normalized)
