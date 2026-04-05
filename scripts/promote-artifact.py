#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact  # noqa: E402
from config import Config  # noqa: E402
from content_calendar import Topic, load_calendar, mark_published  # noqa: E402
from site_rendering import retarget_release_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a release artifact into site/published")
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    config = Config.load(ROOT / "config.yaml")
    artifact = retarget_release_artifact(load_release_artifact(artifact_path), config)

    published_dir = ROOT / "site" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    target_path = published_dir / f"{artifact.slug}.json"
    payload = asdict(artifact)
    payload["status"] = "published"
    payload["promoted_at"] = dt.datetime.now(dt.UTC).isoformat()

    target_path.write_text(json.dumps(payload, indent=2))
    social_brief_path = artifact_path.with_name("social-brief.json")
    social_brief_target: Path | None = None
    social_brief_url: str | None = None
    if social_brief_path.exists():
        social_briefs_dir = published_dir / "social-briefs"
        social_briefs_dir.mkdir(parents=True, exist_ok=True)
        social_brief_target = social_briefs_dir / f"{artifact.slug}.json"
        social_brief_payload = json.loads(social_brief_path.read_text())
        social_brief_target.write_text(json.dumps(social_brief_payload, indent=2))
        (social_briefs_dir / "latest.json").write_text(json.dumps(social_brief_payload, indent=2))
        social_brief_url = f"{config.site.origin}/social-briefs/{artifact.slug}.json"

    index_path = published_dir / "index.json"
    manifest = json.loads(index_path.read_text()) if index_path.exists() else {"artifacts": []}
    entries = {entry["path"]: entry for entry in manifest.get("artifacts", [])}
    entries[f"{artifact.slug}.json"] = {
        "slug": artifact.slug,
        "title": artifact.title,
        "route": artifact.route,
        "path": f"{artifact.slug}.json",
        "canonical_url": artifact.canonical_url,
        "source_run_id": artifact.source_run_id,
        "promoted_at": payload["promoted_at"],
        "social_brief_path": (
            f"social-briefs/{artifact.slug}.json" if social_brief_target is not None else None
        ),
        "social_brief_url": social_brief_url,
    }
    manifest["artifacts"] = sorted(entries.values(), key=lambda entry: entry["slug"])
    index_path.write_text(json.dumps(manifest, indent=2))
    _append_promotion_log(
        {
            "timestamp": payload["promoted_at"],
            "artifact": str(artifact_path),
            "slug": artifact.slug,
            "title": artifact.title,
            "route": artifact.route,
            "source_run_id": artifact.source_run_id,
            "published_json": str(target_path),
            "social_brief_json": str(social_brief_target) if social_brief_target else "",
        }
    )

    calendar_path = ROOT / "content" / "calendar.yaml"
    topic = _find_topic(calendar_path, artifact.slug, artifact.content_type)
    mark_published(calendar_path, topic, artifact.canonical_url, artifact.published_date)
    return 0


def _find_topic(calendar_path: Path, slug: str, content_type: str) -> Topic:
    for topic in load_calendar(calendar_path):
        if topic.slug == slug:
            return topic
    return Topic(
        title=slug.replace("-", " ").title(),
        content_type=content_type,
        slug=slug,
        keywords=[slug.replace("-", " ")],
        priority=1,
        status="release_ready",
    )


def _append_promotion_log(entry: dict[str, str]) -> None:
    log_path = ROOT / "logs" / "promotions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
