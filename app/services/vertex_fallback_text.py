from __future__ import annotations

from typing import Any


def _genre_token(raw_genre: str) -> str:
    lowered = (raw_genre or "").strip().casefold()
    if any(token in lowered for token in ("race", "racing", "openwheel", "formula", "circuit", "drift", "레이싱")):
        return "racing"
    if any(token in lowered for token in ("flight", "island", "pilot", "sky", "wing", "비행")):
        return "flight"
    if any(token in lowered for token in ("shoot", "dogfight", "arena", "combat", "shooter", "슈팅")):
        return "shooter"
    if any(token in lowered for token in ("puzzle", "퍼즐")):
        return "puzzle"
    if any(token in lowered for token in ("survival", "생존")):
        return "survival"
    if any(token in lowered for token in ("experimental", "prototype", "실험")):
        return "experimental"
    if any(token in lowered for token in ("action", "arcade", "액션")):
        return "action"
    return "game"


def build_marketing_fallback_copy(*, display_name: str, keyword: str, genre: str) -> str:
    token = _genre_token(genre)
    line = {
        "racing": "네온 서킷을 질주하며 랩타임을 줄여가는 레이싱",
        "flight": "섬과 구름 사이를 날며 링을 꿰는 비행",
        "shooter": "적 편대를 추격하며 회피와 사격을 이어가는 슈팅",
        "puzzle": "짧은 규칙 안에서 감각적으로 푸는 퍼즐",
        "survival": "압박 속에서 생존 루프를 쌓아가는 서바이벌",
        "experimental": "낯선 규칙 감각을 시험하는 실험작",
        "action": "즉시 시작해 손맛을 확인하는 액션",
        "game": "브라우저에서 바로 실행할 수 있는 게임",
    }[token]
    resolved_keyword = keyword.strip() or display_name
    return f"{display_name} · {resolved_keyword} 감성의 {line}을 지금 플레이해보세요."


def build_publish_copy_fallback(*, display_name: str, genre: str) -> dict[str, Any]:
    token = _genre_token(genre)
    return {
        "marketing_summary": {
            "racing": f"{display_name} · 네온 서킷을 질주하며 기록을 줄여가는 3D 레이싱 게임",
            "flight": f"{display_name} · 섬과 구름 사이를 날며 링을 통과하는 3D 비행 게임",
            "shooter": f"{display_name} · 적 편대를 추격하며 회피와 사격을 이어가는 3D 슈팅 게임",
            "puzzle": f"{display_name} · 짧은 규칙 안에서 경로와 타이밍을 읽는 퍼즐 게임",
            "survival": f"{display_name} · 압박 속에서 생존 시간을 늘려가는 아케이드 생존 게임",
            "experimental": f"{display_name} · 짧고 선명한 규칙 실험에 집중한 실험작",
            "action": f"{display_name} · 즉시 시작해 손맛 있게 즐기는 아케이드 액션 게임",
            "game": f"{display_name} · 브라우저에서 바로 실행할 수 있는 게임",
        }[token],
        "play_overview": {
            "racing": [
                "체크포인트를 이어가며 랩타임을 줄이는 레이싱 구조입니다.",
                "브레이킹 타이밍과 코너 탈출 가속이 기록 차이를 만듭니다.",
            ],
            "flight": [
                "섬과 구름 사이를 날며 링을 통과하는 비행 구조입니다.",
                "고도와 yaw를 안정적으로 유지하면서 다음 링 각도를 읽는 것이 핵심입니다.",
            ],
            "shooter": [
                "적 편대를 추격하며 회피와 사격을 반복하는 전투 구조입니다.",
                "짧은 부스트와 사격 타이밍을 엮어 전투 리듬을 만드는 것이 중요합니다.",
            ],
            "puzzle": [
                "짧은 규칙 안에서 경로와 타이밍을 읽는 퍼즐 구조입니다.",
                "정답 하나보다 탐색 순서와 관찰이 중요합니다.",
            ],
            "survival": [
                "초반 생존 루프를 빠르게 익히고 압박을 관리하는 구조입니다.",
                "공간 확보와 템포 조절이 오래 버티는 핵심입니다.",
            ],
            "experimental": [
                "짧은 플레이 안에 새로운 규칙 감각을 시험하는 실험작입니다.",
                "무엇을 해야 하는지보다 어떻게 해석하는지가 중요한 빌드입니다.",
            ],
            "action": [
                "즉시 시작해 손맛과 템포를 확인할 수 있는 액션 구조입니다.",
                "짧은 회피와 연속 입력 타이밍이 핵심입니다.",
            ],
            "game": ["바로 실행해서 루프와 감각을 확인할 수 있는 빌드입니다."],
        }[token],
        "controls_guide": {
            "racing": ["조향: A / D 또는 ← / →", "가속·감속: W / S 또는 ↑ / ↓", "재시작: R"],
            "flight": ["피치: W / S", "Yaw / Bank: A / D", "부스트: Shift", "자세 안정화: Space", "재시작: R"],
            "shooter": ["피치: W / S", "롤: A / D", "Yaw: Q / E", "사격: Space", "부스트: Shift", "재시작: R"],
            "puzzle": ["이동: 방향키 또는 WASD", "상호작용: Space", "재시작: R"],
            "survival": ["이동: 방향키 또는 WASD", "액션: Space", "재시작: R"],
            "experimental": ["이동: 방향키 또는 WASD", "상호작용: Space", "재시작: R"],
            "action": ["이동: 방향키 또는 WASD", "액션: Space", "재시작: R"],
            "game": ["조작은 화면 상단 HUD를 먼저 확인하세요.", "재시작: R"],
        }[token],
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
