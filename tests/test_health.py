from app.main import healthz


def test_healthz() -> None:
    response = healthz()
    assert response["status"] == "ok"
