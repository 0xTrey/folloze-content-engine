#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-site.py")], cwd=ROOT, check=True)

    dist_dir = ROOT / "site" / "dist"
    output_dir = ROOT / ".vercel" / "output"
    static_dir = output_dir / "static"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    static_dir.mkdir(parents=True, exist_ok=True)

    for source in dist_dir.rglob("*"):
        if source.is_dir():
            continue
        target = static_dir / source.relative_to(dist_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    config = {
        "version": 3,
        "routes": [
            {"handle": "filesystem"},
            {"src": "/(.*)", "dest": "/$1"},
        ],
    }
    (output_dir / "config.json").write_text(json.dumps(config, indent=2))

    log_path = ROOT / "logs" / "deployments.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    "event": "export_vercel_prebuilt",
                    "static_dir": str(static_dir),
                    "config_path": str(output_dir / "config.json"),
                }
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
