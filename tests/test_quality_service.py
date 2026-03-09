from __future__ import annotations

import struct
import zlib

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


def _paeth_predictor(left: int, up: int, up_left: int) -> int:
    guess = left + up - up_left
    left_dist = abs(guess - left)
    up_dist = abs(guess - up)
    up_left_dist = abs(guess - up_left)
    if left_dist <= up_dist and left_dist <= up_left_dist:
        return left
    if up_dist <= up_left_dist:
        return up
    return up_left


def _read_png_center_rgb(png_bytes: bytes) -> tuple[int, int, int]:
    signature = b"\x89PNG\r\n\x1a\n"
    assert png_bytes.startswith(signature)

    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    compressed = bytearray()

    cursor = len(signature)
    while cursor < len(png_bytes):
        chunk_length = struct.unpack(">I", png_bytes[cursor : cursor + 4])[0]
        chunk_type = png_bytes[cursor + 4 : cursor + 8]
        chunk_data_start = cursor + 8
        chunk_data_end = chunk_data_start + chunk_length
        chunk_data = png_bytes[chunk_data_start:chunk_data_end]
        cursor = chunk_data_end + 4  # crc

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk_data)
            assert compression == 0
            assert filter_method == 0
            assert interlace == 0
            assert bit_depth == 8
            assert color_type in {2, 6}
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    bytes_per_pixel = 4 if color_type == 6 else 3
    stride = width * bytes_per_pixel
    decoded = zlib.decompress(bytes(compressed))
    rows: list[bytearray] = []
    offset = 0

    for _ in range(height):
        filter_type = decoded[offset]
        offset += 1
        scanline = bytearray(decoded[offset : offset + stride])
        offset += stride
        previous = rows[-1] if rows else bytearray(stride)

        if filter_type == 1:
            for index in range(bytes_per_pixel, stride):
                scanline[index] = (scanline[index] + scanline[index - bytes_per_pixel]) % 256
        elif filter_type == 2:
            for index in range(stride):
                scanline[index] = (scanline[index] + previous[index]) % 256
        elif filter_type == 3:
            for index in range(stride):
                left = scanline[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                scanline[index] = (scanline[index] + ((left + up) // 2)) % 256
        elif filter_type == 4:
            for index in range(stride):
                left = scanline[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                scanline[index] = (scanline[index] + _paeth_predictor(left, up, up_left)) % 256
        else:
            assert filter_type == 0

        rows.append(scanline)

    center_x = width // 2
    center_y = height // 2
    base = center_x * bytes_per_pixel
    row = rows[center_y]
    return row[base], row[base + 1], row[base + 2]


def test_capture_presentation_screenshot_waits_until_countdown_clears_without_hooks() -> None:
    service = QualityService(Settings(playwright_required=False, qa_smoke_timeout_seconds=8.0))

    screenshot = service.capture_presentation_screenshot(COUNTDOWN_CAPTURE_HTML)

    assert screenshot is not None
    center = _read_png_center_rgb(screenshot)

    assert center[0] > 200
    assert center[1] > 120
    assert center[2] < 120
