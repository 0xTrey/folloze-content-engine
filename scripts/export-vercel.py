#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "site" / "dist"
VERCEL_PROJECT = ROOT / ".vercel" / "project.json"


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-site.py")], cwd=ROOT, check=True)

    # Ensure site/dist has a Vercel project link so `vercel --prod` can be
    # run directly from that directory without interactive setup prompts.
    dist_vercel = DIST_DIR / ".vercel"
    dist_vercel.mkdir(parents=True, exist_ok=True)
    if VERCEL_PROJECT.exists():
        shutil.copyfile(VERCEL_PROJECT, dist_vercel / "project.json")

    # Write a minimal vercel.json into dist so cleanUrls works without
    # an outputDirectory indirection.
    vercel_cfg = {"cleanUrls": True, "trailingSlash": False}
    (DIST_DIR / "vercel.json").write_text(json.dumps(vercel_cfg, indent=2))

    log_path = ROOT / "logs" / "deployments.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    "event": "export_vercel_dist",
                    "dist_dir": str(DIST_DIR),
                }
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
