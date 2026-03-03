from __future__ import annotations

import hashlib
import json
import re

from app.schemas.payloads import AnalyzeContractPayload, DesignContractPayload, GDDPayload, IntentContractPayload, PlanContractPayload

_TOKEN_RE = re.compile(r"[a-z0-9가-힣]+", flags=re.IGNORECASE)
_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "from",
    "that",
    "this",
    "game",
    "loop",
    "player",
    "요청",
    "게임",
    "기반",
}

_VERB_HINTS: tuple[tuple[str, str], ...] = (
    ("move", "move"),
    ("movement", "move"),
    ("dodge", "dodge"),
    ("evade", "dodge"),
    ("attack", "attack"),
    ("shoot", "shoot"),
    ("aim", "aim"),
    ("drift", "drift"),
    ("steer", "steer"),
    ("throttle", "throttle"),
    ("checkpoint", "checkpoint"),
    ("jump", "jump"),
    ("combo", "combo"),
    ("parry", "parry"),
    ("collect", "collect"),
    ("피하기", "dodge"),
    ("회피", "dodge"),
    ("공격", "attack"),
    ("사격", "shoot"),
    ("조준", "aim"),
    ("드리프트", "drift"),
    ("조향", "steer"),
    ("가속", "throttle"),
    ("점프", "jump"),
    ("콤보", "combo"),
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clip_text(value: str, *, limit: int) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    if limit <= 1:
        return normalized[:limit]
    return f"{normalized[: limit - 1].rstrip()}…"


def _merge_unique(rows: list[str], *, limit: int, item_max_length: int | None = None) -> list[str]:
    merged: list[str] = []
    for row in rows:
        text = _normalize_text(str(row))
        if item_max_length is not None:
            text = _clip_text(text, limit=item_max_length)
        if not text or text in merged:
            continue
        merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def _extract_tokens(*values: str) -> list[str]:
    rows: list[str] = []
    for value in values:
        for token in _TOKEN_RE.findall(value.casefold()):
            normalized = token.strip().casefold()
            if len(normalized) < 3 or normalized in _STOPWORDS:
                continue
            rows.append(normalized)
    return rows


def _derive_player_verbs(*, keyword: str, plan_contract: PlanContractPayload) -> list[str]:
    raw_rows = [
        *plan_contract.core_mechanics,
        *plan_contract.risk_reward_plan,
        keyword,
    ]
    normalized_rows = " ".join(str(item) for item in raw_rows).casefold()
    verbs: list[str] = []
    for token, verb in _VERB_HINTS:
        if token in normalized_rows and verb not in verbs:
            verbs.append(verb)
        if len(verbs) >= 8:
            break

    if verbs:
        return verbs

    fallback_tokens = _extract_tokens(*[str(item) for item in raw_rows])
    return _merge_unique(fallback_tokens or ["move", "react"], limit=6)


def build_intent_contract(
    *,
    keyword: str,
    title: str,
    gdd: GDDPayload,
    analyze_contract: AnalyzeContractPayload,
    plan_contract: PlanContractPayload,
    design_contract: DesignContractPayload,
) -> IntentContractPayload:
    fantasy = _clip_text(
        (
        f"{keyword} 요청 판타지를 유지하고 "
        f"{gdd.genre} 장르의 목표({gdd.objective})를 플레이 가능한 루프로 구현한다."
        ),
        limit=260,
    )
    player_verbs = _merge_unique(
        _derive_player_verbs(keyword=keyword, plan_contract=plan_contract),
        limit=8,
        item_max_length=32,
    ) or ["move"]
    camera_interaction = _merge_unique(
        [
            plan_contract.control_model,
            *design_contract.camera_ui_contract[:2],
            "camera/interaction intent must match request",
        ],
        limit=3,
        item_max_length=96,
    )
    progression_loop = _merge_unique(
        [
            *plan_contract.progression_plan,
            *plan_contract.encounter_plan,
            f"session goal: {gdd.objective}",
        ],
        limit=5,
        item_max_length=120,
    )
    fail_restart_loop = _clip_text(
        f"Fail condition must be explicit for {title}, and restart should return to playable state immediately.",
        limit=240,
    )
    non_negotiables = _merge_unique(
        [
            *analyze_contract.hard_constraints,
            *[f"avoid:{item}" for item in analyze_contract.forbidden_patterns],
            "preserve_requested_intent_without_generic_substitution",
        ],
        limit=8,
        item_max_length=120,
    )
    return IntentContractPayload(
        fantasy=fantasy,
        player_verbs=player_verbs,
        camera_interaction=_clip_text(" / ".join(camera_interaction), limit=200),
        progression_loop=progression_loop,
        fail_restart_loop=fail_restart_loop,
        non_negotiables=non_negotiables,
    )


def compute_intent_contract_hash(contract: IntentContractPayload) -> str:
    payload = contract.model_dump()
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
