#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/iis-core-engine}"
BRANCH="${2:-main}"
API_SERVICE="${API_SERVICE:-iis-core-api.service}"
WORKER_SERVICE="${WORKER_SERVICE:-}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-20}"
HEALTHCHECK_RETRY_DELAY="${HEALTHCHECK_RETRY_DELAY:-2}"
SESSION_SCHEMA_EXPECTED="${SESSION_SCHEMA_EXPECTED:-v1}"

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

dump_service_diagnostics() {
  local service_name="$1"
  echo "===== systemd status: ${service_name} ====="
  sudo systemctl --no-pager --full status "${service_name}" || true
  echo "===== journal tail: ${service_name} ====="
  sudo journalctl --no-pager -u "${service_name}" -n 120 || true
}

ensure_git_writable() {
  if [[ -w ".git" && -w ".git/refs" ]]; then
    return
  fi
  echo "Repairing .git ownership/permissions for deploy user"
  sudo chown -R "$(id -u):$(id -g)" .git
  sudo find .git -type d -exec chmod u+rwx {} \;
  sudo find .git -type f -exec chmod u+rw {} \;
}

verify_health_signature() {
  local expected_sha="$1"
  local raw
  raw="$(curl --fail --silent --show-error --max-time 10 "${HEALTHCHECK_URL}")"
  HEALTH_JSON="${raw}" EXPECTED_SHA="${expected_sha}" EXPECTED_SCHEMA="${SESSION_SCHEMA_EXPECTED}" "${PY_BIN}" - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["HEALTH_JSON"])
expected_sha = os.environ["EXPECTED_SHA"].strip().lower()
expected_schema = os.environ["EXPECTED_SCHEMA"].strip()
actual_sha = str(payload.get("git_sha", "")).strip().lower()
actual_schema = str(
    payload.get("session_schema_version")
    or payload.get("pipeline_schema_version")
    or ""
).strip()

if actual_sha in {"", "unknown"}:
    print("health_git_sha_unknown: unable to verify deployed commit via /healthz git_sha", file=sys.stderr)
elif expected_sha and not actual_sha.startswith(expected_sha):
    raise SystemExit(f"health_sha_mismatch expected={expected_sha} actual={actual_sha}")
if expected_schema and actual_schema != expected_schema:
    raise SystemExit(f"health_schema_mismatch expected={expected_schema} actual={actual_schema}")
PY
}

restart_services() {
  sudo systemctl restart "${API_SERVICE}"
  if [[ -n "${WORKER_SERVICE}" ]]; then
    sudo systemctl restart "${WORKER_SERVICE}"
  fi
}

upsert_env_value() {
  local file_path="$1"
  local key="$2"
  local value="$3"
  if [[ ! -f "${file_path}" ]]; then
    return
  fi
  "${PY_BIN}" - "${file_path}" "${key}" "${value}" <<'PY'
import pathlib
import sys

file_path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

lines = file_path.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="
updated = []
replaced = False
for line in lines:
    if line.startswith(prefix):
        updated.append(f"{prefix}{value}")
        replaced = True
    else:
        updated.append(line)
if not replaced:
    updated.append(f"{prefix}{value}")
file_path.write_text("\n".join(updated).rstrip("\n") + "\n", encoding="utf-8")
PY
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

ensure_git_writable

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

upsert_env_value "${APP_DIR}/.env" "GIT_SHA" "${TARGET_COMMIT}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PY_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r requirements.txt
"${VENV_DIR}/bin/python" --version

restart_services

if ! run_healthcheck; then
  echo "Healthcheck failed on target commit ${TARGET_COMMIT}. Capturing diagnostics."
  dump_service_diagnostics "${API_SERVICE}"
  if [[ -n "${WORKER_SERVICE}" ]]; then
    dump_service_diagnostics "${WORKER_SERVICE}"
  fi
  echo "Healthcheck failed. Rolling back to ${PREVIOUS_COMMIT}"
  git reset --hard "${PREVIOUS_COMMIT}"
  "${VENV_DIR}/bin/pip" install -r requirements.txt
  restart_services
  run_healthcheck
  echo "Rollback completed."
  exit 1
fi

EXPECTED_SHA_SHORT="$(echo "${TARGET_COMMIT}" | cut -c1-12)"
verify_health_signature "${EXPECTED_SHA_SHORT}"

echo "Deployment completed: ${TARGET_COMMIT}"
