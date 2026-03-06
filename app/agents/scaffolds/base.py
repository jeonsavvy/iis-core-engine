from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaffoldSeed:
    key: str
    archetype: str
    engine_mode: str
    version: str
    html: str
    acceptance_tags: list[str]
    summary: str
