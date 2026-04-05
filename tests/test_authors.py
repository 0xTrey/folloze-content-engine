from __future__ import annotations

import importlib.util
from pathlib import Path

from authors import load_author_registry, primary_author_profile
from config import Config
from site_rendering import author_profile


ROOT = Path(__file__).resolve().parents[1]


def _load_audit_module():
    module_path = ROOT / "scripts" / "audit_authors.py"
    spec = importlib.util.spec_from_file_location("audit_authors", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_primary_author_registry_uses_enterprise_account_executive_role() -> None:
    default_author_id, authors = load_author_registry()

    assert default_author_id == "trey-harnden"
    assert authors[default_author_id].role_slug == "enterprise_account_executive"
    assert authors[default_author_id].role == "Enterprise Account Executive at Folloze"


def test_author_profile_exposes_registry_fields() -> None:
    config = Config.load(ROOT / "config.yaml")

    payload = author_profile(config)

    assert payload["author_id"] == "trey-harnden"
    assert payload["role_slug"] == "enterprise_account_executive"
    assert payload["role"] == "Enterprise Account Executive at Folloze"


def test_author_audit_flags_stale_generated_role(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    dist_page = repo / "site" / "dist" / "authors" / "trey-harnden" / "index.html"
    dist_page.parent.mkdir(parents=True)
    dist_page.write_text("<p>Trey Harnden</p><p>Account Executive at Folloze</p>")
    data_dir = repo / "data"
    data_dir.mkdir(parents=True)
    data_dir.joinpath("authors.json").write_text((ROOT / "data" / "authors.json").read_text())

    module = _load_audit_module()

    summary, findings = module.run_audit(repo)

    assert summary["role"] == "Enterprise Account Executive at Folloze"
    assert any("Account Executive at Folloze" in finding for finding in findings)


def test_primary_author_profile_returns_canonical_author() -> None:
    author = primary_author_profile()

    assert author.author_id == "trey-harnden"
    assert author.team == "sales"
