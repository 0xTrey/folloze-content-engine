#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifacts import load_release_artifact  # noqa: E402
from config import Config  # noqa: E402
from verify import check_live_against_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a deployed Vercel page against an artifact"
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--target", choices=("preview", "production"), default="preview")
    parser.add_argument("--url")
    args = parser.parse_args()

    config = Config.load(ROOT / "config.yaml")
    artifact = load_release_artifact(Path(args.artifact))

    base_url = args.url or (
        config.delivery.preview_url if args.target == "preview" else config.delivery.production_url
    )
    live_url = f"{base_url.rstrip('/')}{artifact.route}"
    check_live_against_artifact(
        live_url,
        artifact,
        timeout_seconds=config.pipeline.verify_timeout_seconds,
        poll_interval=5,
    )

    log_path = ROOT / "logs" / "deployments.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    "event": "verify_deploy",
                    "target": args.target,
                    "url": live_url,
                    "artifact": str(Path(args.artifact)),
                    "slug": artifact.slug,
                    "source_run_id": artifact.source_run_id,
                    "status": "verified",
                }
            )
            + "\n"
        )
    print(f"Verified {live_url} against {artifact.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
