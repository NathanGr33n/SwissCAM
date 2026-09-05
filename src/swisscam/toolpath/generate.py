"""Generate turning toolpaths from operations and features."""

from __future__ import annotations

import math

from swisscam.domain.models import (
    Feature,
    FeatureKind,
    MotionType,
    Operation,
    PartModel,
    PathSegment,
    Strategy,
    Toolpath,
)


def _rpm_from_css(css_m_per_min: float, diameter_mm: float, rpm_max: float = 10000.0) -> float:
    if diameter_mm <= 1e-6:
        return min(rpm_max, 1000.0)
    rpm = (css_m_per_min * 1000.0) / (math.pi * diameter_mm)
    return max(50.0, min(rpm_max, rpm))


def _est_time(segments: list[PathSegment], default_rpm: float = 2000.0) -> float:
    t = 0.0
    x = 0.0
    z = 0.0
    for seg in segments:
        if seg.motion == MotionType.DWELL and seg.dwell_s:
            t += seg.dwell_s
            continue
        nx = seg.x_diam_mm if seg.x_diam_mm is not None else x
        nz = seg.z_mm if seg.z_mm is not None else z
        dist = math.hypot((nx - x) / 2.0, nz - z)  # X as diameter -> radius delta
        if seg.motion == MotionType.RAPID:
            t += dist / 500.0  # mm / (mm/s) crude
        else:
            feed = seg.feed_mm_rev or 0.1
            rpm = seg.rpm or default_rpm
            mm_min = feed * rpm
            t += 0.0 if mm_min <= 1e-6 else (dist / mm_min) * 60.0
        x, z = nx, nz
    return t


def _od_passes(
    feature: Feature,
    op: Operation,
    stock_dia: float,
) -> list[PathSegment]:
    assert feature.diameter_mm is not None
    target = feature.diameter_mm
    if op.strategy == Strategy.ROUGH:
        target = feature.diameter_mm + 2.0 * op.cut.stock_allowance_mm
    z0, z1 = feature.z0_mm, feature.z1_mm
    if z1 < z0:
        z0, z1 = z1, z0
    doc = max(0.05, op.cut.doc_mm)
    css = op.cut.surface_m_per_min or 120.0
    feed = op.cut.feed_mm_rev
    segs: list[PathSegment] = []
    clear_x = stock_dia + 2.0
    segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=clear_x, z_mm=z0 - 1.0, comment="approach"))
    current = stock_dia
    while current - doc > target + 1e-6:
        current -= doc
        rpm = _rpm_from_css(css, current)
        segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=current, z_mm=z0 - 0.5))
        segs.append(
            PathSegment(
                motion=MotionType.FEED,
                x_diam_mm=current,
                z_mm=z1,
                feed_mm_rev=feed,
                css_m_per_min=css,
                rpm=rpm,
            )
        )
        segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=clear_x, z_mm=z1))
        segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=clear_x, z_mm=z0 - 0.5))
    rpm = _rpm_from_css(css, target)
    segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=target, z_mm=z0 - 0.2))
    segs.append(
        PathSegment(
            motion=MotionType.FEED,
            x_diam_mm=target,
            z_mm=z1,
            feed_mm_rev=feed if op.strategy == Strategy.ROUGH else max(0.05, feed * 0.6),
            css_m_per_min=css,
            rpm=rpm,
            comment=op.strategy.value,
        )
    )
    segs.append(PathSegment(motion=MotionType.RAPID, x_diam_mm=clear_x, z_mm=z1, comment="retract"))
    return segs


def _face_path(feature: Feature, op: Operation, stock_dia: float) -> list[PathSegment]:
    css = op.cut.surface_m_per_min or 120.0
    feed = op.cut.feed_mm_rev
    z = feature.z0_mm
    rpm = _rpm_from_css(css, stock_dia)
    return [
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 2.0, z_mm=z - 1.0),
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 0.5, z_mm=z),
        PathSegment(
            motion=MotionType.FEED,
            x_diam_mm=0.0,
            z_mm=z,
            feed_mm_rev=feed,
            css_m_per_min=css,
            rpm=rpm,
            comment="face",
        ),
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 2.0, z_mm=z - 1.0),
    ]


def _groove_path(feature: Feature, op: Operation, stock_dia: float) -> list[PathSegment]:
    css = op.cut.surface_m_per_min or 100.0
    feed = op.cut.feed_mm_rev
    z_mid = 0.5 * (feature.z0_mm + feature.z1_mm)
    target = feature.diameter_mm or (stock_dia - (feature.depth_mm or 1.0))
    rpm = _rpm_from_css(css, stock_dia)
    return [
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 2.0, z_mm=z_mid),
        PathSegment(
            motion=MotionType.FEED,
            x_diam_mm=target,
            z_mm=z_mid,
            feed_mm_rev=feed,
            css_m_per_min=css,
            rpm=rpm,
            comment="groove plunge",
        ),
        PathSegment(motion=MotionType.DWELL, dwell_s=0.1),
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 2.0, z_mm=z_mid),
    ]


def _cutoff_path(feature: Feature, op: Operation, stock_dia: float) -> list[PathSegment]:
    css = op.cut.surface_m_per_min or 80.0
    feed = min(0.05, op.cut.feed_mm_rev)
    z = feature.z0_mm
    rpm = _rpm_from_css(css, stock_dia)
    return [
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 2.0, z_mm=z),
        PathSegment(
            motion=MotionType.FEED,
            x_diam_mm=-0.5,
            z_mm=z,
            feed_mm_rev=feed,
            css_m_per_min=css,
            rpm=rpm,
            comment="cutoff",
        ),
        PathSegment(motion=MotionType.RAPID, x_diam_mm=stock_dia + 4.0, z_mm=z),
    ]


def generate_toolpaths(
    operations: list[Operation],
    features: list[Feature],
    part: PartModel,
) -> list[Toolpath]:
    feat_by_id = {f.id: f for f in features}
    stock_dia = part.stock.diameter_mm
    paths: list[Toolpath] = []

    for op in operations:
        if not op.tool:
            continue
        feature = feat_by_id.get(op.feature_ids[0]) if op.feature_ids else None
        if feature is None:
            continue
        if op.strategy == Strategy.FACE or feature.kind == FeatureKind.FACE:
            segs = _face_path(feature, op, stock_dia)
        elif op.strategy == Strategy.GROOVE or feature.kind == FeatureKind.GROOVE:
            segs = _groove_path(feature, op, stock_dia)
        elif op.strategy == Strategy.CUTOFF or feature.kind == FeatureKind.CUTOFF_PLANE:
            segs = _cutoff_path(feature, op, stock_dia)
        elif feature.kind in (
            FeatureKind.OD_CYLINDER,
            FeatureKind.OD_TAPER,
            FeatureKind.CHAMFER,
            FeatureKind.RADIUS,
        ):
            segs = _od_passes(feature, op, stock_dia)
        else:
            segs = [
                PathSegment(
                    motion=MotionType.RAPID,
                    x_diam_mm=stock_dia + 2.0,
                    z_mm=feature.z0_mm,
                    comment=f"unsupported {feature.kind.value}",
                )
            ]
        paths.append(
            Toolpath(
                operation_id=op.id,
                tool_id=op.tool.tool_id,
                t_code=op.tool.t_code,
                segments=segs,
                estimated_time_s=_est_time(segs),
            )
        )
    return paths
