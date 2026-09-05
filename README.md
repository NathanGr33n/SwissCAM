# SwissCAM

CAD-to-G-code automation for **Swiss-type (sliding headstock) screw machines**.

SwissCAM is built around guide-bushing turning, gang/turret layouts, main/sub-spindle work, and shop-specific tool cribs — not as a general mill-turn afterthought.

## Status

**Phase 1 MVP in progress** (architecture and research complete).

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, domain model, pipeline, tech choices |
| [RESEARCH.md](RESEARCH.md) | Citizen Cincom / Mitsubishi Meldas research notes |
| `PRD.md` | Product requirements (local design doc; may be gitignored) |

## Goals (MVP)

- Machine profiles + tool crib + turret/gang **layouts**
- STEP import and **rotational** feature recognition (with manual override)
- Automatic tool selection from the **active layout**
- Sequential Swiss process planning (main → cutoff → back hooks)
- Turning toolpaths, cycle-time / bar estimates, safety simulation gates
- Editable post-processor: Citizen/Meldas-oriented dialect first

## Non-goals (v1)

- Full 5-axis milling strategies
- Real-time DNC / machine monitoring
- Cloud-required toolpath generation
- Multi-SKU bar nesting

## Planned stack

- Python 3.11+ package (`src/swisscam`)
- Pydantic domain models + JSON libraries
- OpenCascade (cadquery/OCP) for STEP (optional extra)
- Jinja2 + JSON/YAML post maps
- CLI-first workflow; GUI later

## Quick start (once package lands)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
swisscam --help
swisscam run --part examples/pin.step \
  --machine data/machines/citizen_l20_viii.json \
  --layout data/tools/sample_layout.json \
  --post citizen_meldas_l20 \
  -o output/pin.cnc
```

## Safety

- Treat generated G-code as **unvalidated** until dry-run on the target control.
- Multi-system Citizen programs require paired waits and shop-validated M-code maps.
- Do not commit secrets, licenses, or proprietary post files (`private/`, `.env` are ignored).

## License

TBD by repository owner.
