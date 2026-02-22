from app.schemas.pipeline import PipelineAgentName, PipelineStage


def test_stylist_and_style_values_present() -> None:
    assert PipelineAgentName.STYLIST.value == "Stylist"
    assert PipelineStage.STYLE.value == "style"
