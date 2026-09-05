"""Select tools from the active layout for recognized features."""

from __future__ import annotations

from swisscam.domain.models import (
    AuditReason,
    CutParams,
    Feature,
    FeatureKind,
    Layout,
    LayoutAssignment,
    MaterialLibrary,
    Operation,
    Priority,
    Strategy,
    ToolAssignment,
    ToolCrib,
    ToolCribEntry,
    ToolType,
)


FEATURE_TOOL_MAP: dict[FeatureKind, list[ToolType]] = {
    FeatureKind.FACE: [ToolType.OD_TURN],
    FeatureKind.OD_CYLINDER: [ToolType.OD_TURN],
    FeatureKind.OD_TAPER: [ToolType.OD_TURN],
    FeatureKind.CHAMFER: [ToolType.OD_TURN],
    FeatureKind.RADIUS: [ToolType.OD_TURN],
    FeatureKind.GROOVE: [ToolType.GROOVE],
    FeatureKind.UNDERCUT: [ToolType.GROOVE],
    FeatureKind.THREAD_EXT: [ToolType.THREAD],
    FeatureKind.ID_BORE: [ToolType.ID_BORE],
    FeatureKind.ID_GROOVE: [ToolType.GROOVE],
    FeatureKind.CENTER_DRILL: [ToolType.CENTER_DRILL, ToolType.DRILL],
    FeatureKind.CUTOFF_PLANE: [ToolType.CUTOFF],
}


def _tool_by_id(crib: ToolCrib) -> dict[str, ToolCribEntry]:
    return {t.id: t for t in crib.tools}


def installed_tools(layout: Layout, crib: ToolCrib) -> list[tuple[LayoutAssignment, ToolCribEntry]]:
    by_id = _tool_by_id(crib)
    out: list[tuple[LayoutAssignment, ToolCribEntry]] = []
    for a in layout.assignments:
        tool = by_id.get(a.tool_id)
        if tool is None:
            continue
        out.append((a, tool))
    return out


def _t_code(assign: LayoutAssignment, fallback_index: int) -> str:
    if assign.t_code:
        return assign.t_code
    return f"T{fallback_index + 1:02d}{(fallback_index + 1):02d}"


def _score_tool(
    tool: ToolCribEntry,
    feature: Feature,
    priority: Priority,
) -> float:
    score = 1.0
    if feature.kind == FeatureKind.GROOVE and feature.width_mm is not None:
        if tool.max_width_mm is not None and tool.max_width_mm + 1e-6 < feature.width_mm:
            return -1.0
        if tool.min_width_mm is not None and feature.width_mm + 1e-6 < tool.min_width_mm:
            return -1.0
        if tool.max_width_mm is not None:
            score += max(0.0, 1.0 - abs(tool.max_width_mm - feature.width_mm))
    if priority == Priority.BEST_FINISH:
        score += max(0.0, 0.5 - tool.nose_radius_mm)
    elif priority == Priority.FASTEST_CYCLE:
        score += tool.max_doc_mm * 0.1
    return score


def _cut_params(tool: ToolCribEntry, material_id: str, materials: MaterialLibrary | None) -> CutParams:
    mat_class = material_id
    if materials:
        for m in materials.materials:
            if m.id == material_id:
                mat_class = m.class_name
                base = CutParams(
                    surface_m_per_min=m.default_sfm,
                    feed_mm_rev=m.default_feed_mm_rev,
                    doc_mm=min(tool.max_doc_mm, m.default_doc_mm),
                    css=True,
                )
                break
        else:
            base = CutParams(surface_m_per_min=100.0, feed_mm_rev=0.1, doc_mm=min(0.5, tool.max_doc_mm))
    else:
        base = CutParams(surface_m_per_min=100.0, feed_mm_rev=0.1, doc_mm=min(0.5, tool.max_doc_mm))

    for row in tool.materials:
        if row.material_class == mat_class or row.material_class == material_id:
            return CutParams(
                surface_m_per_min=row.surface_m_per_min or base.surface_m_per_min,
                rpm=row.rpm_cap,
                feed_mm_rev=row.feed_mm_rev,
                doc_mm=min(tool.max_doc_mm, row.doc_mm),
                css=row.surface_m_per_min is not None,
            )
    return base


def _strategies_for(feature: Feature) -> list[Strategy]:
    if feature.kind == FeatureKind.FACE:
        return [Strategy.FACE]
    if feature.kind in (FeatureKind.OD_CYLINDER, FeatureKind.OD_TAPER, FeatureKind.CHAMFER, FeatureKind.RADIUS):
        return [Strategy.ROUGH, Strategy.FINISH]
    if feature.kind == FeatureKind.GROOVE:
        return [Strategy.GROOVE]
    if feature.kind == FeatureKind.THREAD_EXT:
        return [Strategy.THREAD]
    if feature.kind == FeatureKind.CUTOFF_PLANE:
        return [Strategy.CUTOFF]
    if feature.kind in (FeatureKind.CENTER_DRILL,):
        return [Strategy.DRILL]
    if feature.kind == FeatureKind.ID_BORE:
        return [Strategy.ROUGH, Strategy.FINISH]
    return [Strategy.OTHER]


def select_tools(
    features: list[Feature],
    layout: Layout,
    crib: ToolCrib,
    *,
    material_id: str,
    materials: MaterialLibrary | None = None,
    priority: Priority = Priority.FASTEST_CYCLE,
) -> tuple[list[Operation], list[str]]:
    installed = installed_tools(layout, crib)
    ops: list[Operation] = []
    unmet: list[str] = []
    oid = 1

    for feature in features:
        wanted = FEATURE_TOOL_MAP.get(feature.kind, [ToolType.OTHER])
        candidates: list[tuple[float, LayoutAssignment, ToolCribEntry, int]] = []
        for idx, (assign, tool) in enumerate(installed):
            if tool.tool_type not in wanted:
                continue
            sc = _score_tool(tool, feature, priority)
            if sc < 0:
                continue
            candidates.append((sc, assign, tool, idx))
        candidates.sort(key=lambda x: x[0], reverse=True)

        if not candidates:
            unmet.append(feature.id)
            continue

        best = candidates[0]
        assign, tool = best[1], best[2]
        t_code = _t_code(assign, best[3])
        cand_ids = [c[2].id for c in candidates]
        cut = _cut_params(tool, material_id, materials)
        if feature.kind in (FeatureKind.OD_CYLINDER, FeatureKind.OD_TAPER) and any(
            s == Strategy.FINISH for s in _strategies_for(feature)
        ):
            # finish gets lighter DOC
            finish_cut = cut.model_copy(update={"doc_mm": min(0.15, cut.doc_mm), "stock_allowance_mm": 0.0})
        else:
            finish_cut = cut

        for strategy in _strategies_for(feature):
            use_cut = finish_cut if strategy == Strategy.FINISH else cut
            if strategy == Strategy.ROUGH:
                use_cut = cut.model_copy(update={"stock_allowance_mm": 0.2})
            ops.append(
                Operation(
                    id=f"OP{oid:03d}",
                    feature_ids=[feature.id],
                    strategy=strategy,
                    tool=ToolAssignment(
                        tool_id=tool.id,
                        station_id=assign.station_id,
                        t_code=t_code,
                        candidates=cand_ids,
                    ),
                    cut=use_cut,
                    order=oid,
                    audit=[
                        AuditReason(
                            rule="layout_type_match",
                            inputs={
                                "feature": feature.id,
                                "kind": feature.kind.value,
                                "tool": tool.id,
                                "priority": priority.value,
                            },
                            score=best[0],
                            message=f"Selected {tool.id} at {assign.station_id} for {feature.kind.value}",
                        )
                    ],
                )
            )
            oid += 1

    return ops, unmet
