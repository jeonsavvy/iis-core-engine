from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.core.config import Settings
from app.services.quality_service import QualityService


COUNTDOWN_CAPTURE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body { margin: 0; height: 100%; overflow: hidden; background: #020617; }
    #app { position: relative; width: 100%; height: 100%; }
    canvas { width: 100%; height: 100%; display: block; }
    #countdown {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font: 900 92px/1 Inter, system-ui, sans-serif;
      color: white;
      text-shadow: 0 0 24px rgba(255,255,255,0.35);
      pointer-events: none;
    }
  </style>
</head>
<body>
  <div id="app">
    <canvas id="game" width="1280" height="720"></canvas>
    <div id="countdown">3</div>
  </div>
  <script>
    window.__iis_game_boot_ok = true;
    const canvas = document.getElementById("game");
    const ctx = canvas.getContext("2d");
    const countdownEl = document.getElementById("countdown");
    const startAt = performance.now();

    function draw(now) {
      const elapsed = (now - startAt) / 1000;
      const countdown = Math.max(0, 2.8 - elapsed);
      if (countdown > 0) {
        countdownEl.textContent = String(Math.ceil(countdown));
        ctx.fillStyle = "#111827";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      } else {
        countdownEl.textContent = "";
        ctx.fillStyle = "#f59e0b";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
      requestAnimationFrame(draw);
    }

    requestAnimationFrame(draw);
  </script>
</body>
</html>
""".strip()


def test_capture_presentation_screenshot_waits_until_countdown_clears_without_hooks() -> None:
    service = QualityService(Settings(playwright_required=False, qa_smoke_timeout_seconds=8.0))

    screenshot = service.capture_presentation_screenshot(COUNTDOWN_CAPTURE_HTML)

    assert screenshot is not None
    with Image.open(BytesIO(screenshot)).convert("RGB") as image:
        center = image.getpixel((image.width // 2, image.height // 2))

    assert center[0] > 200
    assert center[1] > 120
    assert center[2] < 120
