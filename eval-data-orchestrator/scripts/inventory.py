#!/usr/bin/env python3
"""Inventory a dataset: item count, field coverage, categories, length stats.

Examples:
  python inventory.py data/tasks/
  python inventory.py tasks.json --category-field annotations.category
  python inventory.py tasks/ --category-regex '^fb_task_([a-z]+)_\\d+$'
  python inventory.py results.json --list-path simulations --length-path messages
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter

from _common import (
    approx_tokens,
    category_of,
    get_all,
    item_id,
    load_items,
    text_len,
)


def pct(values: list[int], q: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def field_paths(node, prefix="", depth=0, max_depth=3):
    """Dotted key paths (up to max_depth) present in a dict item."""
    if not isinstance(node, dict) or depth >= max_depth:
        return
    for k, v in node.items():
        p = f"{prefix}.{k}" if prefix else k
        yield p
        yield from field_paths(v, p, depth + 1, max_depth)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="file (.json/.jsonl) or directory")
    ap.add_argument("--list-path", help="path to the item list inside a JSON object")
    ap.add_argument("--id-field", default="id")
    ap.add_argument("--category-field", help="dotted path holding the category")
    ap.add_argument("--category-regex", help="regex on the ID; group 1 = category")
    ap.add_argument("--length-path", default="",
                    help="subtree to measure for length (default: whole item)")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args()

    items = load_items(args.src, args.list_path)
    n = len(items)
    ids = [item_id(it, args.id_field, i) for i, it in enumerate(items)]
    dup = [k for k, c in Counter(ids).items() if c > 1]

    coverage: Counter = Counter()
    for it in items:
        coverage.update(set(field_paths(it)))

    cats = Counter(category_of(it, iid, args.category_field, args.category_regex)
                   for it, iid in zip(items, ids))

    chars = [sum(text_len(v) for v in get_all(it, args.length_path)) for it in items]
    toks = [approx_tokens(c) for c in chars]
    length = {
        "approx_tokens_min": min(toks) if toks else 0,
        "approx_tokens_median": int(statistics.median(toks)) if toks else 0,
        "approx_tokens_p90": pct(toks, 0.9),
        "approx_tokens_max": max(toks) if toks else 0,
    }

    report = {
        "n_items": n,
        "duplicate_ids": dup,
        "categories": dict(cats.most_common()),
        "length": length,
        "field_coverage": {k: f"{v}/{n}" for k, v in sorted(coverage.items())},
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"items: {n}")
    print(f"duplicate ids: {len(dup)}" + (f"  e.g. {dup[:5]}" if dup else ""))
    print("\ncategories:")
    for c, k in cats.most_common():
        print(f"  {c:<40} {k}")
    print("\nlength (approx tokens):")
    for k, v in length.items():
        print(f"  {k:<24} {v}")
    print("\nfield coverage (fields present in <100% of items are worth a look):")
    for k, v in sorted(coverage.items()):
        flag = "" if v == n else "   <-- partial"
        print(f"  {k:<60} {v}/{n}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
