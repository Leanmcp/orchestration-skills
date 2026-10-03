"""Shared helpers: load items from any common layout and read dotted paths.

Supported inputs:
  - a JSON file holding a list of items;
  - a JSON file holding an object whose list lives at `list_path`
    (e.g. tau2 results.json -> "simulations");
  - a JSONL file, one item per line;
  - a directory of *.json / *.jsonl files (each file one item, a list, or JSONL).

Path syntax: dots separate keys, `[]` expands a list, an integer selects an
index. Examples: "annotations.category", "evaluation_criteria.actions[].name",
"messages[].content", "messages.0.role".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

_MISSING = object()


def _load_file(path: Path, list_path: str | None) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if list_path:
        data = get_one(data, list_path)
    if isinstance(data, list):
        return data
    return [data]


def load_items(src: str, list_path: str | None = None) -> list[Any]:
    """Load items from a file or directory (see module docstring)."""
    p = Path(src)
    if p.is_dir():
        items: list[Any] = []
        for f in sorted(p.iterdir()):
            if f.suffix in (".json", ".jsonl") and f.is_file():
                items.extend(_load_file(f, list_path))
        return items
    return _load_file(p, list_path)


def _walk(node: Any, parts: list[str]) -> Iterable[Any]:
    if not parts:
        yield node
        return
    head, rest = parts[0], parts[1:]
    expand = head.endswith("[]")
    key = head[:-2] if expand else head
    if key:
        if isinstance(node, dict):
            node = node.get(key, _MISSING)
        elif isinstance(node, list) and key.isdigit():
            idx = int(key)
            node = node[idx] if idx < len(node) else _MISSING
        else:
            node = _MISSING
    if node is _MISSING or node is None:
        return
    if expand:
        if isinstance(node, list):
            for child in node:
                yield from _walk(child, rest)
        return
    yield from _walk(node, rest)


def get_all(obj: Any, path: str) -> list[Any]:
    """All values at `path` (expanding `[]`). Missing paths give []."""
    if not path:
        return [obj]
    return list(_walk(obj, path.split(".")))


def get_one(obj: Any, path: str, default: Any = None) -> Any:
    """First value at `path`, or `default`."""
    vals = get_all(obj, path)
    return vals[0] if vals else default


def iter_strings(node: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    """Yield (path, string) for every string leaf under `node`."""
    if isinstance(node, str):
        yield prefix, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from iter_strings(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_strings(v, f"{prefix}.{i}" if prefix else str(i))


def text_len(node: Any) -> int:
    """Total characters of all string leaves under `node`."""
    return sum(len(s) for _, s in iter_strings(node))


def approx_tokens(chars: int) -> int:
    """Rough token estimate (~4 chars/token for English)."""
    return chars // 4


def item_id(item: Any, id_field: str, fallback_index: int) -> str:
    val = get_one(item, id_field) if id_field else None
    return str(val) if val is not None else f"item_{fallback_index:05d}"


def category_of(item: Any, iid: str, field: str | None, regex: str | None) -> str:
    """Category from a field, else from a regex group on the ID, else '?'."""
    if field:
        val = get_one(item, field)
        if val is not None:
            return str(val)
    if regex:
        m = re.search(regex, iid)
        if m:
            return m.group(1) if m.groups() else m.group(0)
    return "?"


def compute_metric(item: Any, spec: dict) -> Any:
    """Evaluate a metric spec against one item.

    spec = {"metric": "count" | "distinct" | "value" | "chars" | "tokens" | "exists",
            "path": "...", "filter_in": [...optional allowed values...],
            "filter_not_in": [...optional excluded values...]}
    """
    vals = get_all(item, spec.get("path", ""))
    if "filter_in" in spec:
        allowed = set(spec["filter_in"])
        vals = [v for v in vals if v in allowed]
    if "filter_not_in" in spec:
        banned = set(spec["filter_not_in"])
        vals = [v for v in vals if v not in banned]
    metric = spec.get("metric", "value")
    if metric == "count":
        return len(vals)
    if metric == "distinct":
        return len({json.dumps(v, sort_keys=True) for v in vals})
    if metric == "chars":
        return sum(text_len(v) for v in vals)
    if metric == "tokens":
        return approx_tokens(sum(text_len(v) for v in vals))
    if metric == "exists":
        return bool(vals)
    return vals[0] if vals else None


_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: a is not None and a >= b,
    ">": lambda a, b: a is not None and a > b,
    "<=": lambda a, b: a is not None and a <= b,
    "<": lambda a, b: a is not None and a < b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "regex": lambda a, b: a is not None and re.search(b, str(a)) is not None,
}


def check(value: Any, op: str, target: Any) -> bool:
    if op not in _OPS:
        raise ValueError(f"unknown op {op!r}; use one of {sorted(_OPS)}")
    return _OPS[op](value, target)


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))
