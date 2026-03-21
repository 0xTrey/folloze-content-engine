from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("config.yaml",):
        shutil.copy2(ROOT / name, tmp_path / name)
    for folder in ("content", "schema", "brand", "site"):
        shutil.copytree(ROOT / folder, tmp_path / folder, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            ".vercel",
            "logs",
            "site/dist",
        ),
    )
    return destination
