#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/iis-core-engine}"
BRANCH="${2:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/.venv}"
API_SERVICE="${API_SERVICE:-iis-core-api.service}"
WORKER_SERVICE="${WORKER_SERVICE:-iis-core-worker.service}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"

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
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r requirements.txt

sudo systemctl restart "${API_SERVICE}" "${WORKER_SERVICE}"

if ! curl --fail --silent --show-error --max-time 10 --retry 3 --retry-delay 2 "${HEALTHCHECK_URL}" >/dev/null; then
  echo "Healthcheck failed. Rolling back to ${PREVIOUS_COMMIT}"
  git reset --hard "${PREVIOUS_COMMIT}"
  "${VENV_DIR}/bin/pip" install -r requirements.txt
  sudo systemctl restart "${API_SERVICE}" "${WORKER_SERVICE}"
  curl --fail --silent --show-error --max-time 10 --retry 3 --retry-delay 2 "${HEALTHCHECK_URL}" >/dev/null
  echo "Rollback completed."
  exit 1
fi

echo "Deployment completed: ${TARGET_COMMIT}"
