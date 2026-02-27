#!/usr/bin/env bash
set -euo pipefail

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"
    return
  fi

  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  echo "Python 3.11+ is required. Install python3.11 or set PYTHON_BIN." >&2
  exit 1
}

PY_BIN="$(resolve_python_bin)"
"${PY_BIN}" - <<'PY'
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
