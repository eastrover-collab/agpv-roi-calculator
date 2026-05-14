"""assumptions.yaml 로더 — UI 입력의 기본값 제공."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_assumptions(path: str | Path = None) -> Dict[str, Any]:
    """assumptions.yaml 읽어 dict로 반환."""
    if path is None:
        path = Path(__file__).parent.parent / "assumptions.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
