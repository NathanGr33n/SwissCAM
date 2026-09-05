"""Core domain models for SwissCAM (JSON-serializable, pure data)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SCHEMA_VERSION = "1.0"


class FeatureKind(str, Enum):
    FACE = "face"
    OD_CYLINDER = "od_cylinder"
    OD_TAPER = "od_taper"
    CHAMFER = "chamfer"
    RADIUS = "radius"
    GROOVE = "groove"
    UNDERCUT = "undercut"
    THREAD_EXT = "thread_ext"
    ID_BORE = "id_bore"
    ID_GROOVE = "id_groove"
    CENTER_DRILL = "center_drill"
    CUTOFF_PLANE = "cutoff_plane"
    CROSS_HOLE = "cross_hole"
    FLAT = "flat"
    SLOT = "slot"
    OTHER = "other"


class ToolType(str, Enum):
    OD_TURN = "od_turn"
    ID_BORE = "id_bore"
    GROOVE = "groove"
    THREAD = "thread"
    DRILL = "drill"
    CENTER_DRILL = "center_drill"
    END_MILL = "end_mill"
    CUTOFF = "cutoff"
    OTHER = "other"


class SpindleSide(str, Enum):
    MAIN = "main"
    SUB = "sub"
    EITHER = "either"


class Strategy(str, Enum):
    FACE = "face"
    ROUGH = "rough"
    FINISH = "finish"
    GROOVE = "groove"
    THREAD = "thread"
    DRILL = "drill"
    CUTOFF = "cutoff"
    PICKUP = "pickup"
    BACK = "back"
    OTHER = "other"


class Priority(str, Enum):
    FEWEST_TOOLS = "fewest_tools"
    BEST_FINISH = "best_finish"
    FASTEST_CYCLE = "fastest_cycle"


class MotionType(str, Enum):
    RAPID = "rapid"
    FEED = "feed"
    ARC_CW = "arc_cw"
    ARC_CCW = "arc_ccw"
    DWELL = "dwell"


class DocumentBase(BaseModel):
    schema_version: str = SCHEMA_VERSION


class AxisSpec(BaseModel):
    name: str
    min_mm: float | None = None
    max_mm: float | None = None
    rapid_m_per_min: float | None = None


class SpindleSpec(BaseModel):
    name: str
    rpm_max: float
    power_kw: list[float] = Field(default_factory=list)


class BarSpec(BaseModel):
    max_diameter_mm: float
    optional_max_diameter_mm: float | None = None
    gb_max_length_mm: float
    gbl_max_length_mm: float
    modes: list[str] = Field(default_factory=lambda: ["GB", "GBL"])
    max_unsupported_stickout_mm: float = 25.0


class StationSpec(BaseModel):
    id: str
    zone: Literal["gang", "front", "back"]
    index: int = 0
    live: bool = False
    x_mm: float = 0.0
    z_mm: float = 0.0
    y_mm: float = 0.0


class ToolingTopology(BaseModel):
    stations: list[StationSpec] = Field(default_factory=list)


class ClearanceBox(BaseModel):
    name: str
    x_min_mm: float
    x_max_mm: float
    z_min_mm: float
    z_max_mm: float
    y_min_mm: float = -50.0
    y_max_mm: float = 50.0


class Capabilities(BaseModel):
    c_axis: bool = True
    spindle_sync: bool = True
    superimpose: bool = False
    cross_work: bool = False
    lfv: bool = False
    b_axis: bool = False
    multi_system: bool = True


class MachineProfile(DocumentBase):
    id: str
    name: str
    vendor: str = "Citizen"
    model: str = "L20"
    control_family: str = "meldas_citizen_multi_system"
    axes: list[AxisSpec] = Field(default_factory=list)
    spindles: list[SpindleSpec] = Field(default_factory=list)
    bar: BarSpec
    tooling: ToolingTopology = Field(default_factory=ToolingTopology)
    clearances: list[ClearanceBox] = Field(default_factory=list)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    default_post_id: str = "citizen_meldas_l20"
    notes: str = ""


class MaterialCutData(BaseModel):
    material_class: str
    surface_m_per_min: float | None = None
    rpm_cap: float | None = None
    feed_mm_rev: float = 0.1
    doc_mm: float = 0.5
    max_rpm: float | None = None


class ToolCribEntry(DocumentBase):
    id: str
    name: str
    tool_type: ToolType
    holder: str = ""
    insert: str = ""
    nose_radius_mm: float = 0.2
    tip_angle_deg: float | None = None
    min_width_mm: float | None = None
    max_width_mm: float | None = None
    max_doc_mm: float = 1.5
    max_bore_depth_mm: float | None = None
    drill_diameter_mm: float | None = None
    offsets: dict[str, float] = Field(default_factory=lambda: {"x_mm": 0.0, "z_mm": 0.0})
    materials: list[MaterialCutData] = Field(default_factory=list)
    notes: str = ""


class ToolCrib(DocumentBase):
    id: str
    name: str
    tools: list[ToolCribEntry] = Field(default_factory=list)


class LayoutAssignment(BaseModel):
    station_id: str
    tool_id: str
    offset_overrides: dict[str, float] = Field(default_factory=dict)
    t_code: str | None = None


class Layout(DocumentBase):
    id: str
    name: str
    machine_profile_id: str
    assignments: list[LayoutAssignment] = Field(default_factory=list)


class ProfilePoint(BaseModel):
    """XZ half-profile point; X is radius (mm), Z along axis (mm)."""

    z_mm: float
    x_radius_mm: float


class StockDef(BaseModel):
    diameter_mm: float
    material_id: str = "generic_steel"
    length_mm: float | None = None
    allowance_face_mm: float = 0.2


class PartModel(DocumentBase):
    id: str
    name: str
    source_path: str | None = None
    units: Literal["mm"] = "mm"
    profile: list[ProfilePoint] = Field(default_factory=list)
    stock: StockDef
    notes: str = ""

    @field_validator("profile")
    @classmethod
    def sorted_profile_hint(cls, v: list[ProfilePoint]) -> list[ProfilePoint]:
        return v


class Feature(BaseModel):
    id: str
    kind: FeatureKind
    z0_mm: float
    z1_mm: float
    diameter_mm: float | None = None
    diameter2_mm: float | None = None
    width_mm: float | None = None
    depth_mm: float | None = None
    pitch_mm: float | None = None
    side: SpindleSide = SpindleSide.MAIN
    source: Literal["auto", "manual"] = "auto"
    confidence: float = 1.0
    locked: bool = False
    flags: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class AuditReason(BaseModel):
    rule: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    message: str = ""


class ToolAssignment(BaseModel):
    tool_id: str
    station_id: str
    t_code: str
    candidates: list[str] = Field(default_factory=list)


class CutParams(BaseModel):
    surface_m_per_min: float | None = None
    rpm: float | None = None
    feed_mm_rev: float = 0.1
    doc_mm: float = 0.5
    stock_allowance_mm: float = 0.2
    css: bool = True


class Operation(BaseModel):
    id: str
    feature_ids: list[str] = Field(default_factory=list)
    strategy: Strategy
    tool: ToolAssignment | None = None
    cut: CutParams = Field(default_factory=CutParams)
    spindle_side: SpindleSide = SpindleSide.MAIN
    system: str = "$1"
    order: int = 0
    locked: bool = False
    audit: list[AuditReason] = Field(default_factory=list)
    notes: str = ""


class Barrier(BaseModel):
    id: str
    systems: list[str]
    kind: str = "wait"


class ModeSegment(BaseModel):
    mode: str
    from_op: str | None = None
    to_op: str | None = None
    note: str = ""


class ProcessPlan(DocumentBase):
    id: str
    operations: list[Operation] = Field(default_factory=list)
    barriers: list[Barrier] = Field(default_factory=list)
    mode_segments: list[ModeSegment] = Field(default_factory=list)
    cycle_time_s: float | None = None
    bar_usage_mm: float | None = None
    unmet_features: list[str] = Field(default_factory=list)


class PathSegment(BaseModel):
    motion: MotionType
    x_diam_mm: float | None = None
    z_mm: float | None = None
    i_mm: float | None = None
    k_mm: float | None = None
    feed_mm_rev: float | None = None
    feed_mm_min: float | None = None
    rpm: float | None = None
    css_m_per_min: float | None = None
    dwell_s: float | None = None
    comment: str | None = None


class Toolpath(BaseModel):
    operation_id: str
    tool_id: str
    t_code: str
    segments: list[PathSegment] = Field(default_factory=list)
    estimated_time_s: float = 0.0


class Diagnostic(BaseModel):
    level: Literal["info", "warning", "error"]
    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class SimulationReport(BaseModel):
    ok: bool
    level_reached: str = "L0"
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    override_export: bool = False


class IRBlock(BaseModel):
    kind: Literal["motion", "mcode", "gcode", "wait", "mode", "comment", "tool", "spindle"]
    text: str | None = None
    m: int | None = None
    g: str | None = None
    wait_id: str | None = None
    mode: str | None = None
    segment: PathSegment | None = None
    t_code: str | None = None
    rpm: float | None = None
    css: float | None = None


class IRSystem(BaseModel):
    name: str
    blocks: list[IRBlock] = Field(default_factory=list)


class ProgramIR(DocumentBase):
    program_name: str
    revision: str = "A"
    machine_id: str
    layout_id: str
    material_id: str
    stock_diameter_mm: float
    cycle_time_s: float | None = None
    bar_usage_mm: float | None = None
    tool_list: list[dict[str, Any]] = Field(default_factory=list)
    systems: list[IRSystem] = Field(default_factory=list)
    simulation: SimulationReport | None = None
    swisscam_version: str = "0.1.0"


class MaterialLibraryEntry(BaseModel):
    id: str
    name: str
    class_name: str
    density_g_cm3: float | None = None
    default_sfm: float = 120.0
    default_feed_mm_rev: float = 0.12
    default_doc_mm: float = 0.8


class MaterialLibrary(DocumentBase):
    id: str
    materials: list[MaterialLibraryEntry] = Field(default_factory=list)


class PostConfig(DocumentBase):
    id: str
    name: str
    control_family: str
    diameter_mode: bool = True
    absolute: bool = True
    units: Literal["mm", "inch"] = "mm"
    program_number: int = 1000
    z0_policy: str = "part_face"
    systems: list[str] = Field(default_factory=lambda: ["$1", "$2"])
    g_map: dict[str, str] = Field(default_factory=dict)
    m_map: dict[str, int] = Field(default_factory=dict)
    wait_format: str = "!{id}"
    mode_codes: dict[str, str] = Field(default_factory=dict)
    header_template: str = ""
    footer_template: str = ""
    number_format: str = "0.001"
    line_numbers: bool = False
    comments: bool = True
