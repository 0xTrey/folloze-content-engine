from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_gap_evidence_packs.py"
PACK = ROOT / "content/review-only/persistent-gap-evidence-packs-2026-08.yaml"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_gap_evidence_packs", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_persistent_gap_evidence_packs_are_review_only_and_valid() -> None:
    validator = _load_validator()
    assert validator.validate_pack(PACK) == []
