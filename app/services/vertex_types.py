from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VertexGenerationResult:
    payload: dict[str, Any]
    meta: dict[str, Any]
