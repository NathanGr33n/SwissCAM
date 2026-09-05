"""SwissCAM command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from swisscam.domain.models import Priority
from swisscam.pipeline.run import run_from_paths

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SwissCAM CAD-to-G-code CLI")
console = Console()


def _repo_data(*parts: str) -> Path:
    # src/swisscam/cli/main.py -> parents[3] = repo root
    root = Path(__file__).resolve().parents[3]
    return root.joinpath(*parts)


@app.command("run")
def run_cmd(
    part: Path = typer.Option(..., exists=True, dir_okay=False, help="Part JSON (profile model)"),
    machine: Path = typer.Option(
        None, help="Machine profile JSON (default: data/machines/citizen_l20_viii.json)"
    ),
    layout: Path = typer.Option(None, help="Layout JSON"),
    crib: Path = typer.Option(None, help="Tool crib JSON"),
    post: Path = typer.Option(None, help="Post config JSON"),
    materials: Optional[Path] = typer.Option(None, help="Materials library JSON"),
    output: Path = typer.Option(Path("output/program.cnc"), "--output", "-o"),
    priority: Priority = typer.Option(Priority.FASTEST_CYCLE),
    force: bool = typer.Option(False, help="Export even if simulation has errors"),
) -> None:
    """Run full Phase-1 pipeline and write G-code."""
    machine = machine or _repo_data("data", "machines", "citizen_l20_viii.json")
    layout = layout or _repo_data("data", "tools", "sample_layout.json")
    crib = crib or _repo_data("data", "tools", "sample_crib.json")
    post = post or _repo_data("data", "posts", "citizen_meldas_l20.json")
    materials = materials or _repo_data("data", "materials", "default.json")

    try:
        result = run_from_paths(
            part_path=part,
            machine_path=machine,
            layout_path=layout,
            crib_path=crib,
            post_path=post,
            materials_path=materials,
            output_path=output,
            priority=priority,
            override_export=force,
            project_root=None,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="SwissCAM result")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Features", str(len(result.features)))
    table.add_row("Operations", str(len(result.plan.operations)))
    table.add_row("Unmet", ", ".join(result.plan.unmet_features) or "-")
    table.add_row("Toolpaths", str(len(result.toolpaths)))
    table.add_row("Sim OK", str(result.simulation.ok))
    table.add_row("Cycle s", f"{result.ir.cycle_time_s or 0:.2f}")
    table.add_row("Bar mm", f"{result.ir.bar_usage_mm or 0:.3f}")
    table.add_row("Output", str(output))
    console.print(table)

    for d in result.simulation.diagnostics:
        color = {"info": "cyan", "warning": "yellow", "error": "red"}.get(d.level, "white")
        console.print(f"[{color}]{d.level.upper()} {d.code}[/{color}]: {d.message}")

    if not result.simulation.ok and not force:
        raise typer.Exit(code=2)


@app.command("explain")
def explain_cmd(
    part: Path = typer.Option(..., exists=True, dir_okay=False),
    op_id: str = typer.Option(..., help="Operation id e.g. OP001"),
    machine: Path = typer.Option(None),
    layout: Path = typer.Option(None),
    crib: Path = typer.Option(None),
    post: Path = typer.Option(None),
    materials: Optional[Path] = typer.Option(None),
) -> None:
    """Print audit trail for an operation."""
    machine = machine or _repo_data("data", "machines", "citizen_l20_viii.json")
    layout = layout or _repo_data("data", "tools", "sample_layout.json")
    crib = crib or _repo_data("data", "tools", "sample_crib.json")
    post = post or _repo_data("data", "posts", "citizen_meldas_l20.json")
    materials = materials or _repo_data("data", "materials", "default.json")
    result = run_from_paths(
        part_path=part,
        machine_path=machine,
        layout_path=layout,
        crib_path=crib,
        post_path=post,
        materials_path=materials,
        output_path=None,
        override_export=True,
    )
    op = next((o for o in result.plan.operations if o.id == op_id), None)
    if not op:
        console.print(f"[red]Unknown operation {op_id}[/red]")
        raise typer.Exit(1)
    console.print(op.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
