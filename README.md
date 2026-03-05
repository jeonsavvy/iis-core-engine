# IIS Core Engine (Session-First)

Session 기반 대화형 게임 생성 백엔드입니다.

## 핵심 경로
- `POST /api/v1/sessions`
- `GET /api/v1/sessions?status=&limit=`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/prompt`
- `GET /api/v1/sessions/{session_id}/events?cursor=&limit=`
- `POST /api/v1/sessions/{session_id}/publish`
- `POST /api/v1/sessions/{session_id}/cancel`
- `DELETE /api/v1/sessions/{session_id}`

모든 `/api/v1/sessions/*` 및 `/api/v1/games/*`는 `INTERNAL_API_TOKEN` Bearer 검증을 사용합니다.
(토큰 미설정 시 비활성)

## 정책
- Session Store 미연결 시 세션 API는 **503**
- AI 미연결/실패 시 **Fail-Fast** (stub 반환 금지)
- 이벤트/대화/저장 payload는 **Always Redacted**
- 텔레그램은 **publish success 알림만** 전송

## 로컬 실행
```bash
python -m venv .venv311
source .venv311/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

## 검증
```bash
ruff check app tests
mypy app tests
PYTHONPATH=. pytest -q -s
```

## DB 마이그레이션
- Big-Bang 전환 SQL: `supabase/session_first_big_bang.sql`
- 이 스크립트는 레거시 pipeline 테이블을 hard drop 합니다.
