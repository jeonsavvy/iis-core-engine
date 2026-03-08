# IIS Core Engine

Session-first 비동기 게임 생성·수정·퍼블리시 백엔드입니다.  
FastAPI 위에서 세션 편집 루프, Vertex 기반 생성/QA, Supabase 영속화, 공개 퍼블리시, 아카이브 GitOps를 담당합니다.

## Quick Start

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
./scripts/run_api.sh
```

기본 주소:

- App health: `GET /healthz`
- API v1 health: `GET /api/v1/health`
- API base: `/api/v1`

## 이 레포가 담당하는 것

- FastAPI 기반 세션 편집 API
- Vertex 기반 `CodegenAgent` / `VisualQAAgent` / `PlaytesterAgent`
- Supabase 기반 세션, 대화, 이벤트, 실행 상태, 퍼블리시 이력 저장
- Supabase Storage + `games_metadata` 퍼블리시
- `iis-games-archive` 저장소 GitOps 동기화
- Telegram 런치/마케팅 알림 전송
- 배포 시 health signature(`git_sha`, `session_schema_version`) 검증

## 아키텍처 개요

- Entry point: `app/main.py`
- API router: `app/api/v1/router.py`, `app/api/v1/session_router.py`
- Session persistence: `app/services/session_store.py`
- Publish pipeline: `app/services/session_publisher.py`, `app/services/publisher_service.py`
- Archive GitOps: `app/services/github_service.py`
- Runtime health / schema guard: `app/core/runtime_health.py`

모든 `/api/v1/sessions/*` 및 `/api/v1/games/*`는 `INTERNAL_API_TOKEN`이 설정된 경우 Bearer 인증을 강제합니다.  
`APP_ENV=production`에서는 `INTERNAL_API_TOKEN` 미설정 시 서버가 fail-fast로 기동 실패합니다.

## 주요 정책

- Session Store 미연결 시 세션 API는 `503`
- Vertex/AI 실패 시 stub 반환 없이 fail-fast
- 대화/이벤트/퍼블리시 메타데이터는 저장 전 redaction 적용
- 외부 호출은 timeout/retry 정책을 사용
- Telegram은 운영 명령 채널이 아니라 출시/마케팅 알림 채널로 동작

## API Surface

### Health

- `GET /healthz`
- `GET /api/v1/health`

### Sessions

- `POST /api/v1/sessions`
- `GET /api/v1/sessions?status=&limit=`
- `GET /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/cancel`
- `GET /api/v1/sessions/{session_id}/conversation?limit=`
- `GET /api/v1/sessions/{session_id}/events?cursor=&limit=`
- `POST /api/v1/sessions/{session_id}/plan-draft`
- `POST /api/v1/sessions/{session_id}/prompt`
- `GET /api/v1/sessions/{session_id}/runs/{run_id}`
- `POST /api/v1/sessions/{session_id}/runs/{run_id}/cancel`

### Human-in-the-loop issue flow

- `POST /api/v1/sessions/{session_id}/issues`
- `GET /api/v1/sessions/{session_id}/issues/latest`
- `POST /api/v1/sessions/{session_id}/issues/{issue_id}/propose-fix`
- `POST /api/v1/sessions/{session_id}/issues/{issue_id}/apply-fix`

### Publish / game admin

- `POST /api/v1/sessions/{session_id}/approve-publish`
- `POST /api/v1/sessions/{session_id}/publish`
- `DELETE /api/v1/games/{game_id}`

Portal BFF는 `X-IIS-Actor-Id`, `X-IIS-Actor-Role` 헤더를 전달해 세션/퍼블리시 행위자를 기록합니다.

## 환경변수

전체 샘플은 `.env.example`를 기준으로 관리합니다. 현재 코드 기준 핵심 변수는 아래와 같습니다.

| 변수 | 용도 |
| --- | --- |
| `APP_ENV` | `production`일 때 내부 토큰 강제 |
| `INTERNAL_API_TOKEN` | Portal → Core 내부 API Bearer 인증 |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | 세션/퍼블리시/스토리지 관리 |
| `SUPABASE_STORAGE_BUCKET` | 퍼블리시 대상 버킷 (`games`) |
| `PUBLIC_GAMES_BASE_URL` | 스토리지 public URL fallback |
| `PUBLIC_PORTAL_BASE_URL` | 퍼블리시 후 `/play/<slug>` 링크 생성 |
| `VERTEX_PROJECT_ID` / `VERTEX_LOCATION` | Vertex 모델 호출 |
| `GEMINI_PRO_MODEL` / `GEMINI_FLASH_MODEL` | 생성/보조 모델 선택 |
| `GITHUB_TOKEN` / `GITHUB_ARCHIVE_REPO` | `iis-games-archive` GitOps |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ALLOWED_CHAT_IDS` | 런치 알림 |
| `PLAYWRIGHT_REQUIRED` | 퍼블리시 전 smoke check 강제 여부 |
| `HTTP_TIMEOUT_SECONDS` / `HTTP_MAX_RETRIES` | 외부 호출 정책 |

## Supabase SQL

`supabase/` 폴더에 현재 운영 스키마와 업그레이드 스크립트가 있습니다.

- Baseline: `supabase/session_first_big_bang.sql`
- Async collaboration: `supabase/session_async_collab_upgrade.sql`
- Session capacity / publish copy / creator role:
  - `supabase/session_capacity_upgrade.sql`
  - `supabase/session_publish_copy_upgrade.sql`
  - `supabase/app_role_creator_upgrade.sql`
- Public catalog / asset / retention:
  - `supabase/public_catalog_upgrade.sql`
  - `supabase/asset_registry.sql`
  - `supabase/log_retention.sql`

`session_first_big_bang.sql`은 레거시 pipeline 계열 구조를 정리하는 컷오버 성격의 SQL이므로 적용 전 백업이 필요합니다.

## 검증

```bash
ruff check app tests
mypy
python -m compileall -q app tests
PYTHONPATH=. pytest -q -s
```

## 배포

- CI: `.github/workflows/backend-ci.yml`
- Main deploy: `.github/workflows/deploy-backend.yml`
- Remote deploy script: `scripts/deploy_remote.sh`
- systemd template: `deploy/systemd/iis-core-api.service.tmpl`

배포 스크립트는 대상 서버에서:

1. `git pull --ff-only`
2. `.env`에 `GIT_SHA` 주입
3. venv 보정 및 `requirements.txt` 설치
4. systemd 재시작
5. `/healthz` + schema signature 검증
6. 실패 시 이전 커밋으로 롤백

## 운영 문서

- `docs/oracle-arm-runbook.md`
- `docs/scaffold-v3-migration.md`
- `docs/telegram-operations.md`

## 선택적 수동 점검

아카이브 GitOps를 수동으로 검증할 때만 아래 스크립트를 사용합니다.

```bash
ENABLE_GITOPS_TEST=1 python test_gitops.py
```
