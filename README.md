# iis-core-engine (ForgeMind + ForgeFlow)

Python FastAPI + LangGraph scaffolding for IIS multi-agent automation.

## Architecture

- **API process**: receives trigger and query requests
- **Worker process**: polls queued pipelines and executes LangGraph nodes
- **Queue source**: `admin_config` table in Supabase (fallback: in-memory)
- **Pipeline nodes**: Trigger → Architect → Stylist → Builder ↔ Sentinel (max 3 loops) → Publisher → Echo

Queue decision (MVP lock):
- `admin_config` is used as both trigger audit table and worker queue.
- No separate queue table is introduced in MVP to keep operational complexity low.

## Endpoints

- `POST /api/v1/pipelines/trigger`
- `GET /api/v1/pipelines/{pipeline_id}`
- `GET /api/v1/pipelines/{pipeline_id}/logs`
- `POST /api/v1/pipelines/{pipeline_id}/approvals`
- `POST /api/v1/telegram/webhook`
- `GET /healthz`

`INTERNAL_API_TOKEN`이 설정되면 `pipelines` 엔드포인트는 Bearer 토큰이 필요합니다.

## Telegram commands

- `/run <keyword>`: queue pipeline with `trigger_source=telegram`
- `/status <pipeline_id>`: fetch current status

Guardrails:
- Empty `TELEGRAM_ALLOWED_CHAT_IDS` = deny all chats by default
- Optional `TELEGRAM_WEBHOOK_SECRET` for webhook signature check
- Trigger keyword is normalized + validated (`TRIGGER_MIN_KEYWORD_LENGTH`, `TRIGGER_FORBIDDEN_KEYWORDS`)

## Manual approval mode (Studio Console)

- Trigger payload supports `execution_mode=manual`.
- In manual mode, pipeline pauses at approvable stages and stores `waiting_for_stage`.
- Resume with `POST /api/v1/pipelines/{pipeline_id}/approvals` body `{ "stage": "plan|style|build|qa|publish|echo" }`.
- Approval clears wait state and returns job to queued status for worker pickup.

## Publish flow

- Publisher uploads artifact HTML to Supabase Storage bucket
- Publisher upserts active row in `games_metadata`
- Publisher syncs `games/<slug>/index.html` and `manifest/games.json` to Repo3 via GitHub API (allowlist enforced)

## Payload contracts (MVP)

- `gdd`: `title`, `genre`, `objective`, `visual_style`
- `design_spec`: `visual_style`, `palette`, `hud`, `viewport_width`, `viewport_height`, `safe_area_padding`, `min_font_size_px`, `text_overflow_policy`, `typography`, `thumbnail_concept`
- `build_artifact`: `game_slug`, `game_name`, `game_genre`, `artifact_path`, `artifact_html`, `leaderboard_contract`

## Run (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# terminal 1
./scripts/run_api.sh

# terminal 2
./scripts/run_worker.sh
```

## Security notes

- Never expose `SUPABASE_SERVICE_ROLE_KEY` outside Repo1 runtime.
- External calls use timeout/retry defaults (`HTTP_TIMEOUT_SECONDS`, `HTTP_MAX_RETRIES`).
- Telegram chat whitelist is mandatory for command execution.
- X posting quota guardrail: `X_POSTS_PER_GAME_PER_DAY` + `X_DAILY_STOP_ON_ERROR` (per-day failure lock).
- Archive writes are restricted by allowlisted paths only.
- QA applies smoke check + deterministic quality gate (`QA_MIN_QUALITY_SCORE`).

## ARM note (Oracle Cloud Always Free)

```bash
./scripts/install_playwright_arm.sh
./scripts/verify_playwright_arm.sh
```

systemd service templates:

- `deploy/systemd/iis-core-api.service.tmpl`
- `deploy/systemd/iis-core-worker.service.tmpl`
- installer: `./scripts/install_systemd_services.sh`

운영 문서:

- `docs/oracle-arm-runbook.md`
- `docs/telegram-operations.md`
