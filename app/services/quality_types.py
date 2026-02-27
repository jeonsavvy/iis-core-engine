from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SmokeCheckResult:
    ok: bool
    reason: str | None = None
    console_errors: list[str] | None = None
    fatal_errors: list[str] | None = None
    non_fatal_warnings: list[str] | None = None
    screenshot_bytes: bytes | None = None
    visual_metrics: dict[str, float] | None = None


@dataclass
class QualityGateResult:
    ok: bool
    score: int
    threshold: int
    failed_checks: list[str]
    checks: dict[str, bool]


@dataclass
class GameplayGateResult:
    ok: bool
    score: int
    threshold: int
    failed_checks: list[str]
    checks: dict[str, bool]


@dataclass
class ArtifactContractResult:
    ok: bool
    score: int
    threshold: int
    failed_checks: list[str]
    checks: dict[str, bool]

