from app.core.config import Settings
from app.services.quality_gates import (
    evaluate_artifact_contract,
    evaluate_quality_contract,
    evaluate_visual_gate,
)


def test_evaluate_quality_contract_accepts_valid_runtime_contract() -> None:
    settings = Settings(qa_min_quality_score=40)
    html = """
    <html>
      <head><meta name="viewport" content="width=device-width"></head>
      <body class="overflow-guard" data-overflow-policy="clamp">
        <canvas id="game"></canvas>
        <script>
          window.__iis_game_boot_ok = true;
          window.IISLeaderboard = {};
          const style = "--safe-area-padding: 8px";
          function update() {}
          function draw() {}
          requestAnimationFrame(() => {});
          document.addEventListener("keydown", () => {});
          const overlay = "game over";
        </script>
      </body>
    </html>
    """

    result = evaluate_quality_contract(settings, html)

    assert result.ok is True
    assert result.score >= result.threshold


def test_evaluate_visual_gate_fails_without_metrics() -> None:
    settings = Settings(qa_min_visual_score=45)

    result = evaluate_visual_gate(settings, None)

    assert result.ok is False
    assert "visual_metrics_missing" in result.failed_checks


def test_evaluate_artifact_contract_requires_hybrid_engine_bundle() -> None:
    settings = Settings(qa_min_artifact_contract_score=70)
    manifest = {"bundle_kind": "single_html", "files": [{"path": "index.html"}]}

    result = evaluate_artifact_contract(settings, manifest, art_direction_contract={})

    assert result.ok is False
    assert "unsupported_bundle_kind" in result.failed_checks

