# Telegram 운영 절차서 (단일 관리자 제어)

## 1) 기본 정책

- Telegram 제어는 `TELEGRAM_CONTROL_ENABLED=true`일 때만 동작합니다.
- 제어 명령은 아래 **3가지 조건을 모두** 만족해야 실행됩니다.
  1. webhook secret 헤더(`X-Telegram-Bot-Api-Secret-Token`) 일치
  2. chat id가 `TELEGRAM_ALLOWED_CHAT_IDS`에 포함
  3. user id가 `TELEGRAM_ALLOWED_USER_IDS`에 포함
- 비인가 요청은 전부 차단되며 감사 로그(`admin_config`)로 남습니다.
- 위험 명령은 허용 상태(`TELEGRAM_ALLOW_DANGEROUS_COMMANDS=true`)에서 즉시 실행됩니다.

## 2) 환경변수

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` (**필수**, 없으면 webhook 503)
- `TELEGRAM_CONTROL_ENABLED` (`true/false`)
- `TELEGRAM_ALLOWED_CHAT_IDS` (쉼표 구분)
- `TELEGRAM_ALLOWED_USER_IDS` (쉼표 구분)
- `TELEGRAM_ALLOW_DANGEROUS_COMMANDS` (`true`일 때만 위험 명령 허용)

## 3) 명령어

- 일반 명령
  - `/run <keyword>`
  - `/status <pipeline_id>`
  - `/approve <pipeline_id> <stage>`
  - `/logs <pipeline_id> [limit]`
- 위험 명령 (허용 시 즉시 실행)
  - `/retry <pipeline_id>`
  - `/cancel <pipeline_id>`
  - `/reset <pipeline_id>`
  - `/delete_game <game_id>`

## 4) 위험 명령 실행 플로우

1. 운영자가 `/retry ...` 등 위험 명령 전송
2. 봇이 권한(chat/user) 검증
3. 검증 통과 시 즉시 실행
4. `TELEGRAM_ALLOW_DANGEROUS_COMMANDS=false`면 즉시 차단

## 5) 차단/감사 reason 코드

- `telegram_control_disabled`
- `telegram_webhook_secret_required`
- `telegram_allowed_chat_ids_missing`
- `telegram_allowed_user_ids_missing`
- `telegram_chat_not_allowed`
- `telegram_user_not_allowed`
- `dangerous_commands_disabled`

## 6) 장애 대응

- 비인가 요청 급증:
  - `TELEGRAM_ALLOWED_CHAT_IDS`, `TELEGRAM_ALLOWED_USER_IDS` 재검증
  - 감사 로그의 reason 코드 기준으로 차단 정책 점검
- secret 유출 의심:
  - bot token / webhook secret 즉시 재발급
  - `TELEGRAM_CONFIRM_SECRET`도 함께 교체
- 위험 명령 일시 차단:
  - `TELEGRAM_ALLOW_DANGEROUS_COMMANDS=false`
- 전체 제어 중지:
  - `TELEGRAM_CONTROL_ENABLED=false`

## 7) 점검 체크리스트

- `/run` 실행 시 `trigger_source='telegram'` 확인
- `/status`, `/approve`, `/logs` 정상 응답 확인
- 비허용 user/chat 요청에서 `status=blocked` + 감사 로그 생성 확인
- 위험 명령이 허용 설정에서 즉시 실행되는지 확인
