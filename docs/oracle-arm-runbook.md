# Oracle ARM Runbook (MVP)

## 설치 순서

1. 시스템 패키지/Playwright 의존성 설치
   ```bash
   ./scripts/install_playwright_arm.sh
   ```
2. Playwright 런타임 점검
   ```bash
   ./scripts/verify_playwright_arm.sh
   ```
3. API 서비스 등록
   ```bash
   ./scripts/install_systemd_services.sh /opt/iis-core-engine iis /opt/iis-core-engine/.venv/bin
   sudo systemctl start iis-core-api.service
   ```

## 운영 점검

- `systemctl status iis-core-api`
- `/healthz` 응답 확인
- session API(`/api/v1/sessions/*`) 응답 확인

## 롤백

- 서비스 중지/비활성화
  ```bash
  sudo systemctl disable --now iis-core-api.service
  ```
- 이전 배포 디렉토리로 심볼릭 링크/서비스 WorkingDirectory 복원
