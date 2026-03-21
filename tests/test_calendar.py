from __future__ import annotations

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
