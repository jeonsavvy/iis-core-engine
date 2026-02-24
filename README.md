# iis-core-engine (ForgeMind + ForgeFlow)

IIS 멀티에이전트 게임 제작 파이프라인의 코어 엔진입니다.  
Python FastAPI(API) + Worker(큐 처리) 구조로 동작합니다.

## 아키텍처 요약

- **API 프로세스**: 트리거/조회/승인 요청 수신
- **Worker 프로세스**: 큐를 폴링하며 파이프라인 실행
- **큐 소스**: Supabase `admin_config` 테이블 (MVP에서는 큐+감사로그 겸용)
- **파이프라인 노드**
  - Trigger → Architect → Stylist → Builder ↔ Sentinel(최대 3회 재시도) → Publisher → Echo

## 주요 엔드포인트

- `POST /api/v1/pipelines/trigger`
- `GET /api/v1/pipelines/{pipeline_id}`
- `GET /api/v1/pipelines/{pipeline_id}/logs`
- `POST /api/v1/pipelines/{pipeline_id}/approvals`
- `POST /api/v1/pipelines/{pipeline_id}/controls`
- `POST /api/v1/telegram/webhook`
- `GET /healthz`

`INTERNAL_API_TOKEN`이 설정되면 `pipelines` 계열 엔드포인트는 Bearer 토큰이 필요합니다.

## Telegram 명령어 (실연동 대상)

- `/run <keyword>`: `trigger_source=telegram`로 파이프라인 큐 등록
- `/status <pipeline_id>`: 현재 상태 조회

가드레일:
- `TELEGRAM_ALLOWED_CHAT_IDS` 비어있으면 기본값은 **전부 거부**
- `TELEGRAM_WEBHOOK_SECRET` 선택적으로 사용 가능
- 트리거 키워드는 정규화/금칙어 검사 수행

## 수동 승인 모드 (Studio Console)

- 트리거 payload에서 `execution_mode=manual` 지원
- 수동 모드에서는 승인 가능한 단계에서 일시정지 후 `waiting_for_stage` 저장
- 승인 재개 API:
  - `POST /api/v1/pipelines/{pipeline_id}/approvals`
  - body: `{ "stage": "plan|style|build|qa|publish|echo" }`

## Publish 플로우

- Supabase Storage 버킷에 게임 HTML 업로드
- `games_metadata` 활성 행 upsert
- Repo3(`iis-games-archive`)에 `games/<slug>/index.html`, `manifest/games.json` 동기화 (allowlist 강제)

## Payload 계약 (MVP)

- `gdd`: `title`, `genre`, `objective`, `visual_style`
- `design_spec`: `visual_style`, `palette`, `hud`, `viewport_width`, `viewport_height`, `safe_area_padding`, `min_font_size_px`, `text_overflow_policy`, `typography`, `thumbnail_concept`
- `build_artifact`: `game_slug`, `game_name`, `game_genre`, `artifact_path`, `artifact_html`, `leaderboard_contract`

## 로컬 실행

실행 컨텍스트 표기 규칙:
- `[LOCAL WSL]` : 사용자 PC의 WSL/로컬 터미널
- `[EC2 SSH]` : AWS EC2에 SSH 접속한 셸

```bash
# [LOCAL WSL]
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# [LOCAL WSL] 터미널 1 (API)
./scripts/run_api.sh

# [LOCAL WSL] 터미널 2 (Worker)
./scripts/run_worker.sh
```

## 보안/운영 메모

- `SUPABASE_SERVICE_ROLE_KEY`는 **Repo1 서버 런타임 전용**
- 외부 호출은 timeout/retry 기본값 사용 (`HTTP_TIMEOUT_SECONDS`, `HTTP_MAX_RETRIES`)
- Telegram 실행은 chat whitelist 필수
- X 포스팅은 일일 쿼터 + 실패 시 당일 중단 정책 적용
- Archive 쓰기는 allowlist 경로만 허용
- QA는 Playwright 스모크체크 + 품질 게이트(`QA_MIN_QUALITY_SCORE`) 적용

## GitHub Actions 자동 배포 (Backend)

`main` 브랜치에 push되면 아래 순서로 자동 실행됩니다.

1. `pytest -q` 검증
2. SSH 원격 배포 실행
3. 서비스 재시작 + `/healthz` 확인
4. 헬스체크 실패 시 직전 커밋으로 자동 롤백

워크플로우 파일:
- `.github/workflows/deploy-backend.yml`

원격 배포 스크립트:
- `scripts/deploy_remote.sh`

필수 GitHub Secrets:
- `BACKEND_DEPLOY_HOST` (예: `1.2.3.4`)
- `BACKEND_DEPLOY_USER` (예: `iis`)
- `BACKEND_DEPLOY_SSH_KEY` (PEM private key 원문)

선택 GitHub Secrets:
- `BACKEND_DEPLOY_PORT` (기본 `22`)
- `BACKEND_DEPLOY_PATH` (기본 `/opt/iis-core-engine`)

서버 사전 조건:
- 저장소가 `BACKEND_DEPLOY_PATH` 경로에 clone되어 있을 것
- `sudo systemctl restart iis-core-api.service iis-core-worker.service` 권한이 배포 사용자에 허용되어 있을 것
- `.env`, systemd unit 설치가 완료되어 있을 것

## ARM(Oracle/AWS Graviton) 참고

```bash
# [EC2 SSH] 또는 ARM 서버 셸
./scripts/install_playwright_arm.sh
./scripts/verify_playwright_arm.sh
```

systemd 템플릿:
- `deploy/systemd/iis-core-api.service.tmpl`
- `deploy/systemd/iis-core-worker.service.tmpl`
- 설치 스크립트: `./scripts/install_systemd_services.sh`

운영 문서:
- `docs/oracle-arm-runbook.md`
- `docs/telegram-operations.md`
