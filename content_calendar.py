from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from yaml.error import YAMLError

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
    prompt_id: str | None = None


def slugify(value: str) -> str:
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "untitled"


def load_calendar(path: Path) -> list[Topic]:
    raw = _read_calendar_yaml(path)
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
                prompt_id=item.get("prompt_id"),
            )
        )
    return topics


def get_next_topic(topics: list[Topic]) -> Topic:
    # "proposed" entries from gap analyzer require manual promotion to "pending"
    pending = [topic for topic in topics if topic.status == "pending"]
    if not pending:
        raise CalendarExhaustedError("No pending topics remain in content/calendar.yaml")
    return sorted(
        pending,
        key=lambda topic: (_planned_date_key(topic.planned_date), -topic.priority, topic.title),
    )[0]


def get_oldest_due_topic(topics: list[Topic], as_of: date) -> Topic | None:
    candidates = [
        topic
        for topic in topics
        if topic.status in {"pending", "in_progress", "release_ready"}
        and _planned_date_key(topic.planned_date) <= as_of
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda topic: (_planned_date_key(topic.planned_date), -topic.priority, topic.title),
    )[0]


def mark_in_progress(path: Path, topic: Topic) -> None:
    _update_topic(
        path,
        topic.slug,
        {
            "status": "in_progress",
            "skip_reason": None,
            "last_error": None,
            "last_failed_date": None,
        },
    )


def mark_release_ready(path: Path, topic: Topic, artifact_path: str, date: str) -> None:
    _update_topic(
        path,
        topic.slug,
        {
            "status": "release_ready",
            "release_artifact_path": artifact_path,
            "release_ready_date": date,
            "skip_reason": None,
            "last_error": None,
            "last_failed_date": None,
        },
    )


def mark_published(path: Path, topic: Topic, url: str, date: str) -> None:
    _update_topic(
        path,
        topic.slug,
        {
            "status": "published",
            "published_url": url,
            "published_date": date,
            "skip_reason": None,
            "last_error": None,
            "last_failed_date": None,
            "release_artifact_path": None,
            "release_ready_date": None,
        },
    )


def mark_skipped(path: Path, topic: Topic, reason: str) -> None:
    _update_topic(path, topic.slug, {"status": "skipped", "skip_reason": reason})


def mark_retry_pending(path: Path, topic: Topic, reason: str, failed_date: str) -> None:
    raw = _read_calendar_yaml(path)
    for item in raw.get("topics", []):
        item_slug = item.get("slug") or slugify(item["title"])
        if item_slug != topic.slug:
            continue
        item["slug"] = item_slug
        item["status"] = "pending"
        item["last_error"] = reason
        item["last_failed_date"] = failed_date
        item["retry_count"] = int(item.get("retry_count", 0) or 0) + 1
        item.pop("skip_reason", None)
        path.write_text(yaml.safe_dump(raw, sort_keys=False))
        return
    raise ValueError(f"Topic with slug '{topic.slug}' not found in calendar")


def _update_topic(path: Path, slug: str, updates: dict[str, object | None]) -> None:
    raw = _read_calendar_yaml(path)
    for item in raw.get("topics", []):
        item_slug = item.get("slug") or slugify(item["title"])
        if item_slug == slug:
            item["slug"] = item_slug
            for key, value in updates.items():
                if value is None:
                    item.pop(key, None)
                else:
                    item[key] = value
            break
    else:
        raise ValueError(f"Topic with slug '{slug}' not found in calendar")

    path.write_text(yaml.safe_dump(raw, sort_keys=False))


def _read_calendar_yaml(path: Path) -> dict[str, object]:
    text = path.read_text()
    try:
        return yaml.safe_load(text) or {}
    except YAMLError:
        repaired = _fold_unsafe_multiline_scalars(text)
        if repaired == text:
            raise
        return yaml.safe_load(repaired) or {}


def _fold_unsafe_multiline_scalars(text: str) -> str:
    """Convert legacy plain multiline text fields to folded scalars.

    A previous calendar version allowed entries like:

      notes: ... frame
        as search intent ... frame: personalized account experiences,

    PyYAML treats the colon-space in the continuation line as a mapping value and
    aborts before the pipeline can select a topic. Keep the recovery narrow to
    known free-text fields so real structural YAML errors still fail loudly.
    """
    free_text_keys = {"notes", "skip_reason", "last_error"}
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    changed = False

    while index < len(lines):
        line = lines[index]
        match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s+(.+)$", line)
        if not match or match.group(2) not in free_text_keys:
            output.append(line)
            index += 1
            continue

        indent, key, value = match.groups()
        stripped_value = value.strip()
        if stripped_value.startswith(("'", '"', "|", ">", "[", "{")):
            output.append(line)
            index += 1
            continue

        continuation: list[str] = []
        cursor = index + 1
        child_indent = f"{indent}  "
        while cursor < len(lines):
            next_line = lines[cursor]
            if not next_line.strip():
                continuation.append("")
                cursor += 1
                continue
            if not next_line.startswith(child_indent) or next_line.startswith(f"{child_indent}- "):
                break
            continuation.append(next_line[len(child_indent) :].strip())
            cursor += 1

        if not continuation or not _plain_scalar_needs_folding([stripped_value, *continuation]):
            output.append(line)
            index += 1
            continue

        output.append(f"{indent}{key}: >-")
        output.append(f"{child_indent}{stripped_value}")
        for continuation_line in continuation:
            output.append(f"{child_indent}{continuation_line}" if continuation_line else "")
        index = cursor
        changed = True

    repaired = "\n".join(output)
    if text.endswith("\n"):
        repaired += "\n"
    return repaired if changed else text


def _plain_scalar_needs_folding(lines: list[str]) -> bool:
    return any(": " in line or line.endswith(":") for line in lines)


def _planned_date_key(value: str) -> date:
    if not value:
        return date.max
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.max
