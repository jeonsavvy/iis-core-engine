#!/usr/bin/env bash
set -euo pipefail

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"
    return
  fi

  if [[ -x ".venv311/bin/python" ]]; then
    echo ".venv311/bin/python"
    return
  fi
  if [[ -x ".venv/bin/python" ]]; then
    echo ".venv/bin/python"
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

  echo "Python 3.11+ is required. Install python3.11 or set PYTHON_BIN." >&2
  exit 1
}

PY_BIN="$(resolve_python_bin)"
exec "${PY_BIN}" -m app.workers.pipeline_worker
