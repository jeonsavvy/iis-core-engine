# IIS Core Engine

IIS 전체 서비스에서 게임 생성, 수정, 검수, 퍼블리시를 처리하는 FastAPI 백엔드입니다.

## 이 저장소가 맡는 책임

- 세션 기반 게임 제작 API 제공
- 프롬프트 실행과 비동기 run 상태 관리
- 이슈 제기, 수정안 생성, 수정 반영 흐름 관리
- 퍼블리시 승인과 공개 메타데이터 기록
- `iis-games-archive` 저장소 GitOps 동기화
- 런타임 health와 세션 스키마 일치 여부 검증

## 빠른 시작

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
./scripts/run_api.sh
```

기본 확인 경로:

- `GET /healthz`
- `GET /api/v1/health`
- `GET /api/v1/sessions`

## 요청 처리 흐름

1. 포털이 세션을 생성합니다.
2. 사용자가 프롬프트를 보내면 run이 큐잉되고 상태가 기록됩니다.
3. 코드 생성, 비주얼 검수, 플레이 테스트 결과가 세션 이벤트와 대화 기록에 남습니다.
4. 사용자는 이슈를 등록하고 수정안을 검토한 뒤 반영할 수 있습니다.
5. 퍼블리시 승인 후 HTML, 공개 메타데이터, 썸네일, 아카이브 저장소가 함께 갱신됩니다.

## 주요 API 범위

### Health

- `GET /healthz`
- `GET /api/v1/health`

### Sessions

- `POST /api/v1/sessions`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/cancel`
- `GET /api/v1/sessions/{session_id}/conversation`
- `GET /api/v1/sessions/{session_id}/events`
- `POST /api/v1/sessions/{session_id}/plan-draft`
- `POST /api/v1/sessions/{session_id}/prompt`
- `GET /api/v1/sessions/{session_id}/runs/{run_id}`
- `POST /api/v1/sessions/{session_id}/runs/{run_id}/cancel`

### Issue review

- `POST /api/v1/sessions/{session_id}/issues`
- `GET /api/v1/sessions/{session_id}/issues/latest`
- `POST /api/v1/sessions/{session_id}/issues/{issue_id}/propose-fix`
- `POST /api/v1/sessions/{session_id}/issues/{issue_id}/apply-fix`

### Publish and game admin

- `POST /api/v1/sessions/{session_id}/approve-publish`
- `POST /api/v1/sessions/{session_id}/publish`
- `GET /api/v1/sessions/{session_id}/publish-thumbnail-candidates`
- `DELETE /api/v1/games/{game_id}`

## 핵심 환경변수

전체 샘플은 `.env.example` 에 있습니다.

| 변수 | 설명 |
| --- | --- |
| `APP_ENV` | production 여부를 결정합니다. |
| `INTERNAL_API_TOKEN` | 포털이 호출하는 내부 Bearer 토큰입니다. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | 세션, 메타데이터, 스토리지 접근에 사용합니다. |
| `SUPABASE_STORAGE_BUCKET` | 퍼블리시 결과를 올리는 버킷입니다. |
| `PUBLIC_GAMES_BASE_URL` | 공개 산출물 URL fallback 기준입니다. |
| `PUBLIC_PORTAL_BASE_URL` | 퍼블리시 후 플레이 URL을 만들 때 사용합니다. |
| `VERTEX_PROJECT_ID` / `VERTEX_LOCATION` | Vertex 호출 기본 설정입니다. |
| `GEMINI_PRO_MODEL` / `GEMINI_FLASH_MODEL` | 생성 작업 모델 이름입니다. |
| `GITHUB_TOKEN` / `GITHUB_ARCHIVE_REPO` | 아카이브 저장소 커밋에 사용합니다. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ALLOWED_CHAT_IDS` | 출시 알림 전송에 사용합니다. |
| `PLAYWRIGHT_REQUIRED` | 퍼블리시 전 런타임 검증 강제 여부입니다. |
| `HTTP_TIMEOUT_SECONDS` / `HTTP_MAX_RETRIES` | 외부 호출 정책입니다. |

## Supabase SQL 파일 정리 기준

현재 운영 경로 기준 주요 파일:

- 기본 스키마: `supabase/schema.sql`
- 세션 전환 기준 스키마: `supabase/session_first_big_bang.sql`
- 세션 협업/용량/퍼블리시 업그레이드:
  - `supabase/session_async_collab_upgrade.sql`
  - `supabase/session_capacity_upgrade.sql`
  - `supabase/session_publish_copy_upgrade.sql`
  - `supabase/app_role_creator_upgrade.sql`
- 공개 카탈로그/자산/로그 보조 스키마:
  - `supabase/public_catalog_upgrade.sql`
  - `supabase/asset_registry.sql`
  - `supabase/log_retention.sql`

보존 중인 이력성 파일:

- `supabase/modular_gen_core.sql`
- `supabase/pipeline_v2_breaking.sql`
- `supabase/pipeline_v2_repair.sql`

이 세 파일은 현재 기본 부트스트랩 경로에는 포함하지 않지만, 과거 운영 이력 추적과 복구 근거를 위해 저장소에 유지합니다.

## 검증

```bash
ruff check app tests
mypy
python -m compileall -q app tests
PYTHONPATH=. pytest -q -s
```

## 배포와 운영 문서

- CI: `.github/workflows/backend-ci.yml`
- 배포: `.github/workflows/deploy-backend.yml`
- 원격 배포 스크립트: `scripts/deploy_remote.sh`
- systemd 템플릿: `deploy/systemd/iis-core-api.service.tmpl`
- 운영 문서:
  - `docs/oracle-arm-runbook.md`
  - `docs/scaffold-v3-migration.md`
  - `docs/telegram-operations.md`

## 공개 저장소 기준

- 비밀값은 `.env` 에만 두고 커밋하지 않습니다.
- 퍼블리시 결과물은 이 저장소에 직접 저장하지 않고 `iis-games-archive` 로 보냅니다.
- 포털이 사용하는 내부 API 계약은 유지하되, 운영 전용 자격증명은 코드에 넣지 않습니다.

## License

MIT
