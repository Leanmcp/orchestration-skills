#!/usr/bin/env python3
"""Stratified, group-aware split with an optional hidden slice.

Items that share any group value (a customer ID, fixture, template, seed) are
kept in the same split, so nothing learned from one split leaks into another.
Within each stratum (e.g. category x tier), whole groups are assigned to the
split furthest below its target ratio.

Config (see assets/split_config.example.json):
{
  "id_field": "id",
  "list_path": null,
  "strata": ["annotations.fraud_mechanism"],
  "group_by": ["annotations.control_pair_id"],
  "group_regex": {"user_scenario.instructions": "\\\\b(?:u|chk|biz)_[A-Za-z0-9]+\\\\b"},
  "ratios": {"train": 0.6, "dev": 0.1, "test": 0.15, "hidden": 0.15},
  "seed": 13
}
`group_by` paths are read as values; `group_regex` extracts IDs from text at a
path. Hidden-split items are written as hashes only in the public manifest.

  python split.py tasks/ --config split_config.json --out-dir splits/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from _common import get_all, item_id, load_config, load_items


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def item_hash(item) -> str:
    blob = json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    items = load_items(args.src, cfg.get("list_path"))
    ids = [item_id(it, cfg.get("id_field", "id"), i) for i, it in enumerate(items)]
    ratios: dict[str, float] = cfg.get("ratios", {"train": 0.8, "test": 0.2})
    total_r = sum(ratios.values())
    ratios = {k: v / total_r for k, v in ratios.items()}

    # 1. groups: union items sharing any group key
    uf = UnionFind(len(items))
    owner: dict[str, int] = {}
    for i, it in enumerate(items):
        keys: set[str] = set()
        for path in cfg.get("group_by", []):
            keys.update(f"{path}={v}" for v in get_all(it, path) if v is not None)
        for path, rx in cfg.get("group_regex", {}).items():
            for v in get_all(it, path):
                keys.update(f"id={m}" for m in re.findall(rx, str(v)))
        for k in keys:
            if k in owner:
                uf.union(owner[k], i)
            else:
                owner[k] = i
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(items)):
        groups[uf.find(i)].append(i)

    # 2. stratum of a group = most common stratum among its members
    def stratum(i: int) -> str:
        parts = []
        for path in cfg.get("strata", []):
            vals = get_all(items[i], path)
            parts.append(str(vals[0]) if vals else "?")
        return "|".join(parts) or "all"

    by_stratum: dict[str, list[list[int]]] = defaultdict(list)
    for members in groups.values():
        s = Counter(stratum(i) for i in members).most_common(1)[0][0]
        by_stratum[s].append(members)

    # 3. assign groups (largest first) to the split furthest below target
    rng = random.Random(cfg.get("seed", 13))
    assign: dict[int, str] = {}
    for s in sorted(by_stratum):
        grps = by_stratum[s]
        rng.shuffle(grps)
        grps.sort(key=len, reverse=True)
        n_s = sum(len(g) for g in grps)
        filled = Counter()
        for g in grps:
            split = max(ratios, key=lambda k: ratios[k] * n_s - filled[k])
            filled[split] += len(g)
            for i in g:
                assign[i] = split

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": cfg.get("seed", 13), "ratios": ratios, "splits": {}}
    for split in ratios:
        members = sorted((ids[i], i) for i in assign if assign[i] == split)
        if split == "hidden":
            manifest["splits"][split] = {
                "n": len(members),
                "sha256": [item_hash(items[i]) for _, i in members],
            }
            private = [items[i] for _, i in members]
            (out / "hidden_PRIVATE.json").write_text(
                json.dumps(private, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            manifest["splits"][split] = {"n": len(members),
                                         "ids": [iid for iid, _ in members]}
        print(f"{split:<8} {len(members)}")

    n_multi = sum(1 for g in groups.values() if len(g) > 1)
    print(f"groups: {len(groups)} ({n_multi} with >1 item), strata: {len(by_stratum)}")
    (out / "split_manifest.json").write_text(json.dumps(manifest, indent=2),
                                             encoding="utf-8")
    print(f"wrote {out / 'split_manifest.json'}")
    if "hidden" in ratios:
        print(f"wrote {out / 'hidden_PRIVATE.json'} (do not publish)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
