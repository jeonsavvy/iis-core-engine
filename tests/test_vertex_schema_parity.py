from __future__ import annotations

from app.schemas.payloads import (
    AnalyzeContractPayload,
    DesignContractPayload,
    DesignSpecPayload,
    PlanContractPayload,
)
from app.services.vertex_models import (
    AnalyzeContractModel,
    DesignContractModel,
    DesignSpecModel,
    PlanContractModel,
)


def _field_signature(model_cls) -> dict[str, tuple[str, list[str]]]:
    signature: dict[str, tuple[str, list[str]]] = {}
    for name, field in model_cls.model_fields.items():
        signature[name] = (
            str(field.annotation),
            [str(meta) for meta in field.metadata],
        )
    return signature


def test_analyze_contract_schema_parity_between_vertex_and_payload() -> None:
    assert _field_signature(AnalyzeContractModel) == _field_signature(AnalyzeContractPayload)


def test_plan_contract_schema_parity_between_vertex_and_payload() -> None:
    assert _field_signature(PlanContractModel) == _field_signature(PlanContractPayload)


def test_design_contract_schema_parity_between_vertex_and_payload() -> None:
    assert _field_signature(DesignContractModel) == _field_signature(DesignContractPayload)


def test_design_spec_schema_parity_between_vertex_and_payload() -> None:
    assert _field_signature(DesignSpecModel) == _field_signature(DesignSpecPayload)

