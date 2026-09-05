"""Sequence operations into a Swiss-style process plan."""

from __future__ import annotations

from swisscam.domain.models import (
    Barrier,
    Feature,
    ModeSegment,
    Operation,
    PartModel,
    ProcessPlan,
    Strategy,
)
from swisscam.features.recognize import part_length_mm

STRATEGY_ORDER = {
    Strategy.FACE: 10,
    Strategy.DRILL: 15,
    Strategy.ROUGH: 20,
    Strategy.GROOVE: 30,
    Strategy.THREAD: 35,
    Strategy.FINISH: 40,
    Strategy.PICKUP: 50,
    Strategy.CUTOFF: 60,
    Strategy.BACK: 70,
    Strategy.OTHER: 90,
}


def build_plan(
    operations: list[Operation],
    features: list[Feature],
    part: PartModel,
    *,
    unmet: list[str] | None = None,
    plan_id: str = "plan-1",
) -> ProcessPlan:
    feat_by_id = {f.id: f for f in features}

    def sort_key(op: Operation) -> tuple:
        z0 = 0.0
        if op.feature_ids:
            f = feat_by_id.get(op.feature_ids[0])
            if f:
                z0 = f.z0_mm
        return (STRATEGY_ORDER.get(op.strategy, 99), z0, op.order)

    ordered = sorted(operations, key=sort_key)
    for i, op in enumerate(ordered, start=1):
        op.order = i
        op.system = "$1"

    # Barriers for future multi-system pickup/cutoff handoff
    barriers = [
        Barrier(id="W1", systems=["$1", "$2"], kind="wait"),
        Barrier(id="W2", systems=["$1", "$2"], kind="wait"),
    ]
    modes = [
        ModeSegment(mode="G610", note="Gang/front working (main path)"),
        ModeSegment(mode="G650", note="Pickup/support placeholder for Phase 2"),
    ]

    length = part_length_mm(part)
    bar_usage = length + part.stock.allowance_face_mm + 1.0  # cutoff kerf approx
    # Rough cycle estimate: sum path times filled later; placeholder proportional to length
    cycle_s = max(5.0, length * 1.5 + 8.0 * len(ordered))

    return ProcessPlan(
        id=plan_id,
        operations=ordered,
        barriers=barriers,
        mode_segments=modes,
        cycle_time_s=cycle_s,
        bar_usage_mm=bar_usage,
        unmet_features=list(unmet or []),
    )
