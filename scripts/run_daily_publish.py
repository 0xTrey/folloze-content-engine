#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact  # noqa: E402
from config import Config  # noqa: E402
from content_calendar import Topic  # noqa: E402
from notify import send_published  # noqa: E402
from quality import QualityResult  # noqa: E402
from runtime_secrets import get_secret  # noqa: E402
from site_rendering import retarget_release_artifact  # noqa: E402

LOGGER = logging.getLogger("daily_publish")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Folloze publish workflow")
    parser.add_argument("--date", help="YYYY-MM-DD run directory to use after pipeline completion")
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Resume publish from an existing run-manifest without rerunning pipeline.py",
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Stop after export-vercel.py and do not deploy or verify",
    )
    args = parser.parse_args()

    _configure_logging()
    config = Config.load(ROOT / "config.yaml")

    if args.skip_pipeline:
        LOGGER.info("Resuming daily publish workflow from existing run data")
    else:
        LOGGER.info("Starting daily publish workflow")
        _run_command([sys.executable, str(ROOT / "pipeline.py")])

    run_date = args.date or _latest_run_date()
    status = _publish_from_run(run_date, config, skip_deploy=args.skip_deploy)
    return 0 if status in {"published", "promoted", "empty", "locked"} else 1


def _configure_logging() -> None:
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "daily-publish.log"),
            logging.StreamHandler(),
        ],
    )


def _latest_run_date() -> str:
    runs_dir = ROOT / "logs" / "runs"
    run_dates = sorted(path.name for path in runs_dir.iterdir() if path.is_dir())
    if not run_dates:
        raise FileNotFoundError("No run directories found under logs/runs")
    return run_dates[-1]


def _publish_from_run(run_date: str, config: Config, skip_deploy: bool = False) -> str:
    run_dir = ROOT / "logs" / "runs" / run_date
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    status = manifest.get("status", "")
    LOGGER.info("Pipeline completed with status=%s", status)

    if status in {"empty", "locked"}:
        LOGGER.info("No publish action required for status=%s", status)
        return status
    if status != "release_ready":
        raise RuntimeError(f"Pipeline did not produce a publishable artifact: {status}")

    artifact_path = Path(manifest["release_artifact"])
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path

    _run_command(
        [
            sys.executable,
            str(ROOT / "scripts" / "promote-artifact.py"),
            "--artifact",
            str(artifact_path),
        ]
    )
    _run_command([sys.executable, str(ROOT / "scripts" / "export-vercel.py")])

    if skip_deploy:
        LOGGER.info("Skipping Vercel deploy by request")
        return "promoted"

    _run_command(
        ["vercel", "--prod", "--yes"],
        cwd=ROOT / "site" / "dist",
        env=_command_env(),
    )
    _run_command(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify-deploy.py"),
            "--artifact",
            str(artifact_path),
            "--target",
            "production",
        ]
    )

    artifact = retarget_release_artifact(load_release_artifact(artifact_path), config)
    quality = _load_quality_result(run_dir / "quality-report.json")
    send_published(
        Topic(
            title=artifact.title,
            content_type=artifact.content_type,
            slug=artifact.slug,
            keywords=artifact.target_keywords,
            priority=1,
            status="published",
        ),
        artifact.canonical_url,
        quality,
        config,
    )
    LOGGER.info("Daily publish workflow completed for %s", artifact.slug)
    return "published"


def _load_quality_result(path: Path) -> QualityResult:
    payload = json.loads(path.read_text())
    return QualityResult(**payload)


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault(
        "PATH",
        "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    )
    token = get_secret("VERCEL_TOKEN")
    if token:
        env["VERCEL_TOKEN"] = token
    return env


def _run_command(
    command: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> None:
    LOGGER.info("Running command: %s", " ".join(command))
    completed = shutil.which(command[0], path=(env or os.environ).get("PATH"))
    if completed is None and not Path(command[0]).exists():
        raise FileNotFoundError(f"Command not found: {command[0]}")
    subprocess.run(command, cwd=cwd or ROOT, env=env, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
