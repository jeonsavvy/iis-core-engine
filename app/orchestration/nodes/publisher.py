from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.PUBLISH,
        agent_name=PipelineAgentName.PUBLISHER,
    )
    if gated_state is not None:
        return gated_state

    try:
        artifact = BuildArtifactPayload.model_validate(
            state["outputs"].get("build_artifact")
            or {
                "game_slug": str(state["outputs"].get("game_slug", "untitled")),
                "game_name": str(state["outputs"].get("game_name", "untitled")),
                "game_genre": str(state["outputs"].get("game_genre", "arcade")),
                "artifact_path": str(state["outputs"].get("artifact_path", "games/untitled/index.html")),
                "artifact_html": str(
                    state["outputs"].get(
                        "artifact_html",
                        "<!doctype html><html><body><h1>Untitled</h1><script>window.__iis_game_boot_ok=true;</script></body></html>",
                    )
                ),
            }
        )
    except ValidationError as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "invalid_build_artifact_payload"
        return append_log(
            state,
            stage=PipelineStage.PUBLISH,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PUBLISHER,
            message="Publish failed: build artifact payload is invalid.",
            reason=str(exc.errors()),
        )

    slug = artifact.game_slug
    game_name = artifact.game_name
    genre = artifact.game_genre
    artifact_html = artifact.artifact_html
    artifact_files = [file.model_dump() for file in artifact.artifact_files or []]
    entrypoint_path = artifact.entrypoint_path or artifact.artifact_path

    append_log(
        state,
        stage=PipelineStage.PUBLISH,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.PUBLISHER,
        message="Uploading artifact to Supabase storage.",
        metadata={"slug": slug},
    )

    publish_result = deps.publisher_service.publish_game(
        slug=slug,
        name=game_name,
        genre=genre,
        html_content=artifact_html,
        artifact_files=artifact_files,
        entrypoint_path=entrypoint_path,
    )

    if publish_result.get("status") == "error":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = str(publish_result.get("reason", "publisher_error"))
        return append_log(
            state,
            stage=PipelineStage.PUBLISH,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PUBLISHER,
            message="Publish failed.",
            reason=state["reason"],
            metadata={"slug": slug},
        )

    public_url = str(publish_result.get("public_url", ""))
    state["outputs"]["public_url"] = public_url
    state["outputs"]["publish_result"] = {
        "status": publish_result.get("status"),
        "public_url": public_url,
        "game_id": publish_result.get("game_id"),
    }

    archive_status = "skipped"
    archive_reason = None

    append_log(
        state,
        stage=PipelineStage.PUBLISH,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.PUBLISHER,
        message="Syncing archive repository manifest.",
        metadata={"slug": slug, "url": public_url},
    )

    archive_result = deps.github_archive_service.commit_archive_game(
        game_slug=slug,
        game_name=game_name,
        genre=genre,
        html_content=artifact_html,
        public_url=public_url,
        artifact_files=artifact_files,
    )
    archive_status = str(archive_result.get("status", "unknown"))
    archive_reason = archive_result.get("reason")

    if archive_status == "error":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = str(archive_reason or "archive_commit_error")
        return append_log(
            state,
            stage=PipelineStage.PUBLISH,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PUBLISHER,
            message="Archive commit failed.",
            reason=state["reason"],
            metadata={"slug": slug, "url": public_url},
        )

    publish_status = PipelineStatus.SUCCESS if publish_result.get("status") in {"published", "skipped"} else PipelineStatus.ERROR

    return append_log(
        state,
        stage=PipelineStage.PUBLISH,
        status=publish_status,
        agent_name=PipelineAgentName.PUBLISHER,
        message="Artifact published and archive sync completed.",
        metadata={
            "url": public_url,
            "publisher_status": publish_result.get("status"),
            "archive_status": archive_status,
            "archive_reason": archive_reason,
            "storage_path": publish_result.get("storage_path"),
            "uploaded_files": publish_result.get("uploaded_files", []),
        },
    )
