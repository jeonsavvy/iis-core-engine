#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("data:text/html,<html><body><h1>arm-ok</h1></body></html>", wait_until="domcontentloaded")
    title = page.text_content("h1")
    if title != "arm-ok":
        raise SystemExit("playwright_check_failed")
    browser.close()

print("playwright_arm_check_ok")
PY
