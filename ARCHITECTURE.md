# SwissCAM Architecture

**Product:** CAD-to-G-code CAM for Swiss-type (sliding headstock) screw machines  
**Companion docs:** `PRD.md` (requirements), `RESEARCH.md` (Citizen/Meldas facts)  
**Status:** Architecture v1.0 — implementation baseline

---

## 1. Problem framing

SwissCAM is not general mill-turn CAM with a Swiss checkbox. The product centers on:

1. What tools are **physically installed** (crib + layout).
2. What the **machine kinematics** allow (guide bushing, sub-spindle, gang envelope).
3. Turning-first feature intent from CAD, then live-tool features.
4. A process plan that becomes **control-faithful G-code** through editable posts.

Success is time-to-safe-program for owner-operators and small job shops — not enterprise breadth.

---

## 2. What the final product actually requires

### 2.1 Must-have subsystems

| Subsystem | Why it is required |
|---|---|
| Machine Profile store | Encodes travel, spindles, GB/GBL, tooling topology, control binding |
| Tool Crib + Layout | Selection is against installed positions, not abstract catalogs |
| CAD import (STEP first) | Solid geometry source of truth |
| Feature recognition + manual override | Auto for OD/ID/groove/face/thread; override for ambiguity (PRD risk #1) |
| Tool selection engine | Ranked candidates + unmet-feature reports |
| Process planner | Swiss sequence conventions; barriers for future multi-system |
| Toolpath generators | Turning first; live-tool later — same path IR |
| Constraint / sim gate | Bushing stick-out, travel, tool-tool, export lock (FR-35) |
| Post framework | Data-driven G/M maps; multi-system ready IR |
| Project / library I/O | JSON portability, offline-first |
| Audit trail | Why each tool/sequence choice was made (NFR-6) |
| Cycle time + bar usage | Quoting workflow |

### 2.2 Explicitly not required for effective v1

- Cloud CAM dependency
- 5-axis surface strategies
- DNC / live machine telemetry
- Multi-part bar nesting across SKUs
- Perfect PMI/GD&T (manual tolerance fields acceptable early)
- Dozens of factory-validated posts (framework + L20 Meldas + Fanuc-style stub)

### 2.3 Phase mapping (aligned to PRD §9)

| Phase | Ships | Architecture obligation now |
|---|---|---|
| **1 MVP** | Profiles, crib/layout, STEP, turn features, sequential plan, turn paths, sim flags, one Citizen/Meldas post | Domain + pipeline + IR + post engine |
| **2** | Back-work, sync, cross-work, Fanuc post | Multi-system IR, waits, modes, superimposition sim |
| **3** | C-axis milling depth, thread library, traveler export | Live-tool path families |
| **4** | Optimizer, post authoring toolkit, multi-seat lib sync | Pluggable scorers; post SDK |

---

## 3. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  UI / CLI  (Phase 1: CLI; later PySide or web shell)             │
└─────────────────────────────┬───────────────────────────────────┘
                              │ commands / DTOs
┌─────────────────────────────▼───────────────────────────────────┐
│  Application services (use-cases)                               │
│  ImportPart | Recognize | AssignTools | Plan | Generate | Post  │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │          │
┌──────▼──┐ ┌─────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────────────┐
│Geometry │ │Features  │ │Tools   │ │Planning│ │Toolpath+Sim     │
│OCC/OCP  │ │recognize │ │select  │ │sequence│ │paths, estimates │
└──────┬──┘ └─────┬────┘ └───┬────┘ └───┬────┘ └──┬──────────────┘
       │          │          │          │         │
       └──────────┴──────────┴──────────┴────┬────┘
                                             │ canonical IR
                                    ┌────────▼────────┐
                                    │ Post engine     │
                                    │ templates+maps  │
                                    └────────┬────────┘
                                             │ NC text
                                    ┌────────▼────────┐
                                    │ Project store   │
                                    │ JSON libraries  │
                                    └─────────────────┘
```

**Rules:**

- Domain objects are pure data (no UI, no file IO inside entities).
- Pipeline stages are pure functions: `in + config → out + diagnostics + audit`.
- G-code is never generated from ad-hoc string concat inside planners.
- Geometry kernel is isolated behind ports so tests can use synthetic profiles without OCC.

---

## 4. Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Fast iteration, strong scientific/CAD bindings, easy JSON tooling |
| Packaging | `src/swisscam` + `pyproject.toml` (hatch/setuptools) | Standard installable package |
| Geometry | OpenCascade via **cadquery/OCP** (optional extra); profile fallback without OCC | STEP AP203/214; face classification |
| Schemas | Pydantic v2 models ↔ JSON | Validation, portability (NFR-4) |
| Posts | YAML/JSON maps + Jinja2 templates | Shop-editable (FR-31) |
| CLI | Typer or argparse | MVP workflow without GUI tax |
| Tests | pytest + golden NC files | Regression on posts |
| UI (later) | PySide6 or thin local web | Not blocking kernel |
| Units | Internal **millimetres**; inch at boundaries | Single source of truth |

GPU is not required for core CAM (NFR-1).

---

## 5. Domain model

### 5.1 Core entities

```
MachineProfile
  id, name, vendor, model, control_family
  axes[] {name, min, max, rapid_mm_min}
  spindles {main, sub, live_groups[]}
  bar {max_diameter_mm, gb_max_length_mm, gbl_max_length_mm, modes[]}
  tooling_topology {zones[]: gang|front|back, stations[]}
  clearances {guide_bushing, collets, envelopes}
  capabilities {c_axis, sync, superimpose, cross_work, lfv, b_axis}
  default_post_id

ToolCribEntry
  id, type (od_turn|id_bore|groove|thread|drill|end_mill|cutoff|...)
  holder, insert, nose_radius_mm, geometry limits
  offsets {x_mm, z_mm}  # crib defaults
  materials[] {material_class, sfm_or_rpm, feed_mm_rev, doc_mm, max_rpm}
  life_optional

Layout
  id, machine_profile_id, name
  assignments[] {station_id, tool_id, offset_overrides}
  conflict diagnostics on save

PartModel
  id, source path, units
  solid_ref / profile_polylines
  stock {diameter_mm, material_id, length_mode}
  tolerances[] (manual or PMI later)

Feature
  id, kind, params (dia, z0, z1, width, pitch, ...)
  side (main|sub|either)
  source (auto|manual)
  faces/edges refs
  confidence, flags[]

Operation
  id, feature_ids[], tool_assignment
  strategy (rough|finish|groove|thread|drill|cutoff|...)
  cut_params resolved
  spindle_side, system_hint
  audit {reasons[]}

ProcessPlan
  operations[] ordered
  barriers[] {id, participants systems}
  mode_segments[] {mode, span}
  locks[] (user-pinned order)
  estimates {cycle_s, bar_mm}

Toolpath
  segments[] {motion rapid|feed|arc, x_diam_mm, z_mm, f, s, c?}
  meta {op_id, tool_id}

ProgramIR
  headers meta
  systems[] {name, blocks[]}
  blocks = paths + m_codes + waits + mode_calls
  simulation_status

PostConfig
  id, control_family
  g_map, m_map, modal defaults
  multi_system rules, templates
  z0_policy, diameter_mode, program number style
```

### 5.2 Feature kinds (Phase 1 solid set)

`face`, `od_cylinder`, `od_taper`, `chamfer`, `radius`, `groove`, `undercut`, `thread_ext`, `id_bore`, `id_groove`, `center_drill`, `cutoff_plane`  
Phase 2+: `cross_hole`, `flat`, `slot`, `hex`, `back_*` variants.

---

## 6. Pipeline design

### 6.1 Stages

1. **Import** — STEP → B-rep; heal; unit detect; bbox vs bar capacity warnings; optional DXF profile overlay later.
2. **Stock** — user stock or smallest standard bar enclosing OD.
3. **Recognize** — rotational decomposition along Z; confidence scores; ambiguous → `needs_review`.
4. **Override** — user tags faces/params; re-validate.
5. **SelectTools** — candidates from **active Layout only**; rank by reach, DOC, finish, change count.
6. **Sequence** — Swiss default order; insert bar feed / cutoff / pickup placeholders; user locks.
7. **Toolpath** — generate path segments; apply material table feeds/speeds.
8. **Simulate** — backplot + constraint checks; set `simulation_status`.
9. **Post** — IR → NC text; header with tools, stock, cycle time, revision.
10. **Diff** (later) — block-level compare to prior export.

### 6.2 Swiss default sequence (Phase 1)

```
face / center
→ rough OD (main)
→ rough ID (if any)
→ grooves / threads
→ finish OD/ID
→ (Phase 2 cross-work)
→ sub pickup + sync
→ cutoff
→ back-working
→ eject / count
```

Phase 1 may emit sequential single-system-first NC with explicit TODO markers for multi-system expansion, **or** emit multi-system skeletons with waits already paired (preferred once post maps exist). Architecture prefers **paired waits from day one** even if `$2` is mostly dwell/safe.

### 6.3 Audit

Every auto decision attaches:

```json
{
  "rule": "prefer_finishing_insert_for_tol_lt",
  "inputs": {"tol_mm": 0.01, "tool_id": "T0303"},
  "score": 0.82
}
```

Surfaced in CLI as `swisscam explain op-12`.

---

## 7. Geometry & feature recognition strategy

### 7.1 Turn-first approach (efficient and sufficient)

Most Swiss bar work is dominated by **axisymmetric profiles**. Pipeline:

1. Detect primary axis (fit cylinders/planes; assume Z along bar).
2. Extract silhouette / revolve profile (XZ half-profile).
3. Segment profile into line/arc primitives.
4. Classify: face, OD step, taper, chamfer, groove (narrow valley), thread candidates (helical edges or user).
5. ID features from inner profile if hollow.
6. Non-rotational faces → Phase 2 live-tool queue (flag early, do not fail Phase 1 turn export if turn-only mode).

### 7.2 Manual override

First-class: attach `Feature` to face ids or sketch segments; lock kind/params; recognition never silently overwrites locks.

### 7.3 Performance budget

≤50 features → recognize + select < 15 s on CPU (NFR-1). Profile extraction and rule classifiers stay O(faces + edges); avoid full volumetric meshing on hot path.

---

## 8. Tool selection & planning

### 8.1 Feasibility filters

- Type match (groove tool width ≤ groove width, etc.).
- Reach / stick-out vs feature depth.
- Station side (main gang vs back).
- RPM/DOC vs material table and machine caps.
- Holder collision envelope vs neighbors (layout-time + path-time).

### 8.2 Ranking objectives (user weight)

`fewest_tools` | `best_finish` | `fastest_cycle` (PRD FR-17).

### 8.3 Unmet features

Hard stop before toolpath: list feature id, geometry highlight ref, suggested tool class string.

---

## 9. Toolpath & simulation

### 9.1 Path IR

Motion in **diameter X**, Z along part; feed modes CSS or RPM resolved before post.

Strategies Phase 1:

- OD rough (stock allowance, multiple passes)
- OD finish
- Face
- Groove (plunge or multi-pass)
- Thread (multi-pass depth chart)
- Cutoff
- Simple drill (peck optional)

### 9.2 Guide bushing constraints

- Max unsupported stick-out from bushing face per op class.
- Reject or warn when finish pass requires protrusion beyond machine GB length without rechuck plan.

### 9.3 Simulation levels

| Level | Phase | Checks |
|---|---|---|
| L0 backplot | 1 | Travel limits, NaN, empty paths |
| L1 envelopes | 1 | Tool vs bushing box, gang neighbors AABB |
| L2 solid removal | 2–3 | Stock boolean / mesh |
| L3 multi-system | 2 | Waits, modes, superimposition composition |

Export default: require L0+L1 clear or explicit override log.

---

## 10. Post-processor architecture

### 10.1 Principles

- Kernel emits **ProgramIR**, not Citizen strings.
- PostConfig supplies: address formats, M maps, system headers (`$1`), wait syntax, mode calls, tool change blocks, header/footer templates.
- One engine; many configs under `data/posts/`.

### 10.2 MVP posts

1. `citizen_meldas_l20` — diameter mode, CSS, turning moves, chuck/spindle M defaults from research maps, multi-system skeleton with safe `$2` waits.
2. `fanuc_swiss_generic` — Fanuc-like G96/G99 turning dialect for shops on Fanuc-style controls (Phase 2 complete validation).

### 10.3 Header content (FR-32)

Program name/rev, machine id, layout id, tool list with stations/offsets, material/stock, estimated cycle time, SwissCAM version, simulation status, override flags.

---

## 11. Repository layout

```
SwissCAM/
  README.md
  ARCHITECTURE.md
  RESEARCH.md
  PRD.md                 # local design doc (may stay gitignored)
  pyproject.toml
  .gitignore
  src/swisscam/
    __init__.py
    domain/              # pydantic models
    geometry/            # import, profile extract
    features/            # recognition, overrides
    tools/               # crib, layout, selection
    planning/            # sequencing, estimates
    toolpath/            # generators
    simulate/            # checks
    post/                # engine + loaders
    io/                  # project json
    pipeline/            # orchestrate stages
    cli/                 # entrypoints
  data/
    machines/
    posts/
    materials/
    tools/               # optional catalog seeds
  tests/
    unit/
    golden/
  examples/
```

---

## 12. Security, safety, and quality

- **No secrets** in repo; ignore `.env`, licenses, shop proprietary posts if marked private.
- **Path safety:** refuse writes outside project root; sanitize NC file names.
- **G-code safety:** simulation gate; warn on missing waits in multi-system IR; never invent spindle-off while dual-chuck assumed.
- **Determinism:** stable ordering for golden tests; seed-free geometry ops where possible.
- **Validation:** pydantic on all loaded JSON; schema version field on every document.
- **Logging:** structured diagnostics; no silent catch-and-continue on geometry failures.

---

## 13. CLI happy path (PRD §8)

```bash
swisscam machine load data/machines/citizen_l20_viii.json
swisscam layout load ./shop/layout_a.json
swisscam part import part.step --stock-dia 12 --material 304SS
swisscam recognize
swisscam features list
swisscam tools assign --priority fastest_cycle
swisscam plan
swisscam toolpath
swisscam simulate
swisscam post --post citizen_meldas_l20 -o part.cnc
swisscam explain op-3
```

Single command facade:

```bash
swisscam run --part part.step --machine ... --layout ... --post ... -o part.cnc
```

---

## 14. Testing strategy

| Layer | Content |
|---|---|
| Unit | model validation, selection filters, sequence rules, path math |
| Geometry | STEP fixtures (small revolve solids), profile segment snapshots |
| Post golden | IR fixtures → NC text diff |
| Integration | `run` on example pin part |
| Safety | unmet tool, over-travel, stick-out, export-without-sim audit |

---

## 15. Implementation sequence (engineering)

1. Docs + gitignore + README ← current
2. Package skeleton, domain models, JSON load/save
3. Seed L20 machine, materials, sample crib/layout, post maps
4. Profile-based feature recognition (synthetic + STEP when OCC present)
5. Tool selection + planner
6. Turning toolpaths + estimates
7. Simulate L0/L1
8. Post engine + citizen_meldas_l20 golden
9. CLI `run` end-to-end
10. Branch merge; next branch for Phase 2 multi-system depth

Each feature lands on its own branch, is reviewed for logic/security, then merges to `Master` per project workflow rules.

---

## 16. Success criteria for architecture

Architecture is correct if:

- A new machine is added **only** by JSON profile + post maps.
- Phase 2 sync does not rewrite domain models — only fills IR fields already reserved.
- Shops can edit M-codes without touching Python.
- Core pipeline runs offline.
- Every automatic choice is explainable.

---

## 17. Document control

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-09-05 |
| Owner | Engineering |
