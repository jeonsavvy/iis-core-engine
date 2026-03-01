#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/iis-core-engine}"
BRANCH="${2:-main}"
API_SERVICE="${API_SERVICE:-iis-core-api.service}"
WORKER_SERVICE="${WORKER_SERVICE:-iis-core-worker.service}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-20}"
HEALTHCHECK_RETRY_DELAY="${HEALTHCHECK_RETRY_DELAY:-2}"

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      command -v "${PYTHON_BIN}"
      return
    fi
    echo "PYTHON_BIN does not exist on PATH: ${PYTHON_BIN}" >&2
    exit 1
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

  echo "python runtime is required (python3.11 preferred)." >&2
  exit 1
}

resolve_venv_dir() {
  if [[ -n "${VENV_DIR:-}" ]]; then
    echo "${VENV_DIR}"
    return
  fi
  if [[ -x "${APP_DIR}/.venv311/bin/python" ]]; then
    echo "${APP_DIR}/.venv311"
    return
  fi
  if [[ -x "${APP_DIR}/.venv/bin/python" ]]; then
    echo "${APP_DIR}/.venv"
    return
  fi
  echo "${APP_DIR}/.venv311"
}

run_healthcheck() {
  curl --fail --silent --show-error \
    --max-time 10 \
    --retry "${HEALTHCHECK_RETRIES}" \
    --retry-delay "${HEALTHCHECK_RETRY_DELAY}" \
    --retry-connrefused \
    "${HEALTHCHECK_URL}" >/dev/null
}

PY_BIN="$(resolve_python_bin)"
VENV_DIR="$(resolve_venv_dir)"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required"
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required"
  exit 1
fi

cd "${APP_DIR}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "APP_DIR is not a git repository: ${APP_DIR}"
  exit 1
fi

if ! git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  git checkout -b "${BRANCH}" "origin/${BRANCH}"
else
  git checkout "${BRANCH}"
fi

PREVIOUS_COMMIT="$(git rev-parse HEAD)"
git fetch --prune origin "${BRANCH}"
TARGET_COMMIT="$(git rev-parse "origin/${BRANCH}")"

if [[ "${PREVIOUS_COMMIT}" == "${TARGET_COMMIT}" ]]; then
  echo "Already up to date: ${TARGET_COMMIT}"
else
  git pull --ff-only origin "${BRANCH}"
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PY_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r requirements.txt
"${VENV_DIR}/bin/python" --version

sudo systemctl restart "${API_SERVICE}" "${WORKER_SERVICE}"

if ! run_healthcheck; then
  echo "Healthcheck failed. Rolling back to ${PREVIOUS_COMMIT}"
  git reset --hard "${PREVIOUS_COMMIT}"
  "${VENV_DIR}/bin/pip" install -r requirements.txt
  sudo systemctl restart "${API_SERVICE}" "${WORKER_SERVICE}"
  run_healthcheck
  echo "Rollback completed."
  exit 1
fi

echo "Deployment completed: ${TARGET_COMMIT}"
