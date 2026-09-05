"""Build ProgramIR and render G-code via PostConfig maps."""

from __future__ import annotations

from jinja2 import BaseLoader, Environment, select_autoescape

from swisscam.domain.models import (
    IRBlock,
    IRSystem,
    Layout,
    MachineProfile,
    MotionType,
    PartModel,
    PostConfig,
    ProcessPlan,
    ProgramIR,
    SimulationReport,
    Toolpath,
)


def build_ir(
    *,
    program_name: str,
    machine: MachineProfile,
    layout: Layout,
    part: PartModel,
    plan: ProcessPlan,
    toolpaths: list[Toolpath],
    simulation: SimulationReport,
) -> ProgramIR:
    tool_list = []
    seen: set[str] = set()
    for tp in toolpaths:
        if tp.t_code in seen:
            continue
        seen.add(tp.t_code)
        tool_list.append(
            {
                "t_code": tp.t_code,
                "tool_id": tp.tool_id,
                "operation_id": tp.operation_id,
            }
        )

    sys1_blocks: list[IRBlock] = [
        IRBlock(kind="comment", text="SwissCAM main system $1"),
        IRBlock(kind="mode", mode="G610"),
        IRBlock(kind="mcode", m=None, text="coolant_on"),
        IRBlock(kind="spindle", css=None, text="main_cw"),
    ]

    for tp in toolpaths:
        sys1_blocks.append(IRBlock(kind="tool", t_code=tp.t_code))
        for seg in tp.segments:
            sys1_blocks.append(IRBlock(kind="motion", segment=seg))

    sys1_blocks.append(IRBlock(kind="wait", wait_id="W1"))
    sys1_blocks.append(IRBlock(kind="comment", text="pickup/cutoff sync point"))
    sys1_blocks.append(IRBlock(kind="wait", wait_id="W2"))
    sys1_blocks.append(IRBlock(kind="mcode", text="coolant_off"))
    sys1_blocks.append(IRBlock(kind="mcode", text="main_stop"))
    sys1_blocks.append(IRBlock(kind="mcode", text="part_count"))

    sys2_blocks: list[IRBlock] = [
        IRBlock(kind="comment", text="SwissCAM sub system $2 (safe skeleton)"),
        IRBlock(kind="wait", wait_id="W1"),
        IRBlock(kind="comment", text="sub spindle ready / pickup placeholder"),
        IRBlock(kind="wait", wait_id="W2"),
        IRBlock(kind="comment", text="back-working placeholder"),
    ]

    cycle = sum(tp.estimated_time_s for tp in toolpaths) or plan.cycle_time_s

    return ProgramIR(
        program_name=program_name,
        machine_id=machine.id,
        layout_id=layout.id,
        material_id=part.stock.material_id,
        stock_diameter_mm=part.stock.diameter_mm,
        cycle_time_s=cycle,
        bar_usage_mm=plan.bar_usage_mm,
        tool_list=tool_list,
        systems=[
            IRSystem(name="$1", blocks=sys1_blocks),
            IRSystem(name="$2", blocks=sys2_blocks),
        ],
        simulation=simulation,
    )


def _fmt(value: float, fmt: str = "0.001") -> str:
    # fmt like 0.001 -> 3 decimals
    if "." in fmt:
        decimals = len(fmt.split(".", 1)[1])
    else:
        decimals = 3
    return f"{value:.{decimals}f}"


def _motion_line(seg, post: PostConfig) -> str:
    g_rapid = post.g_map.get("rapid", "G00")
    g_feed = post.g_map.get("linear", "G01")
    g_dwell = post.g_map.get("dwell", "G04")
    bits: list[str] = []
    if seg.motion == MotionType.RAPID:
        bits.append(g_rapid)
    elif seg.motion == MotionType.FEED:
        bits.append(g_feed)
    elif seg.motion == MotionType.DWELL:
        bits.append(g_dwell)
        if seg.dwell_s is not None:
            bits.append(f"U{_fmt(seg.dwell_s, post.number_format)}")
        return " ".join(bits) + (f" ({seg.comment})" if post.comments and seg.comment else "")
    else:
        bits.append(g_feed)

    if seg.x_diam_mm is not None:
        bits.append(f"X{_fmt(seg.x_diam_mm, post.number_format)}")
    if seg.z_mm is not None:
        bits.append(f"Z{_fmt(seg.z_mm, post.number_format)}")
    if seg.motion == MotionType.FEED:
        if seg.feed_mm_rev is not None:
            bits.append(f"F{_fmt(seg.feed_mm_rev, post.number_format)}")
        if seg.css_m_per_min is not None and post.g_map.get("css_on"):
            # CSS often set separately; include as comment if modal already on
            pass
    if post.comments and seg.comment:
        bits.append(f"({seg.comment})")
    return " ".join(bits)


def render_gcode(ir: ProgramIR, post: PostConfig) -> str:
    if ir.simulation and not ir.simulation.ok and not ir.simulation.override_export:
        raise RuntimeError("Refusing to post: simulation failed (set override to force)")

    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(enabled_extensions=()))
    header_ctx = {
        "program_name": ir.program_name,
        "program_number": post.program_number,
        "revision": ir.revision,
        "machine_id": ir.machine_id,
        "layout_id": ir.layout_id,
        "material_id": ir.material_id,
        "stock_diameter_mm": ir.stock_diameter_mm,
        "cycle_time_s": ir.cycle_time_s,
        "bar_usage_mm": ir.bar_usage_mm,
        "tool_list": ir.tool_list,
        "swisscam_version": ir.swisscam_version,
        "simulation_ok": ir.simulation.ok if ir.simulation else False,
        "z0_policy": post.z0_policy,
    }
    lines: list[str] = []
    if post.header_template.strip():
        lines.extend(env.from_string(post.header_template).render(**header_ctx).splitlines())
    else:
        lines.append(f"O{post.program_number}")
        lines.append(f"({ir.program_name} rev {ir.revision})")
        lines.append(f"(machine {ir.machine_id} layout {ir.layout_id})")
        lines.append(f"(stock dia {ir.stock_diameter_mm} material {ir.material_id})")
        if ir.cycle_time_s is not None:
            lines.append(f"(est cycle s {ir.cycle_time_s:.2f})")
        if ir.bar_usage_mm is not None:
            lines.append(f"(bar usage mm {ir.bar_usage_mm:.3f})")
        for t in ir.tool_list:
            lines.append(f"(tool {t['t_code']} {t['tool_id']})")
        lines.append(f"(swisscam {ir.swisscam_version} sim_ok {header_ctx['simulation_ok']})")

    # Modal prelude
    if post.units == "mm":
        lines.append(post.g_map.get("metric", "G21"))
    else:
        lines.append(post.g_map.get("inch", "G20"))
    if post.absolute:
        lines.append(post.g_map.get("absolute", "G90"))
    lines.append(post.g_map.get("feed_per_rev", "G99"))
    lines.append(post.g_map.get("css_on", "G96"))

    m = post.m_map
    for system in ir.systems:
        lines.append(system.name)
        for block in system.blocks:
            if block.kind == "comment" and block.text:
                if post.comments:
                    lines.append(f"({block.text})")
            elif block.kind == "mode" and block.mode:
                code = post.mode_codes.get(block.mode, block.mode)
                lines.append(code)
            elif block.kind == "wait" and block.wait_id:
                lines.append(post.wait_format.format(id=block.wait_id))
            elif block.kind == "tool" and block.t_code:
                lines.append(block.t_code)
            elif block.kind == "spindle":
                lines.append(f"M{m.get('main_cw', 3):02d}")
            elif block.kind == "mcode":
                key = block.text or ""
                if key in m:
                    lines.append(f"M{m[key]:02d}")
                elif block.m is not None:
                    lines.append(f"M{block.m:02d}")
            elif block.kind == "motion" and block.segment is not None:
                lines.append(_motion_line(block.segment, post))
            elif block.kind == "gcode" and block.g:
                lines.append(block.g)

    if post.footer_template.strip():
        lines.extend(env.from_string(post.footer_template).render(**header_ctx).splitlines())
    else:
        lines.append(f"M{m.get('program_end', 30):02d}")
        lines.append("%")

    # Ensure multi-system waits appear in every listed system
    wait_ids = set()
    for system in ir.systems:
        for block in system.blocks:
            if block.kind == "wait" and block.wait_id:
                wait_ids.add(block.wait_id)
    for wid in wait_ids:
        for system in ir.systems:
            has = any(b.kind == "wait" and b.wait_id == wid for b in system.blocks)
            if not has:
                raise RuntimeError(f"Wait {wid} missing from system {system.name}")

    return "\n".join(lines) + "\n"
