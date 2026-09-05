# SwissCAM Machine & Control Research

**Purpose:** Capture public manufacturer specs and control programming facts that drive SwissCAM machine profiles, kinematics constraints, and post-processors.  
**Primary reference machine:** Citizen Cincom L20 (3rd gen), Mitsubishi Meldas-class control.  
**Status:** Research synthesis for engineering use — not a substitute for a machine-specific programming manual. M-codes and multi-system G-codes vary by generation and builder options; every post must remain data-driven and shop-validated.

---

## 1. Sources (public)

| Source | What it provides |
|---|---|
| Citizen Machinery L20 product pages / catalogs (cmj.citizen.co.jp, citizen.de brochures) | Axis layout, bar capacity, spindle speeds, tooling modules, NC feature list |
| Mitsubishi MELDAS 600L Programming Manual (BNP-B2232) | Lathe G-code baseline: G00/G01/G02/G03, G33 thread, G90/G91, diameter mode, multi-system notes |
| Mitsubishi MELDAS 600M / C6/C64 manuals | General NC program structure; machine maker manuals override for Swiss-specific codes |
| Citizen Cincom E32 IV G/M code lists (public programmer references) | Illustrative Citizen-family M-codes (chuck, back spindle, sync wait, live tools) |
| Industry analyses of L20 multi-system programming (e.g. Eureka G-Code L20 notes) | G600-series machining modes, wait codes, superimposition traps |

Official full Cincom programming manuals are machine-specific and often restricted. SwissCAM must treat published lists as **defaults to override**, not hard truth.

---

## 2. Swiss kinematics (what the software must model)

### 2.1 Sliding headstock + guide bushing

- Bar is gripped in the main spindle collet and supported by a **guide bushing** immediately adjacent to the cut zone.
- **Z1** motion is primarily bar feed / headstock slide relative to tooling at the bushing face.
- Long slender parts are machined with short unsupported stick-out; this is the core Swiss constraint SwissCAM must enforce (PRD FR-26, FR-37).
- Many Cincom L-series machines support **GB** (guide bush) and **GBL** (guide bush-less) conversion:
  - **GB L20 Ø20:** up to ~200 mm machining length per chucking.
  - **GB L20 Ø25 option:** ~188 mm per chucking.
  - **GBL L20:** ~50 mm per chucking (short remnant / short parts).

### 2.2 Axis naming (L20-class)

Typical controlled axes (configuration-dependent):

| Axis | Role |
|---|---|
| Z1 | Main spindle / sliding headstock |
| X1, Y1 | Gang tool post |
| C1 | Main spindle C-axis |
| Z2, X2 | Back spindle / back tool post |
| Y2 | Back tool post Y (higher types) |
| C2 | Back spindle C-axis |
| B | Programmable B on gang rotary tools (Type XII / XIIB5) |

Rapid feeds (catalog): X1/Y1/Z1/X2/Z2 ≈ 32 m/min; Y2 ≈ 8 m/min when present.

### 2.3 Tooling zones

SwissCAM machine profiles must model **positions**, not just tool types:

1. **Gang tool post** — linear-indexed turning tools + cross rotary tools (near bushing).
2. **Opposite / front drill block** — end-working fixed and/or rotary tools.
3. **Back tool post** — fixed and rotary tools for sub-spindle work after transfer.

L20 modular examples (catalog): U31B/U32B/U35B gang rotary modules; U120B/U121B/U125–U128 front holders; U150–U155 back holders. Exact station counts differ by type VIII / IX / X / XII / XIIB5.

### 2.4 Spindle & capacity (L20 3rd gen, public specs)

| Parameter | Typical value |
|---|---|
| Max machining diameter | Ø20 mm (Ø25 / 1" option) |
| Main spindle speed | max 10,000 min⁻¹ |
| Back spindle speed | max 10,000 min⁻¹ |
| Spindle through-hole | ~Ø26.4 mm |
| Main front drill / tap | Ø10 mm / M8 |
| Back drill / tap | Ø8 mm / M8 (varies by type) |
| Gang rotary drill / tap | Ø8 mm / M6; rotary up to 6,000–9,000 min⁻¹ |
| Back rotary | up to ~7,500 min⁻¹ (type-dependent) |
| Turning tool shank | 12 mm sq (13/16 options) |
| Rotary collets | ER11 / ER16 |
| Max tools mounted | ~34–45 depending on type |
| Gang turning tools | up to 6 |
| Workpiece take-out length | ~130 mm |
| Back protrusion limit | ~40 mm |

Motors (order-of-magnitude): main 2.2/3.7/5.5 kW; back 1.5/2.2/3.7 kW; gang rotary ~1.0–2.2 kW.

### 2.5 NC unit (catalog)

- Older L20 gens: Mitsubishi Meldas M70LPC-VU class.
- Newer L20: Meldas M820VW (VIII/X/XII); M850LUC-V on XIIB5-class.
- Standard NC features called out in brochures: spindle sync, nose-R compensation, milling interpolation, multiple repetitive cycles, sync thread cutting, deep drill cycles, C-axis main/back, constant surface speed, user macros, corner chamfer/round.

Optional: tool life, hob, polygon, helical interpolation, expanded offsets/memory.

### 2.6 Citizen-specific process tech (out of MVP path generation, optional later)

- **LFV** (Low Frequency Vibration): servo oscillation synchronized to spindle for chip breaking (X/Z pairs; Y typically excluded; generation-specific limits).
- **ATC + B-axis** on high-end types: magazine tools, chip-to-chip ~4 s — model as optional tool source, not Phase 1 requirement.
- **Cincom Control** idle-time reductions (tool-post overlap, direct spindle indexing) affect cycle-time estimates more than path geometry.

---

## 3. Control programming model

### 3.1 Baseline lathe G-codes (Meldas 600L family)

Useful kernel-level IR targets that posts map to ISO-like output:

| Code | Role |
|---|---|
| G00 | Rapid |
| G01 | Linear feed |
| G02 / G03 | Circular |
| G04 | Dwell |
| G28 | Reference return |
| G32 / G33 | Thread (manual-family dependent) |
| G40/G41/G42 | Nose radius comp off/left/right |
| G50 | Coordinate / max spindle clamp (context-dependent) |
| G96 / G97 | CSS on / RPM mode |
| G98 / G99 | Feed per min / per rev (Fanuc-like numbering; confirm per dialect) |
| G90 / G91 | Abs / inc (and on some lathe lists, canned cycles share numbers — **post tables must disambiguate**) |

Meldas lathe manuals emphasize:

- Diameter vs radius programming for X.
- Multi-system programs: coordinate care across systems; do not drop slave spindle rotation while both spindles hold one bar (sync safety).
- Machine-maker restrictions override generic NC docs.

### 3.2 Citizen multi-system reality (L20-class)

Modern Cincom L20 programs are **not** single-stream Fanuc turning programs. Typical structure:

- Multiple systems: `$1`, `$2`, `$3` (gang/front, back, auxiliary — exact assignment is machine/post specific).
- **Wait / queue codes** must appear in every participating system (`!` labels or start-position queue G-codes). Missing a wait desyncs heads → collision risk in a tiny work envelope.
- **Machining mode G600-series** (reported L20 programming practice; validate per control software):

| Code | Reported role |
|---|---|
| G610 | Gang / front working |
| G620 | Simultaneous ID/OD with back-Z superimposed on main-Z |
| G630 | Front + back parallel |
| G640 | 3-system simultaneous |
| G650 | Pick-off / center support |
| G600 | Cancel modes (often retracts sub to safe point) |

SwissCAM internal IR must represent **mode + system + wait barriers** explicitly. Emitting G-code without that IR is unsafe for Phase 2+.

### 3.3 Superimposition

When back-spindle Z is superimposed on main Z, true tool motion is the **sum** of axes possibly owned by different systems. Simulation that only reads one `$` listing will miss collisions. Phase 2 simulator must compose superimposed axes.

### 3.4 Z zero / G50 traps on Swiss

- Bar advances through the bushing; Swiss Z sign conventions differ from fixed-head lathes.
- `G50` / `G50W` shifts interact with modal state; wrong shift misplaces all subsequent motion.
- Posts must document Z0 policy: bushing face, part face, or machine home — shop-configurable.

### 3.5 Spindle synchronization

Public Citizen-family references:

| Code | Role |
|---|---|
| G114.1 | Spindle sync (detailed master/slave, phase) |
| G814 | Simplified Citizen-oriented sync with R phase; often needs M77 wait when phased |
| M77 | Wait for spindle synchronization complete |
| M123 / M75 | Back-spindle torque limit during cutoff/sync (prevent slip) |
| M124 | Torque limit off |

Pickup/cutoff sequence typically: approach sub → close back chuck → sync spindles → cutoff → open main / residual handling → back work.

### 3.6 Illustrative Citizen-family M-codes (E32 IV public list — **remap per machine**)

| M | Meaning (illustrative) |
|---|---|
| M03/M04/M05 | Main spindle CW/CCW/stop |
| M06/M07 | Chuck close/open |
| M15/M16 | Back chuck close/open |
| M23/M24/M25 | Back spindle CW/CCW/stop |
| M18/M20 | C-axis engage / cancel |
| M52/M53 | Coolant on/off |
| M56 | Part count |
| M72/M73 | Back air blow |
| M80–M85 | Live tool spindle start/stop groups |
| M88/M89 | Interference check off/on |
| M98/M99 | Subprogram call/return |

Older multi-line simultaneous macros (E32-style G710–G750 / G999) show historical Citizen patterns; L20 Meldas gens use the multi-system + G600 approach above. **Never hard-code one family into the kernel.**

### 3.7 Fanuc-style second dialect (MVP post #2 target)

Many Star / some Citizen shops expect Fanuc-like:

- G96/G97, G98/G99, G76 thread cycles, G71/G72 roughing (where supported).
- Still need Swiss-specific M and multi-path handling when the real control is multi-channel.

Phase 1 ships one Citizen/Meldas-oriented post path; Phase 2 adds Fanuc-style mapping tables over the same IR.

---

## 4. Implications for SwissCAM data model

### 4.1 Machine Profile must include

- Axis list + travel limits + rapid rates + which axes exist on this type.
- Spindle specs (main/sub/live) with max RPM and power bands if known.
- Bar capacity, GB vs GBL modes, max stick-out / machining length.
- Tooling topology: gang rows, opposite block stations, back stations, optional B.
- Control family id + post binding (`citizen_meldas_l20_viii`, etc.).
- Clearance solids hooks: bushing, collets, gang block envelope (even if coarse boxes in v1).
- Sync capability flags: spindle sync, superimposition, C-axis, LFV (optional).

### 4.2 Process IR must include (before G-code)

- Ordered operations with spindle side (`main` | `sub`).
- System assignment (`$1`…).
- Barrier/wait ids shared across systems.
- Machining mode segments (G610-class semantics).
- Pickup/cutoff state machine stages.
- Diameter-mode X, units, CSS vs RPM, feed mode.

### 4.3 Safety rules derived from research

1. Never post multi-system code without paired waits.
2. Never cancel machining mode (G600) between pickup blocks without modeling sub retract.
3. Enforce guide-bushing support length on main-side cuts.
4. Gate export on simulation (PRD FR-35), especially once sync exists.
5. Treat all M-code maps as editable config with checksum/version in program header.

---

## 5. What is *not* required for an effective v1 product

From PRD non-goals + research cost:

| Defer | Why |
|---|---|
| Full 5-axis / B-axis surface milling | Needs Phase 3 toolpaths + XIIB5 kinematics |
| LFV parameter generation | Shop-specific; optional post hooks later |
| Real-time DNC / machine monitoring | Out of scope |
| Perfect automatic feature recognition on blends | Manual override is mandatory day one |
| Shipping dozens of validated posts | Framework + 1–2 posts; shops edit maps |
| Cloud licensing dependency in CAM path | Offline-first |

**v1 must still be “real CAM”:** correct Swiss Z/X semantics, layout-aware tool pick, sequential main→cutoff→back plan, collision flags vs bushing/tools, and a credible Citizen/Meldas post for single-path-first programs that can grow to multi-system IR without rewrite.

---

## 6. Reference machine profile seed (Citizen L20 Type VIII-class)

Use as `data/machines/citizen_l20_viii.json` defaults (editable):

```
max_bar_diameter_mm: 20 (25 optional flag)
gb_max_length_mm: 200
gbl_max_length_mm: 50
main_rpm_max: 10000
sub_rpm_max: 10000
rapid_m_per_min: {X1:32, Y1:32, Z1:32, X2:32, Z2:32}
gang_turning_stations: 6
front_drill_stations: 3
back_stations: 4
control: meldas_citizen_multi_system
posts: [citizen_meldas_l20]
```

Higher types add Y2, more back tools, B-axis — same schema, more capability flags.

---

## 7. Open validation checklist (shop / hardware)

Before claiming a post “production”:

- [ ] Confirm system numbers and wait syntax on target control software version
- [ ] Confirm G600-series availability and side effects (sub retract on cancel)
- [ ] Confirm chuck/coolant/live-tool M-codes on that serial
- [ ] Confirm diameter programming and tool offset pair behavior
- [ ] Dry-run pickup/cutoff with single-block and interference check ON
- [ ] Compare cycle time estimate vs actual within shop tolerance

---

## 8. Document control

| Field | Value |
|---|---|
| Created for | SwissCAM architecture |
| Research date | 2026-09-05 |
| Next update trigger | First hardware-validated post or new machine family |
