from app.main import healthz


def test_healthz() -> None:
    response = healthz()
    assert response["status"] == "ok"
    assert "git_sha" in response
    assert response["pipeline_schema_version"] == "v2"
    assert "reporter" in response["pipeline_agent_enum_signature"]
    assert response["generation_engine_version"] == "scaffold_v3"
    assert response["rqc_version"]
    assert response["module_signature"]
