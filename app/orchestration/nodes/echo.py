from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    slug = state["outputs"].get("game_slug", "unknown-game")
    genre = state["outputs"].get("game_genre", "arcade")
    keyword = state.get("keyword", "unknown")
    
    marketing_result = deps.vertex_service.generate_marketing_copy(
        keyword=keyword, slug=slug, genre=genre
    )
    marketing_text = marketing_result.payload.get("marketing_copy", "")
    
    resolved_public_url = ""
    publish_result = state["outputs"].get("publish_result")
    if isinstance(publish_result, dict):
        maybe_public_url = publish_result.get("public_url")
        if isinstance(maybe_public_url, str):
            resolved_public_url = maybe_public_url.strip()
    if not resolved_public_url:
        raw_public_url = state["outputs"].get("public_url")
        if isinstance(raw_public_url, str):
            resolved_public_url = raw_public_url.strip()
    if not resolved_public_url:
        base_url = deps.telegram_service.settings.public_games_base_url.rstrip("/")
        resolved_public_url = f"{base_url}/{slug}/index.html"

    telegram_text = f"🎮 신규 게임 게시됨\n\n{marketing_text}\n\n🕹️ 플레이: {resolved_public_url}"
    
    result = deps.telegram_service.broadcast_message(telegram_text)
    
    screenshot_url = state["outputs"].get("screenshot_url")
    deps.publisher_service.update_game_marketing(
        slug=slug,
        ai_review=marketing_text,
        screenshot_url=screenshot_url
    )

    status = PipelineStatus.SUCCESS if result.get("status") in ("posted", "skipped") else PipelineStatus.SKIPPED
    reason = result.get("reason")

    state = append_log(
        state,
        stage=PipelineStage.ECHO,
        status=status,
        agent_name=PipelineAgentName.ECHO,
        message=f"Telegram broadcast result: {result.get('status', 'unknown')}",
        metadata={
            "generation_source": marketing_result.meta.get("generation_source"),
            "model": marketing_result.meta.get("model"),
            "latency_ms": marketing_result.meta.get("latency_ms"),
            "usage": marketing_result.meta.get("usage", {}),
            "marketing_language": "ko-KR",
            "resolved_public_url": resolved_public_url,
        },
        reason=reason,
    )

    if state["status"] != PipelineStatus.ERROR:
        state["status"] = PipelineStatus.SUCCESS
        append_log(
            state,
            stage=PipelineStage.DONE,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.ECHO,
            message="Pipeline finished.",
        )
    return state
