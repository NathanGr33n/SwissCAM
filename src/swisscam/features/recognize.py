"""Recognize turned features from an XZ half-profile (radius vs Z)."""

from __future__ import annotations

from swisscam.domain.models import Feature, FeatureKind, PartModel, ProfilePoint, SpindleSide


def _seg_kind(p0: ProfilePoint, p1: ProfilePoint, stock_r: float) -> tuple[FeatureKind, float]:
    dz = p1.z_mm - p0.z_mm
    dr = p1.x_radius_mm - p0.x_radius_mm
    abs_dz = abs(dz)
    abs_dr = abs(dr)

    if abs_dz < 1e-9 and abs_dr < 1e-9:
        return FeatureKind.OTHER, 0.2

    # Face-like (radial move, little Z)
    if abs_dz <= 1e-6 and abs_dr > 1e-6:
        return FeatureKind.FACE, 0.95

    # Near-vertical OD cylinder
    if abs_dr <= 1e-4 and abs_dz > 1e-6:
        return FeatureKind.OD_CYLINDER, 0.95

    # Short steep chamfer
    if abs_dz > 1e-6 and abs_dr != 0 and abs_dz <= 3.0 and abs(abs_dr / abs_dz) >= 0.3:
        return FeatureKind.CHAMFER, 0.8

    # Taper
    if abs_dz > 1e-6 and abs_dr != 0:
        return FeatureKind.OD_TAPER, 0.75

    return FeatureKind.OTHER, 0.4


def recognize_profile(part: PartModel, *, groove_max_width_mm: float = 6.0) -> list[Feature]:
    """Decompose sorted profile polyline into turned features + cutoff plane."""
    pts = sorted(part.profile, key=lambda p: p.z_mm)
    if len(pts) < 2:
        raise ValueError("Part profile needs at least two points")

    stock_r = part.stock.diameter_mm / 2.0
    features: list[Feature] = []
    fid = 1

    # Face at minimum Z (bar end / part face convention: z increases into bar)
    z_min = pts[0].z_mm
    z_max = pts[-1].z_mm
    max_dia = max(p.x_radius_mm for p in pts) * 2.0

    features.append(
        Feature(
            id=f"F{fid:03d}",
            kind=FeatureKind.FACE,
            z0_mm=z_min,
            z1_mm=z_min,
            diameter_mm=max_dia,
            side=SpindleSide.MAIN,
            confidence=1.0,
            flags=["auto_face"],
        )
    )
    fid += 1

    i = 0
    while i < len(pts) - 1:
        p0 = pts[i]
        p1 = pts[i + 1]
        kind, conf = _seg_kind(p0, p1, stock_r)
        dia = max(p0.x_radius_mm, p1.x_radius_mm) * 2.0
        width = abs(p1.z_mm - p0.z_mm)

        # Detect groove: valley relative to neighbors (narrow OD dip)
        if (
            i > 0
            and i < len(pts) - 2
            and p0.x_radius_mm < pts[i - 1].x_radius_mm - 1e-4
            and p1.x_radius_mm <= p0.x_radius_mm + 1e-4
        ):
            # look ahead for climb back out
            j = i + 1
            while j < len(pts) - 1 and pts[j].x_radius_mm <= p0.x_radius_mm + 1e-3:
                j += 1
            groove_w = abs(pts[min(j, len(pts) - 1)].z_mm - p0.z_mm)
            if groove_w <= groove_max_width_mm:
                depth = (pts[i - 1].x_radius_mm - min(p.x_radius_mm for p in pts[i : j + 1])) * 2.0
                features.append(
                    Feature(
                        id=f"F{fid:03d}",
                        kind=FeatureKind.GROOVE,
                        z0_mm=p0.z_mm,
                        z1_mm=pts[min(j, len(pts) - 1)].z_mm,
                        diameter_mm=min(p.x_radius_mm for p in pts[i : j + 1]) * 2.0,
                        width_mm=groove_w,
                        depth_mm=max(depth, 0.0),
                        confidence=0.7,
                        flags=["auto_groove"],
                    )
                )
                fid += 1
                i = max(j, i + 1)
                continue

        if kind != FeatureKind.FACE:
            features.append(
                Feature(
                    id=f"F{fid:03d}",
                    kind=kind,
                    z0_mm=min(p0.z_mm, p1.z_mm),
                    z1_mm=max(p0.z_mm, p1.z_mm),
                    diameter_mm=dia,
                    diameter2_mm=min(p0.x_radius_mm, p1.x_radius_mm) * 2.0
                    if kind in (FeatureKind.OD_TAPER, FeatureKind.CHAMFER)
                    else None,
                    width_mm=width if width > 0 else None,
                    confidence=conf,
                )
            )
            fid += 1
        i += 1

    features.append(
        Feature(
            id=f"F{fid:03d}",
            kind=FeatureKind.CUTOFF_PLANE,
            z0_mm=z_max,
            z1_mm=z_max,
            diameter_mm=part.stock.diameter_mm,
            side=SpindleSide.MAIN,
            confidence=1.0,
            flags=["auto_cutoff"],
        )
    )

    # Merge consecutive OD cylinders with same diameter
    merged: list[Feature] = []
    for feat in features:
        if (
            merged
            and feat.kind == FeatureKind.OD_CYLINDER
            and merged[-1].kind == FeatureKind.OD_CYLINDER
            and feat.diameter_mm is not None
            and merged[-1].diameter_mm is not None
            and abs(feat.diameter_mm - merged[-1].diameter_mm) < 1e-4
            and abs(feat.z0_mm - merged[-1].z1_mm) < 1e-4
        ):
            merged[-1].z1_mm = feat.z1_mm
            continue
        merged.append(feat)
    return merged


def part_length_mm(part: PartModel) -> float:
    if not part.profile:
        return part.stock.length_mm or 0.0
    zs = [p.z_mm for p in part.profile]
    return max(zs) - min(zs)
