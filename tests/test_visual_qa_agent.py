from __future__ import annotations

import asyncio

from app.agents.visual_qa_agent import VisualQAAgent
from app.services.quality_types import SmokeCheckResult


class DummyVertex:
    pass


class DummyQuality:
    def __init__(self, smoke_result: SmokeCheckResult) -> None:
        self.smoke_result = smoke_result

    def run_smoke_check(self, html_content: str, *, artifact_files=None, entrypoint_path=None):  # type: ignore[no-untyped-def]
        return self.smoke_result


def test_visual_qa_treats_zero_metrics_as_inconclusive_when_runtime_boots() -> None:
    agent = VisualQAAgent(
        vertex_service=DummyVertex(),
        quality_service=DummyQuality(
            SmokeCheckResult(
                ok=True,
                screenshot_bytes=b"png",
                visual_metrics={
                    "canvas_width": 1280,
                    "canvas_height": 720,
                    "luminance_std": 0.0,
                    "non_dark_ratio": 0.0,
                    "edge_energy": 0.0,
                    "motion_delta": 0.0,
                    "color_bucket_count": 1,
                },
            )
        ),
    )

    result = asyncio.run(agent.evaluate(html_content="<html></html>"))
    assert result.ok is True
    assert result.issues == []
    assert result.score == 60
