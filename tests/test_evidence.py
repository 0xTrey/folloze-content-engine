from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evidence import SourceCandidate, build_evidence_report, validate_source_url


def test_validate_source_url_rejects_local_and_credentials() -> None:
    assert validate_source_url("https://example.com/report")[0] is True
    assert validate_source_url("http://localhost/report")[0] is False
    assert validate_source_url("https://user:secret@example.com/report")[0] is False


def test_direct_known_source_makes_material_claim_ready() -> None:
    source = SourceCandidate(
        title="Benchmark report",
        url="https://research.example.com/report",
        publisher="Research Example",
        origin="brave",
    )
    report = build_evidence_report(
        '<p>Campaign teams improved conversion by 25% in the '
        '<a href="https://research.example.com/report">benchmark report</a>.</p>',
        [source],
    )
    assert report.status == "ready"
    assert report.score == 100
    assert report.claim_source_matrix[0].source_urls == [source.url]


def test_unknown_inline_source_is_weak_support_not_ready() -> None:
    report = build_evidence_report(
        '<p>Campaign teams improved conversion by 25% in the '
        '<a href="https://unknown.example/report">benchmark report</a>.</p>'
    )
    assert report.status == "weak_support"
    assert report.score == 90


def test_link_for_one_sentence_does_not_support_another_sentence() -> None:
    source = SourceCandidate(
        title="Benchmark report",
        url="https://research.example.com/report",
        publisher="Research Example",
        origin="brave",
    )
    report = build_evidence_report(
        '<p>The <a href="https://research.example.com/report">benchmark report</a> found a '
        "25% improvement. A separate program improved conversion by 40%.</p>",
        [source],
    )
    statuses = {claim.claim: claim.status for claim in report.claim_source_matrix}
    assert statuses["The benchmark report found a 25% improvement."] == "ready"
    assert statuses["A separate program improved conversion by 40%."] == "unsupported"
    assert report.status == "unsupported"


def test_unsupported_material_claim_is_release_blocking_status() -> None:
    report = build_evidence_report("<p>Teams improved conversion by 25%.</p>")
    assert report.status == "unsupported"
    assert report.score == 65
    assert report.unsupported_material_claims == ["Teams improved conversion by 25%."]


def test_non_material_guidance_does_not_require_a_citation() -> None:
    report = build_evidence_report(
        "<p>Start by documenting the audience, owner, approval path, and next action.</p>"
    )
    assert report.status == "ready"
    assert report.claim_source_matrix == []


def test_audit_script_writes_manifest_without_rewriting_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "published"
    source_dir.mkdir()
    artifact = source_dir / "article.json"
    artifact.write_text(
        json.dumps(
            {
                "slug": "article",
                "canonical_url": "https://example.com/insights/article",
                "body_html": "<p>Teams improved conversion by 25%.</p>",
            }
        )
    )
    before = artifact.read_bytes()
    output = tmp_path / "reports" / "evidence-remediation.json"

    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "audit-evidence.py"),
            "--source-dir",
            str(source_dir),
            "--output",
            str(output),
        ],
        check=True,
    )

    assert artifact.read_bytes() == before
    manifest = json.loads(output.read_text())
    assert manifest["status_counts"]["unsupported"] == 1
    assert manifest["remediation"][0]["slug"] == "article"
