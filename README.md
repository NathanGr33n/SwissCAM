# SwissCAM

CAD-to-G-code automation for **Swiss-type (sliding headstock) screw machines**.

SwissCAM is built around guide-bushing turning, gang/turret layouts, main/sub-spindle work, and shop-specific tool cribs — not as a general mill-turn afterthought.

## Status

**Phase 1 MVP core is implemented** (CLI pipeline: profile part → features → tools → plan → toolpaths → sim → G-code).

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, domain model, pipeline, tech choices |
| [RESEARCH.md](RESEARCH.md) | Citizen Cincom / Mitsubishi Meldas research notes |
| `PRD.md` | Product requirements (local design doc; may be gitignored) |

## What works now

- Machine profile, tool crib, and layout JSON (seed: Citizen L20 VIII)
- Rotational feature recognition from XZ half-profiles (face, OD, groove, cutoff, …)
- Layout-aware tool selection with audit reasons
- Swiss sequential process planning + multi-system wait skeleton (`$1`/`$2`, `!W1`/`!W2`)
- OD rough/finish, face, groove, cutoff toolpaths
- L0/L1 simulation gates (travel, bar capacity, stick-out, unmet tools)
- Editable Citizen/Meldas-style post (`data/posts/citizen_meldas_l20.json`)
- CLI: `swisscam run`, `swisscam explain`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
swisscam run --part examples/demo_pin.json -o output/demo_pin.cnc
```

Optional overrides:

```bash
swisscam run \
  --part examples/demo_pin.json \
  --machine data/machines/citizen_l20_viii.json \
  --layout data/tools/sample_layout.json \
  --crib data/tools/sample_crib.json \
  --post data/posts/citizen_meldas_l20.json \
  --materials data/materials/default.json \
  -o output/demo_pin.cnc
```

## Package layout

```
src/swisscam/     domain, features, tools, planning, toolpath, simulate, post, pipeline, cli
data/             machines, tools, posts, materials
examples/         demo_pin.json profile part
tests/unit/       pipeline tests
```

## Safety

- Treat generated G-code as **unvalidated** until dry-run on the target control.
- Multi-system Citizen programs require paired waits and shop-validated M-code maps.
- Do not commit secrets, licenses, or proprietary post files (`private/`, `.env` are ignored).
- Simulation failures block export unless `--force` is used (logged override path).

## Roadmap (next)

- STEP import via OpenCascade (optional `cad` extra)
- Full multi-system pickup/cutoff IR (G650) and Fanuc-style post
- Live-tool / C-axis features
- Desktop UI

## License

TBD by repository owner.
