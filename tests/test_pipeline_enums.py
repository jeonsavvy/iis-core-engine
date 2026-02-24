from app.schemas.pipeline import PipelineAgentName, PipelineControlAction, PipelineStage


def test_stylist_and_style_values_present() -> None:
    assert PipelineAgentName.STYLIST.value == "Stylist"
    assert PipelineStage.STYLE.value == "style"


def test_pipeline_control_actions_present() -> None:
    assert PipelineControlAction.PAUSE.value == "pause"
    assert PipelineControlAction.RESUME.value == "resume"
    assert PipelineControlAction.CANCEL.value == "cancel"
    assert PipelineControlAction.RETRY.value == "retry"
