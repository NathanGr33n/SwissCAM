"""Orchestrate SwissCAM Phase-1 pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from swisscam.domain.models import (
    Feature,
    Layout,
    MachineProfile,
    MaterialLibrary,
    PartModel,
    PostConfig,
    Priority,
    ProcessPlan,
    ProgramIR,
    SimulationReport,
    ToolCrib,
    Toolpath,
)
from swisscam.features.recognize import recognize_profile
from swisscam.io.store import load_model, write_text_safe
from swisscam.planning.sequence import build_plan
from swisscam.post.engine import build_ir, render_gcode
from swisscam.simulate.checks import simulate
from swisscam.toolpath.generate import generate_toolpaths
from swisscam.tools.select import select_tools


@dataclass
class PipelineResult:
    part: PartModel
    features: list[Feature]
    plan: ProcessPlan
    toolpaths: list[Toolpath]
    simulation: SimulationReport
    ir: ProgramIR
    gcode: str


def run_pipeline(
    *,
    part: PartModel,
    machine: MachineProfile,
    layout: Layout,
    crib: ToolCrib,
    post: PostConfig,
    materials: MaterialLibrary | None = None,
    priority: Priority = Priority.FASTEST_CYCLE,
    program_name: str | None = None,
    override_export: bool = False,
) -> PipelineResult:
    if layout.machine_profile_id != machine.id:
        raise ValueError(
            f"Layout machine_profile_id {layout.machine_profile_id!r} != machine id {machine.id!r}"
        )

    features = recognize_profile(part)
    ops, unmet = select_tools(
        features,
        layout,
        crib,
        material_id=part.stock.material_id,
        materials=materials,
        priority=priority,
    )
    plan = build_plan(ops, features, part, unmet=unmet)
    toolpaths = generate_toolpaths(plan.operations, features, part)
    if toolpaths:
        plan.cycle_time_s = sum(tp.estimated_time_s for tp in toolpaths)

    sim = simulate(toolpaths, plan, part, machine)
    if override_export:
        sim.override_export = True

    ir = build_ir(
        program_name=program_name or part.name or part.id,
        machine=machine,
        layout=layout,
        part=part,
        plan=plan,
        toolpaths=toolpaths,
        simulation=sim,
    )
    gcode = render_gcode(ir, post)
    return PipelineResult(
        part=part,
        features=features,
        plan=plan,
        toolpaths=toolpaths,
        simulation=sim,
        ir=ir,
        gcode=gcode,
    )


def run_from_paths(
    *,
    part_path: Path | str,
    machine_path: Path | str,
    layout_path: Path | str,
    crib_path: Path | str,
    post_path: Path | str,
    materials_path: Path | str | None = None,
    output_path: Path | str | None = None,
    priority: Priority = Priority.FASTEST_CYCLE,
    override_export: bool = False,
    project_root: Path | None = None,
) -> PipelineResult:
    part = load_model(part_path, PartModel)
    machine = load_model(machine_path, MachineProfile)
    layout = load_model(layout_path, Layout)
    crib = load_model(crib_path, ToolCrib)
    post = load_model(post_path, PostConfig)
    materials = load_model(materials_path, MaterialLibrary) if materials_path else None

    result = run_pipeline(
        part=part,
        machine=machine,
        layout=layout,
        crib=crib,
        post=post,
        materials=materials,
        priority=priority,
        override_export=override_export,
    )

    if output_path is not None:
        write_text_safe(output_path, result.gcode, root=project_root)
    return result
