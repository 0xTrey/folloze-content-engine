#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from citation_monitor.monitor import CitationMonitor  # noqa: E402
from config import Config  # noqa: E402

LOGGER = logging.getLogger("citation_monitor_runner")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Folloze citation monitor")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without external provider calls",
    )
    parser.add_argument("--resume", action="store_true", help="Resume the latest incomplete run")
    parser.add_argument(
        "--db-path",
        default=str(ROOT / "data" / "citation_monitor.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--providers",
        default="perplexity,openai",
        help="Comma-separated provider names",
    )
    args = parser.parse_args()

    _configure_logging()

    try:
        config = Config.load(ROOT / "config.yaml")
        LOGGER.info("Loaded config for citation monitor (timezone=%s)", config.pipeline.timezone)

        providers = [provider.strip() for provider in args.providers.split(",") if provider.strip()]
        monitor = CitationMonitor(
            db_path=Path(args.db_path),
            providers=providers,
            dry_run=args.dry_run,
        )
        summary = monitor.run(resume=args.resume)
        LOGGER.info(
            "Citation monitor summary:\n%s",
            json.dumps(asdict(summary), indent=2, sort_keys=True),
        )
        return 0
    except Exception:
        LOGGER.exception("Citation monitor failed")
        return 1


def _configure_logging() -> None:
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "citation-monitor.log"),
            logging.StreamHandler(),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
