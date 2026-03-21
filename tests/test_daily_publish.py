from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module(repo_copy: Path):
    module_path = repo_copy / "scripts" / "run_daily_publish.py"
    spec = importlib.util.spec_from_file_location("run_daily_publish", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_daily_publish_runs_full_release_flow(repo_copy: Path, monkeypatch) -> None:
    module = _load_module(repo_copy)

    run_dir = repo_copy / "logs" / "runs" / "2026-03-21"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "release-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "title": "Title",
                "slug": "title",
                "route": "/insights/title",
                "content_type": "blog",
                "body_html": "<p>Hello</p>",
                "meta_title": "Meta",
                "meta_description": "Desc",
                "json_ld": '{"@context":"https://schema.org","@type":"Article"}',
                "target_keywords": ["hello"],
                "published_date": "2026-03-21",
                "citation_score": 88,
                "word_count": 600,
                "canonical_url": "https://folloze-blog.vercel.app/insights/title",
                "source_run_id": "run-1",
                "status": "release_ready",
                "review_notes": [],
            },
            indent=2,
        )
    )
    (run_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "passed": True,
                "score": 88,
                "reasons": ["definition_block: pass"],
                "failures": [],
            },
            indent=2,
        )
    )
    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "status": "release_ready",
                "release_artifact": "logs/runs/2026-03-21/release-artifact.json",
            },
            indent=2,
        )
    )

    commands: list[list[str]] = []
    published = {}

    monkeypatch.setattr(module, "_latest_run_date", lambda: "2026-03-21")
    monkeypatch.setattr(
        module,
        "_run_command",
        lambda command, env=None: commands.append(command),
    )
    monkeypatch.setattr(
        module,
        "send_published",
        lambda topic, url, quality, config: published.update(
            {"title": topic.title, "url": url, "score": quality.score}
        ),
    )
    monkeypatch.setattr(sys, "argv", ["run_daily_publish.py"])

    assert module.main() == 0
    assert commands[0][-1].endswith("pipeline.py")
    assert commands[1][-1] == str(artifact_path)
    assert commands[2][-1].endswith("export-vercel.py")
    assert commands[3][0] == "vercel"
    assert commands[4][-1] == "production"
    assert published == {
        "title": "Title",
        "url": "https://folloze-blog.vercel.app/insights/title",
        "score": 88,
    }
