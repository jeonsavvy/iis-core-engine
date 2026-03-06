from __future__ import annotations

from typing import Any


def build_marketing_fallback_copy(*, display_name: str, keyword: str, genre: str) -> str:
    return (
        f"🎮 '{display_name}' 신규 게임이 게시되었습니다! "
        f"'{keyword}' 키워드 기반의 {genre} 플레이를 지금 확인해보세요. #indiegame #html5"
    )


def build_publish_copy_fallback(*, display_name: str, genre: str) -> dict[str, Any]:
    genre_text = genre.strip() or "web"
    return {
        "marketing_summary": f"{display_name} · {genre_text} 플레이를 바로 즐길 수 있는 브라우저 게임",
        "play_overview": [
            "게임을 시작하면 화면의 목표와 루프를 먼저 확인하세요.",
            "초반에는 생존과 조작 감각 파악에 집중하고, 익숙해지면 기록과 효율을 끌어올리세요.",
        ],
        "controls_guide": [
            "기본 이동/조작은 화면 HUD 또는 게임 내 안내를 우선 확인하세요.",
            "재시작은 일반적으로 R 키 기준으로 동작하도록 설계됩니다.",
        ],
    }


def build_ai_review_fallback(*, keyword: str, game_name: str, genre: str, objective: str) -> str:
    return (
        f"{game_name}은(는) '{keyword}' 키워드를 {genre} 플레이 루프로 정리했습니다. "
        f"{objective} 목표를 중심으로 속도감과 장애물 회피 리듬을 강화했고, "
        "HUD 가독성과 즉시 재도전 흐름을 우선하도록 구성했습니다."
    )


def build_grounded_ai_review_fallback(*, objective: str, evidence: dict[str, Any]) -> str:
    engine = str(evidence.get("genre_engine", "")).strip() or "unknown"
    quality_score = evidence.get("quality_score")
    gameplay_score = evidence.get("gameplay_score")
    return (
        f"현재 빌드는 '{engine}' 루프 기반이며 목표는 '{objective}'입니다. "
        f"QA 점수(quality={quality_score}, gameplay={gameplay_score}) 기준으로 동작은 확인됐지만, "
        "요청 대비 장르 깊이/시뮬레이션 정밀도는 추가 개선이 필요합니다."
    )
