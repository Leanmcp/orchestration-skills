#!/usr/bin/env python3
"""Assign each item a tier (or any label) from an ordered rule file.

Rules are data, so tiers are reproducible and can be re-applied after edits.
The first rule whose conditions all hold wins; `default` applies otherwise.

Rule file shape (see assets/classify_rules.example.json):
{
  "id_field": "id",
  "list_path": null,
  "metrics": {
    "n_writes": {"metric": "count", "path": "evaluation_criteria.actions[].name",
                 "filter_not_in": ["get_user_information_by_id"]},
    "n_tools":  {"metric": "distinct", "path": "evaluation_criteria.actions[].name"}
  },
  "rules": [
    {"label": "S4a", "all": [["n_writes", ">=", 3], ["n_tools", "==", 1]]},
    {"label": "S4b", "any": [["n_writes", ">=", 3], ["n_tools", ">=", 3]]}
  ],
  "default": "S1"
}
Each condition is [metric_name, op, value]; ops: == != >= > <= < in not_in regex.
A rule may use "all", "any", or both.

  python classify.py tasks/ --rules rules.json --out tiers.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from _common import check, compute_metric, item_id, load_config, load_items


def matches(rule: dict, values: dict) -> bool:
    all_c = rule.get("all", [])
    any_c = rule.get("any", [])
    ok_all = all(check(values.get(m), op, v) for m, op, v in all_c)
    ok_any = any(check(values.get(m), op, v) for m, op, v in any_c) if any_c else True
    return ok_all and ok_any


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", help="write {id: {label, metrics}} JSON here")
    args = ap.parse_args()

    cfg = load_config(args.rules)
    items = load_items(args.src, cfg.get("list_path"))
    metrics = cfg.get("metrics", {})
    rules = cfg.get("rules", [])
    default = cfg.get("default", "unclassified")

    out: dict[str, dict] = {}
    for i, it in enumerate(items):
        iid = item_id(it, cfg.get("id_field", "id"), i)
        values = {name: compute_metric(it, spec) for name, spec in metrics.items()}
        label = next((r["label"] for r in rules if matches(r, values)), default)
        out[iid] = {"label": label, "metrics": values}

    counts = Counter(v["label"] for v in out.values())
    print("label counts:")
    for lab, k in counts.most_common():
        print(f"  {lab:<30} {k}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
        print(f"\nwrote {len(out)} labels to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
