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

# Ubuntu ARM server baseline for Playwright dependencies.
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  libnss3 \
  libatk-bridge2.0-0 \
  libxkbcommon0 \
  libgtk-3-0 \
  libasound2t64 \
  libgbm1 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libxshmfence1 \
  libx11-xcb1 \
  libxext6 \
  libxrender1

PY_BIN="$(resolve_python_bin)"
"${PY_BIN}" -m playwright install chromium
