from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from exceptions import CalendarExhaustedError

SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class Topic:
    title: str
    content_type: str
    slug: str
    keywords: list[str]
    priority: int
    status: str
    notes: str = ""
    planned_date: str = ""


def slugify(value: str) -> str:
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "untitled"


def load_calendar(path: Path) -> list[Topic]:
    raw = yaml.safe_load(path.read_text()) or {}
    items = raw.get("topics", [])
    topics: list[Topic] = []
    for item in items:
        topics.append(
            Topic(
                title=item["title"],
                content_type=item["content_type"],
                slug=item.get("slug") or slugify(item["title"]),
                keywords=item["keywords"],
                priority=int(item["priority"]),
                status=item["status"],
                notes=item.get("notes", ""),
                planned_date=item.get("planned_date", ""),
            )
        )
    return topics


def get_next_topic(topics: list[Topic]) -> Topic:
    pending = [topic for topic in topics if topic.status == "pending"]
    if not pending:
        raise CalendarExhaustedError("No pending topics remain in content/calendar.yaml")
    return sorted(
        pending,
        key=lambda topic: (_planned_date_key(topic.planned_date), -topic.priority, topic.title),
    )[0]


def mark_in_progress(path: Path, topic: Topic) -> None:
    _update_topic(path, topic.slug, {"status": "in_progress"})


def mark_release_ready(path: Path, topic: Topic, artifact_path: str, date: str) -> None:
    _update_topic(
        path,
        topic.slug,
        {
            "status": "release_ready",
            "release_artifact_path": artifact_path,
            "release_ready_date": date,
        },
    )


def mark_published(path: Path, topic: Topic, url: str, date: str) -> None:
    _update_topic(
        path,
        topic.slug,
        {"status": "published", "published_url": url, "published_date": date},
    )


def mark_skipped(path: Path, topic: Topic, reason: str) -> None:
    _update_topic(path, topic.slug, {"status": "skipped", "skip_reason": reason})


def _update_topic(path: Path, slug: str, updates: dict[str, str]) -> None:
    raw = yaml.safe_load(path.read_text()) or {}
    for item in raw.get("topics", []):
        item_slug = item.get("slug") or slugify(item["title"])
        if item_slug == slug:
            item["slug"] = item_slug
            item.update(updates)
            break
    else:
        raise ValueError(f"Topic with slug '{slug}' not found in calendar")

    path.write_text(yaml.safe_dump(raw, sort_keys=False))


def _planned_date_key(value: str) -> date:
    if not value:
        return date.max
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.max
