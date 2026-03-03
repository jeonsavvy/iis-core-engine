from app.main import healthz


def test_healthz() -> None:
    response = healthz()
    assert response["status"] == "ok"
    assert "git_sha" in response
    assert response["pipeline_schema_version"] == "v2"
    assert "reporter" in response["pipeline_agent_enum_signature"]
    assert response["gen_core_mode"] in {"legacy", "modular", "scaffold"}
    assert response["rqc_version"]
    assert response["module_signature"]
