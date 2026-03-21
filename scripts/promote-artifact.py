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
from content_calendar import Topic, load_calendar, mark_published  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a release artifact into site/published")
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    artifact = load_release_artifact(artifact_path)

    published_dir = ROOT / "site" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    target_path = published_dir / f"{artifact.slug}.json"
    payload = asdict(artifact)
    payload["status"] = "published"
    payload["promoted_at"] = dt.datetime.now(dt.UTC).isoformat()

    target_path.write_text(json.dumps(payload, indent=2))

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
