from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

import content_calendar
from exceptions import CalendarExhaustedError


def test_get_next_topic_returns_highest_priority(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Low",
                        "content_type": "guide",
                        "keywords": ["low"],
                        "priority": 1,
                        "status": "pending",
                    },
                    {
                        "title": "High",
                        "content_type": "guide",
                        "keywords": ["high"],
                        "priority": 5,
                        "status": "pending",
                    },
                ]
            },
            sort_keys=False,
        )
    )

    topics = content_calendar.load_calendar(calendar_path)
    topic = content_calendar.get_next_topic(topics)

    assert topic.title == "High"


def test_get_next_topic_prefers_earlier_planned_date(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Later",
                        "content_type": "guide",
                        "keywords": ["later"],
                        "priority": 5,
                        "planned_date": "2026-03-22",
                        "status": "pending",
                    },
                    {
                        "title": "Sooner",
                        "content_type": "guide",
                        "keywords": ["sooner"],
                        "priority": 1,
                        "planned_date": "2026-03-20",
                        "status": "pending",
                    },
                ]
            },
            sort_keys=False,
        )
    )

    topics = content_calendar.load_calendar(calendar_path)
    topic = content_calendar.get_next_topic(topics)

    assert topic.title == "Sooner"


def test_get_next_topic_raises_when_all_processed() -> None:
    topics = [
        content_calendar.Topic("Done", "guide", "done", ["done"], 1, "published"),
    ]
    with pytest.raises(CalendarExhaustedError):
        content_calendar.get_next_topic(topics)


def test_get_oldest_due_topic_includes_release_ready_and_in_progress(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Future Pending",
                        "content_type": "guide",
                        "slug": "future-pending",
                        "keywords": ["future"],
                        "priority": 5,
                        "planned_date": "2026-03-30",
                        "status": "pending",
                    },
                    {
                        "title": "Due Release Ready",
                        "content_type": "guide",
                        "slug": "due-release-ready",
                        "keywords": ["release"],
                        "priority": 1,
                        "planned_date": "2026-03-27",
                        "status": "release_ready",
                    },
                    {
                        "title": "Due In Progress",
                        "content_type": "guide",
                        "slug": "due-in-progress",
                        "keywords": ["progress"],
                        "priority": 4,
                        "planned_date": "2026-03-28",
                        "status": "in_progress",
                    },
                ]
            },
            sort_keys=False,
        )
    )

    topics = content_calendar.load_calendar(calendar_path)
    topic = content_calendar.get_oldest_due_topic(topics, date(2026, 3, 28))

    assert topic is not None
    assert topic.slug == "due-release-ready"


def test_mark_published_updates_status(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Hello",
                        "content_type": "guide",
                        "slug": "hello",
                        "keywords": ["hello"],
                        "priority": 3,
                        "status": "pending",
                    }
                ]
            },
            sort_keys=False,
        )
    )

    topic = content_calendar.Topic("Hello", "guide", "hello", ["hello"], 3, "pending")
    content_calendar.mark_published(calendar_path, topic, "https://example.com/hello", "2026-03-20")

    payload = yaml.safe_load(calendar_path.read_text())
    assert payload["topics"][0]["status"] == "published"
    assert payload["topics"][0]["published_url"] == "https://example.com/hello"


def test_mark_published_clears_stale_failure_and_release_fields(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Hello",
                        "content_type": "guide",
                        "slug": "hello",
                        "keywords": ["hello"],
                        "priority": 3,
                        "status": "release_ready",
                        "skip_reason": "old failure",
                        "last_error": "old failure",
                        "last_failed_date": "2026-03-27",
                        "release_artifact_path": "logs/runs/2026-03-27/release-artifact.json",
                        "release_ready_date": "2026-03-27",
                    }
                ]
            },
            sort_keys=False,
        )
    )

    topic = content_calendar.Topic("Hello", "guide", "hello", ["hello"], 3, "release_ready")
    content_calendar.mark_published(calendar_path, topic, "https://example.com/hello", "2026-03-28")

    payload = yaml.safe_load(calendar_path.read_text())
    item = payload["topics"][0]
    assert item["status"] == "published"
    assert "skip_reason" not in item
    assert "last_error" not in item
    assert "last_failed_date" not in item
    assert "release_artifact_path" not in item
    assert "release_ready_date" not in item


def test_mark_retry_pending_requeues_topic(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.yaml"
    calendar_path.write_text(
        yaml.safe_dump(
            {
                "topics": [
                    {
                        "title": "Hello",
                        "content_type": "guide",
                        "slug": "hello",
                        "keywords": ["hello"],
                        "priority": 3,
                        "status": "in_progress",
                    }
                ]
            },
            sort_keys=False,
        )
    )

    topic = content_calendar.Topic("Hello", "guide", "hello", ["hello"], 3, "in_progress")
    content_calendar.mark_retry_pending(calendar_path, topic, "temporary failure", "2026-03-28")
    content_calendar.mark_retry_pending(calendar_path, topic, "temporary failure again", "2026-03-29")

    payload = yaml.safe_load(calendar_path.read_text())
    item = payload["topics"][0]
    assert item["status"] == "pending"
    assert item["last_error"] == "temporary failure again"
    assert item["last_failed_date"] == "2026-03-29"
    assert item["retry_count"] == 2
