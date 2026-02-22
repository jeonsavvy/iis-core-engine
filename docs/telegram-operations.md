# Telegram 운영 절차서 (MVP)

## 1) 기본 정책

- 허용된 chat id(`TELEGRAM_ALLOWED_CHAT_IDS`)만 실행
- 비허용 chat의 `/run` 요청은 큐 등록 대신 `status=skipped` 감사 엔트리로 기록
- 명령어:
  - `/run <keyword>`
  - `/status <pipeline_id>`

## 2) 환경변수

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS` (쉼표 구분)
- `TELEGRAM_WEBHOOK_SECRET` (권장)

## 3) Webhook 모드

1. API 엔드포인트 준비
   - `POST /api/v1/telegram/webhook`
2. Telegram webhook 등록
   - secret token을 `TELEGRAM_WEBHOOK_SECRET`와 동일하게 설정
3. API 로그에서 403 여부 확인
   - secret mismatch 시 403

## 4) 장애 대응

- 잘못된 chat 유입 급증:
  - `TELEGRAM_ALLOWED_CHAT_IDS` 축소
  - 필요 시 webhook 일시 해제
- Bot token 유출 의심:
  - 즉시 token revoke/reissue
  - `.env` 교체 후 API 재시작
- Supabase 또는 worker 장애:
  - Telegram은 접수만 하고 큐 적재 실패를 반환할 수 있음
  - `admin_config` insert 에러 우선 확인

## 5) 점검 체크리스트

- `/run` 실행 시 `trigger_source='telegram'` 확인
- `/status`에서 pipeline 상태 회신 확인
- 차단 chat에서 `telegram_chat_not_allowed` 감사 엔트리 확인
