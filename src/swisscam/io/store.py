"""JSON document I/O with basic path safety."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._\-]+$")


def assert_safe_filename(name: str) -> str:
    base = Path(name).name
    if not base or not _SAFE_NAME.match(base):
        raise ValueError(f"Unsafe file name: {name!r}")
    return base


def resolve_under(root: Path, path: Path | str) -> Path:
    """Resolve path and ensure it stays under root (after resolve)."""
    root_r = root.resolve()
    target = (root_r / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        target.relative_to(root_r)
    except ValueError as exc:
        # Allow absolute paths only if explicitly under root already checked;
        # for absolute outside root, still reject when a root confinement is required.
        raise ValueError(f"Path escapes project root: {target}") from exc
    return target


def load_model(path: Path | str, model_type: type[T]) -> T:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return model_type.model_validate(data)


def save_model(path: Path | str, model: BaseModel, *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = model.model_dump_json(indent=indent)
    p.write_text(text + "\n", encoding="utf-8")


def write_text_safe(path: Path | str, content: str, *, root: Path | None = None) -> Path:
    p = Path(path)
    if root is not None:
        if p.is_absolute():
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError(f"Refusing write outside project root: {p}") from exc
        else:
            p = resolve_under(root, p)
    else:
        p = p.resolve()
    assert_safe_filename(p.name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
