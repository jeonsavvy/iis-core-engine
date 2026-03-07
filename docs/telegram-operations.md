# Telegram 운영 절차서 (게임 런치/마케팅 알림 봇)

## 1) 봇 정체성

- Telegram 봇의 1차 목적은 **운영 제어**가 아니라 **게임 런치/마케팅 알림**입니다.
- 퍼블리시 성공 시 아래 4가지를 우선 전달합니다.
  1. 대표 이미지 (`thumbnail_url > screenshot_url`, 단 Telegram에서 바로 열 수 있는 공개 `http(s)` 이미지여야 함)
  2. 게임 제목
  3. 한줄 마케팅 감성 설명 (`marketing_summary` 기반)
  4. 플레이 링크 (`PUBLIC_PORTAL_BASE_URL + /play/<slug>` 권장)
- 대표 이미지를 안전하게 만들 수 없으면 **텍스트 알림으로 자동 fallback** 됩니다.

## 2) 알림 포맷 정책

### 대표 이미지 우선순위
- 1순위: `thumbnail_url`
- 2순위: `screenshot_url`
- 제외: 로컬 상대경로, 비공개 URL, `.svg`

### 텍스트 톤
- 출시 공지 + 감성 카피 중심
- 내부 운영 필드, 파이프라인 상태, 기술 로그는 기본 알림 본문에서 제외
- 링크는 `play`를 우선, `public`은 보조 정보일 때만 추가

## 3) 환경변수

### 필수/권장
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS`
- `PUBLIC_PORTAL_BASE_URL` (**권장**: Telegram에서 절대 플레이 링크 생성용)
- `HTTP_TIMEOUT_SECONDS`
- `HTTP_MAX_RETRIES`

## 4) 명령어 정책

- 이 봇은 **명령을 받지 않습니다.**
- `/run`, `/approve`, `/retry`, `/cancel`, `/reset`, `/delete_game` 같은 운영 제어 명령은 제품 정의에서 완전히 제거합니다.
- 향후에도 Telegram은 **출시 홍보 알림 전용 채널**로 유지하고, 운영 제어는 별도 도구에서 처리합니다.

## 5) 장애 대응

- 사진이 오지 않음
  - `thumbnail_url` / `screenshot_url`가 절대 `http(s)` URL인지 확인
  - `.svg`, 상대경로(`/assets/...`)면 텍스트 fallback이 정상 동작한 것인지 확인
- 플레이 링크가 상대경로로 옴
  - `PUBLIC_PORTAL_BASE_URL` 설정 여부 확인
- 알림 톤이 너무 기술적임
  - `marketing_summary` 생성 품질과 fallback 문구를 우선 점검

## 6) 점검 체크리스트

- 퍼블리시 성공 시 대표 이미지가 있으면 `sendPhoto`, 없으면 `sendMessage`로 fallback 되는지 확인
- 알림 본문에 게임 제목 / 한줄 설명 / 플레이 링크가 모두 들어가는지 확인
- `PUBLIC_PORTAL_BASE_URL` 설정 시 Telegram에서 절대 플레이 링크가 열리는지 확인
- 내부 기술 메시지(`slug`, pipeline, raw debug text)가 과도하게 노출되지 않는지 확인
