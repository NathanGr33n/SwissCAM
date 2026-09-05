"""L0/L1 simulation checks before G-code export."""

from __future__ import annotations

import math

from swisscam.domain.models import (
    Diagnostic,
    MachineProfile,
    PartModel,
    ProcessPlan,
    SimulationReport,
    Toolpath,
)
from swisscam.features.recognize import part_length_mm


def simulate(
    toolpaths: list[Toolpath],
    plan: ProcessPlan,
    part: PartModel,
    machine: MachineProfile,
) -> SimulationReport:
    diags: list[Diagnostic] = []

    if plan.unmet_features:
        diags.append(
            Diagnostic(
                level="error",
                code="UNMET_FEATURES",
                message=f"Unmet features: {', '.join(plan.unmet_features)}",
                context={"features": plan.unmet_features},
            )
        )

    if not toolpaths:
        diags.append(
            Diagnostic(level="error", code="NO_TOOLPATHS", message="No toolpaths generated")
        )

    length = part_length_mm(part)
    if length > machine.bar.gb_max_length_mm + 1e-6:
        diags.append(
            Diagnostic(
                level="warning",
                code="PART_LENGTH_GB",
                message=(
                    f"Part length {length:.3f} mm exceeds GB max "
                    f"{machine.bar.gb_max_length_mm:.3f} mm; rechuck or GBL mode may be required"
                ),
            )
        )

    if part.stock.diameter_mm > machine.bar.max_diameter_mm + 1e-9:
        opt = machine.bar.optional_max_diameter_mm
        if opt is None or part.stock.diameter_mm > opt + 1e-9:
            diags.append(
                Diagnostic(
                    level="error",
                    code="BAR_DIAMETER",
                    message=(
                        f"Stock diameter {part.stock.diameter_mm} mm exceeds machine capacity "
                        f"{machine.bar.max_diameter_mm} mm"
                    ),
                )
            )
        else:
            diags.append(
                Diagnostic(
                    level="warning",
                    code="BAR_DIAMETER_OPTION",
                    message="Stock uses optional oversized bar capacity",
                )
            )

    # Stick-out: full part length treated as protrusion for main work (conservative)
    if length > machine.bar.max_unsupported_stickout_mm + 1e-6:
        diags.append(
            Diagnostic(
                level="warning",
                code="STICKOUT",
                message=(
                    f"Part length {length:.3f} mm exceeds configured max unsupported stick-out "
                    f"{machine.bar.max_unsupported_stickout_mm:.3f} mm"
                ),
            )
        )

    axis_limits = {a.name: a for a in machine.axes}
    for tp in toolpaths:
        for i, seg in enumerate(tp.segments):
            if seg.x_diam_mm is not None and (math.isnan(seg.x_diam_mm) or math.isinf(seg.x_diam_mm)):
                diags.append(
                    Diagnostic(
                        level="error",
                        code="NAN_PATH",
                        message=f"Invalid X in {tp.operation_id} seg {i}",
                    )
                )
            if seg.z_mm is not None and (math.isnan(seg.z_mm) or math.isinf(seg.z_mm)):
                diags.append(
                    Diagnostic(
                        level="error",
                        code="NAN_PATH",
                        message=f"Invalid Z in {tp.operation_id} seg {i}",
                    )
                )
            z_ax = axis_limits.get("Z1")
            if z_ax and seg.z_mm is not None:
                if z_ax.min_mm is not None and seg.z_mm < z_ax.min_mm - 1e-6:
                    diags.append(
                        Diagnostic(
                            level="error",
                            code="TRAVEL_Z",
                            message=f"Z {seg.z_mm} below min {z_ax.min_mm} in {tp.operation_id}",
                        )
                    )
                if z_ax.max_mm is not None and seg.z_mm > z_ax.max_mm + 1e-6:
                    diags.append(
                        Diagnostic(
                            level="error",
                            code="TRAVEL_Z",
                            message=f"Z {seg.z_mm} above max {z_ax.max_mm} in {tp.operation_id}",
                        )
                    )

            # Guide bushing box coarse check on X
            for box in machine.clearances:
                if box.name != "guide_bushing" or seg.x_diam_mm is None or seg.z_mm is None:
                    continue
                # Tool nose roughly at X radius; flag deep negative X near bushing Z band
                if (
                    box.z_min_mm <= seg.z_mm <= box.z_max_mm
                    and seg.x_diam_mm < box.x_min_mm
                    and "cutoff" not in (seg.comment or "")
                ):
                    diags.append(
                        Diagnostic(
                            level="warning",
                            code="BUSHING_ENV",
                            message=(
                                f"Path nears bushing envelope at Z={seg.z_mm} Xd={seg.x_diam_mm} "
                                f"({tp.operation_id})"
                            ),
                        )
                    )

    # Multi-system wait pairing presence on plan
    for b in plan.barriers:
        if len(b.systems) < 2:
            diags.append(
                Diagnostic(
                    level="error",
                    code="WAIT_UNPAIRED",
                    message=f"Barrier {b.id} must list at least two systems",
                )
            )

    errors = [d for d in diags if d.level == "error"]
    return SimulationReport(ok=len(errors) == 0, level_reached="L1", diagnostics=diags)
