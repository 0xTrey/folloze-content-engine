#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evidence import build_evidence_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit published artifacts for claim-level evidence without modifying them."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=PROJECT_ROOT / "site" / "published",
        help="Directory containing published artifact JSON files.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output = args.output.resolve()
    if output == source_dir or source_dir in output.parents:
        parser.error("--output must be outside the published source directory")

    remediation: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    status_counts = {"ready": 0, "weak_support": 0, "unsupported": 0}
    audited_count = 0

    for path in sorted(source_dir.glob("*.json"), key=lambda item: item.name):
        if path.name == "index.json":
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            skipped.append({"path": path.name, "reason": f"invalid JSON: {exc}"})
            continue
        body_html = payload.get("body_html")
        if not isinstance(body_html, str):
            skipped.append({"path": path.name, "reason": "missing body_html"})
            continue

        report = build_evidence_report(body_html, payload.get("source_candidates") or [])
        audited_count += 1
        status_counts[report.status] += 1
        if report.status == "ready":
            continue
        remediation.append(
            {
                "slug": str(payload.get("slug", path.stem)),
                "path": path.name,
                "canonical_url": str(payload.get("canonical_url", "")),
                "evidence_status": report.status,
                "evidence_score": report.score,
                "unsupported_material_claims": report.unsupported_material_claims,
                "invalid_urls": report.invalid_urls,
                "claim_source_matrix": [
                    {
                        "claim_id": item.claim_id,
                        "claim": item.claim,
                        "source_urls": item.source_urls,
                        "status": item.status,
                        "rationale": item.rationale,
                    }
                    for item in report.claim_source_matrix
                    if item.status != "ready"
                ],
                "required_fixes": [
                    {
                        "claim_id": item.claim_id,
                        "action": item.rationale,
                    }
                    for item in report.evidence_plan
                    if item.claim_id
                    in {
                        claim.claim_id
                        for claim in report.claim_source_matrix
                        if claim.status != "ready"
                    }
                ],
            }
        )

    manifest = {
        "schema_version": "1.0",
        "source_dir": str(source_dir),
        "audited_artifact_count": audited_count,
        "status_counts": status_counts,
        "remediation_count": len(remediation),
        "remediation": remediation,
        "skipped": skipped,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), **status_counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
