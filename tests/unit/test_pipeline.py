from __future__ import annotations

from pathlib import Path

import pytest

from swisscam.domain.models import FeatureKind, Priority
from swisscam.features.recognize import recognize_profile
from swisscam.io.store import load_model
from swisscam.domain.models import PartModel
from swisscam.pipeline.run import run_from_paths

ROOT = Path(__file__).resolve().parents[2]


def test_recognize_demo_pin_has_core_features() -> None:
    part = load_model(ROOT / "examples" / "demo_pin.json", PartModel)
    features = recognize_profile(part)
    kinds = {f.kind for f in features}
    assert FeatureKind.FACE in kinds
    assert FeatureKind.OD_CYLINDER in kinds
    assert FeatureKind.CUTOFF_PLANE in kinds
    assert FeatureKind.GROOVE in kinds


def test_pipeline_generates_gcode_with_waits() -> None:
    result = run_from_paths(
        part_path=ROOT / "examples" / "demo_pin.json",
        machine_path=ROOT / "data" / "machines" / "citizen_l20_viii.json",
        layout_path=ROOT / "data" / "tools" / "sample_layout.json",
        crib_path=ROOT / "data" / "tools" / "sample_crib.json",
        post_path=ROOT / "data" / "posts" / "citizen_meldas_l20.json",
        materials_path=ROOT / "data" / "materials" / "default.json",
        priority=Priority.FASTEST_CYCLE,
        override_export=True,
    )
    assert result.features
    assert result.plan.operations
    assert result.toolpaths
    assert "!W1" in result.gcode
    assert "!W2" in result.gcode
    assert "$1" in result.gcode and "$2" in result.gcode
    assert "G00" in result.gcode and "G01" in result.gcode
    assert result.gcode.strip().endswith("%")


def test_path_safety_rejects_bad_name(tmp_path: Path) -> None:
    from swisscam.io.store import assert_safe_filename

    with pytest.raises(ValueError):
        assert_safe_filename("../evil.cnc")
