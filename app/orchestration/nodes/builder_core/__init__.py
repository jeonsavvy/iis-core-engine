from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.orchestration.nodes.builder_core.capability_extractor import extract_capability_profile
from app.orchestration.nodes.builder_core.capability_graph import build_capability_graph, build_module_plan
from app.orchestration.nodes.builder_core.contract_compiler import compile_builder_contract
from app.orchestration.nodes.builder_core.module_assembler import assemble_runtime_modules
from app.orchestration.nodes.builder_core.runtime_exporter import export_runtime_artifact
from app.orchestration.nodes.builder_core.selfcheck_runner import run_builder_selfcheck


@dataclass(frozen=True)
class BuilderCoreResult:
    artifact_html: str
    capability_profile: dict[str, Any]
    capability_graph: dict[str, Any]
    module_plan: dict[str, Any]
    runtime_modules: list[dict[str, Any]]
    module_signature: str
    contract_bundle: dict[str, Any]
    selfcheck_result: dict[str, Any]


def build_modular_artifact(
    *,
    keyword: str,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    viewport_width: int,
    viewport_height: int,
    safe_area_padding: int,
    text_overflow_policy: str,
    core_loop_type: str,
    analyze_contract: dict[str, Any] | None = None,
    plan_contract: dict[str, Any] | None = None,
    design_contract: dict[str, Any] | None = None,
    rqc_version: str = "rqc-1",
) -> BuilderCoreResult:
    capability_profile = extract_capability_profile(
        keyword=keyword,
        title=title,
        genre=genre,
        core_loop_type=core_loop_type,
        analyze_contract=analyze_contract,
        plan_contract=plan_contract,
        design_contract=design_contract,
    )
    capability_graph = build_capability_graph(capability_profile)
    module_plan = build_module_plan(capability_profile, capability_graph)
    contract_bundle = compile_builder_contract(
        keyword=keyword,
        title=title,
        genre=genre,
        capability_profile=capability_profile,
        analyze_contract=analyze_contract,
        plan_contract=plan_contract,
        design_contract=design_contract,
    )
    assembled_modules = assemble_runtime_modules(
        module_plan=module_plan,
        capability_profile=capability_profile,
    )
    artifact_html = export_runtime_artifact(
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        safe_area_padding=safe_area_padding,
        text_overflow_policy=text_overflow_policy,
        capability_profile=capability_profile,
        module_plan=module_plan,
        assembled_modules=assembled_modules,
        contract_bundle=contract_bundle,
        rqc_version=rqc_version,
    )
    selfcheck_result = run_builder_selfcheck(
        html_content=artifact_html,
        capability_profile=capability_profile,
        module_plan=module_plan,
        rqc_version=rqc_version,
    )
    return BuilderCoreResult(
        artifact_html=artifact_html,
        capability_profile=capability_profile,
        capability_graph=capability_graph,
        module_plan=module_plan,
        runtime_modules=assembled_modules.get("runtime_modules", []),
        module_signature=str(assembled_modules.get("module_signature", "unknown")),
        contract_bundle=contract_bundle,
        selfcheck_result=selfcheck_result,
    )
