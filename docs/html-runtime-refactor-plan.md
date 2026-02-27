# html_runtime.py 분해 계획 (최소위험 단계적 적용)

## 현재 상태

- 대상 파일: `app/orchestration/nodes/builder_parts/html_runtime.py`
- 구조: 단일 함수 `_build_hybrid_engine_html(...)` 내부에 템플릿/상수/런타임 로직 문자열이 밀집
- 리스크:
  - 작은 수정도 회귀 범위가 넓어 QA 비용이 큼
  - 장르별 조건 분기 추적이 어려움
  - mypy/리뷰에서 의미 단위 검증이 어려움

## 분해 원칙

1. **출력 HTML 완전 동일성 우선**
   - 1단계에서는 결과 문자열 동등성을 깨는 변경 금지
2. **단계별 추출**
   - 큰 함수를 한 번에 나누지 않고, "문자열 조각 생성 함수"부터 분리
3. **회귀 테스트 선행**
   - 기존 `tests/test_builder_genre_engines.py` 중심으로 회귀 방어

## 제안 단계

## 진행 현황 (2026-02-27)

- [x] Phase 1-a: 모드 메타/CONFIG 직렬화 분리
  - `html_runtime_config.py` 추가
  - `resolve_mode_config`, `build_runtime_config_json` 추출
- [x] Phase 2-a: 런타임 밸런스 상수 분리
  - `html_runtime_balance.py` 추가
  - `CONTROL_PRESETS`, `DEPTH_PACKS`, `RELIC_SYNERGY_RULES` 추출
  - `build_runtime_balance_block_js`로 JS 블록 조합
- [x] Phase 2-b: progression/업그레이드 규칙 분리
  - `html_runtime_progression.py` 추가
  - `PROGRESSION_TUNING`, `UPGRADE_PICKS` 추출
  - `build_progression_block_js`로 JS 블록 조합
- [x] Phase 3-a: 문서 셸 조립 분리
  - `html_runtime_shell.py` 추가
  - HTML head/layout/footer 템플릿 분리
- [x] Phase 3-b(1차): 런타임 함수군 일부 섹션 분리
  - `html_runtime_sections.py` 추가
  - 유틸/오디오/WebGL 함수 블록 추출
  - progression 함수 블록(`grantXp/stepProgression/addCombo/consumeDash`) 추출
- [x] Phase 3-b(2차): 스폰/업데이트/렌더/HUD 함수 블록 추가 분리
  - `build_runtime_spawn_combat_functions_js` 추출
  - `build_runtime_update_function_js` 추출
  - `build_runtime_render_functions_js` + `build_runtime_hud_functions_js` 추출
  - 섹션 모듈 재분할:
    - `html_runtime_sections_utility.py`
    - `html_runtime_sections_progression.py`
    - `html_runtime_sections_gameplay.py`
    - `html_runtime_sections_render.py`
    - `html_runtime_sections.py`는 re-export 집합으로 축소
  - 결과: `html_runtime.py` 311 lines (기존 2120 대비 약 85% 축소)

### Phase 1 (저위험)

- 신규 모듈 생성:
  - `app/orchestration/nodes/builder_parts/html_runtime_config.py`
- 추출 대상:
  - 장르 엔진별 메타(label/objective/controls)
  - `CONFIG` JSON 직렬화
- 검증:
  - `test_html_runtime_config.py` + 기존 builder 테스트

### Phase 2 (중위험)

- 런타임 상수/규칙 분리:
  - `CONTROL_PRESETS`, `DEPTH_PACKS`, `RELIC_SYNERGY_RULES`
  - (다음) 업그레이드/리릭/난이도 progression 규칙
- 함수화:
  - `build_runtime_balance_block_js()`
  - (다음) `build_progression_rules(mode, asset_pack, config)` 형태
- 검증:
  - `test_html_runtime_balance.py` + `test_builder_genre_engines.py` + `quality_gate` 점수 회귀 확인

### Phase 3 (중위험)

- 최종 조합기 분리:
  - `assemble_runtime_html(sections: list[str]) -> str`
- `html_runtime.py`는 orchestration wrapper 역할로 축소

## [Risk]

- 문자열 병합 순서 변경으로 런타임 초기화 순서가 깨질 수 있음
- 장르별 hook 토큰 누락 시 gameplay/contract gate 실패 가능

## [Rollback]

- 단계별 브랜치/커밋 단위로 분리
- 각 phase에서 `html_runtime.py` 기존 함수를 즉시 복원 가능한 상태 유지
- 회귀 시 해당 phase만 revert (전체 리팩터 되돌리지 않음)

## 완료 조건

- `html_runtime.py` 단일 파일 라인 수 40% 이상 축소
- 기존 builder/quality 테스트 전량 통과
- 샘플 mode(topdown/webgl/flight/f1)에서 artifact contract 회귀 없음
