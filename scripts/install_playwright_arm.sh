#!/usr/bin/env bash
set -euo pipefail

# Oracle Cloud Ubuntu ARM safe baseline.
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

python -m playwright install chromium
