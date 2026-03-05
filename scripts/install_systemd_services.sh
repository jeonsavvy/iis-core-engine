#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/iis-core-engine}"
RUN_USER="${2:-iis}"
if [[ -n "${3:-}" ]]; then
  VENV_BIN="$3"
elif [[ -x "${APP_DIR}/.venv311/bin/python" ]]; then
  VENV_BIN="${APP_DIR}/.venv311/bin"
else
  VENV_BIN="${APP_DIR}/.venv/bin"
fi
SYSTEMD_DIR="/etc/systemd/system"

render_and_install() {
  local template_file="$1"
  local output_name="$2"

  sed \
    -e "s|__IIS_USER__|${RUN_USER}|g" \
    -e "s|__IIS_APP_DIR__|${APP_DIR}|g" \
    -e "s|__IIS_VENV_BIN__|${VENV_BIN}|g" \
    "$template_file" | sudo tee "${SYSTEMD_DIR}/${output_name}" >/dev/null
}

render_and_install "deploy/systemd/iis-core-api.service.tmpl" "iis-core-api.service"

services=("iis-core-api.service")
if [[ -f "deploy/systemd/iis-core-worker.service.tmpl" ]]; then
  render_and_install "deploy/systemd/iis-core-worker.service.tmpl" "iis-core-worker.service"
  services+=("iis-core-worker.service")
fi

sudo systemctl daemon-reload
sudo systemctl enable "${services[@]}"

echo "Installed services:"
for service in "${services[@]}"; do
  sudo systemctl status "${service}" --no-pager || true
done
