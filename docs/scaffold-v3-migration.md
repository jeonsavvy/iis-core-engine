# Scaffold V3 Migration Guide (Core ↔ Portal)

## 변경 요약
- Builder 생성 엔진이 `scaffold_v3` 단일 경로로 통합되었습니다.
- QA 단계는 verify-only 하드게이트로 동작하며, 품질 미달 시 Release 이전에 파이프라인이 종료됩니다.
- 로그 메타데이터는 `quality_gate_report`, `generation_engine_version`, `blocking_reasons` 중심으로 재정의되었습니다.

## Breaking 포인트
- Health 응답의 `gen_core_mode` 키는 제거되고 `generation_engine_version`가 제공됩니다.
- Builder 메타데이터의 modular 전용 필드는 더 이상 보장되지 않습니다.

## 배포 순서 (동시 컷오버)
1. `iis-core-engine` 배포
2. `iis-game-portal` 배포
3. 운영실(`/admin`)에서 `quality_gate_report` / `blocking_reasons` 노출 확인

## 롤백
- 메인 코드 fallback은 유지하지 않습니다.
- 롤백 시 `archive/pre-refactor-*` 브랜치 기준으로 Core + Portal 동시 재배포합니다.
