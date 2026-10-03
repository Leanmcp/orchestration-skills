#!/usr/bin/env python3
"""Bucket run results by length and find where results break (the knee).

Outcomes are kept separate: pass, fail, timeout, sim_invalid, infra_error.
Pass rate is computed over valid episodes (pass + fail) only; the invalid rate
is reported next to it.

Config (see assets/ladder_config.example.json; defaults fit tau2 results.json):
{
  "list_path": "simulations",
  "id_field": "task_id",
  "length": {"metric": "count", "path": "messages[]"},
  "reward_path": "reward_info.reward",
  "pass_threshold": 0.999,
  "termination_path": "termination_reason",
  "termination_map": {"max_steps": "timeout", "too_many_errors": "infra_error"},
  "infra_error_regex": "(rate limit|429|403|quota|context length|daily limit)",
  "error_text_path": "messages[].content",
  "buckets": [0, 10, 20, 40, 80, 160],
  "knee_drop": 0.15,
  "knee_invalid": 0.10
}
`length.metric` may be count / distinct / chars / tokens (see _common.py).

  python length_ladder.py data/simulations/<run>/results.json --config ladder.json
  python length_ladder.py runs_dir/ --config ladder.json      # many results files
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

from _common import compute_metric, get_all, get_one, load_config, load_items

DEFAULTS = {
    "list_path": "simulations",
    "id_field": "task_id",
    "length": {"metric": "count", "path": "messages[]"},
    "reward_path": "reward_info.reward",
    "pass_threshold": 0.999,
    "termination_path": "termination_reason",
    "termination_map": {"max_steps": "timeout", "too_many_errors": "infra_error"},
    "infra_error_regex": "",
    "error_text_path": "",
    "buckets": [0, 10, 20, 40, 80, 160],
    "knee_drop": 0.15,
    "knee_invalid": 0.10,
}


def outcome(ep, cfg) -> str:
    term = str(get_one(ep, cfg["termination_path"], "") or "")
    for key, label in cfg["termination_map"].items():
        if key and key in term:
            return label
    if cfg["infra_error_regex"] and cfg["error_text_path"]:
        rx = re.compile(cfg["infra_error_regex"], re.I)
        if any(rx.search(str(t)) for t in get_all(ep, cfg["error_text_path"])):
            return "infra_error"
    sim_flag = cfg.get("sim_invalid_path")
    if sim_flag and get_one(ep, sim_flag):
        return "sim_invalid"
    reward = get_one(ep, cfg["reward_path"])
    if reward is None:
        return "infra_error"
    return "pass" if float(reward) >= cfg["pass_threshold"] else "fail"


def bucket_label(v: float, edges: list[float]) -> str:
    for lo, hi in zip(edges, edges[1:]):
        if lo <= v < hi:
            return f"[{lo},{hi})"
    return f"[{edges[-1]},inf)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="results file or directory of results files")
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = {**DEFAULTS, **load_config(args.config)}
    episodes = load_items(args.src, cfg["list_path"])
    edges = sorted(cfg["buckets"])
    order = [f"[{lo},{hi})" for lo, hi in zip(edges, edges[1:])] + [f"[{edges[-1]},inf)"]

    table: dict[str, Counter] = {b: Counter() for b in order}
    for ep in episodes:
        length = compute_metric(ep, cfg["length"]) or 0
        table[bucket_label(float(length), edges)][outcome(ep, cfg)] += 1

    cols = ["pass", "fail", "timeout", "sim_invalid", "infra_error"]
    print(f"episodes: {len(episodes)}   length = {cfg['length']}")
    print(f"{'bucket':<14}{'n':>5}" + "".join(f"{c:>13}" for c in cols)
          + f"{'pass_rate':>11}{'invalid':>9}")
    prev_rate = None
    knee = None
    for b in order:
        c = table[b]
        n = sum(c.values())
        if n == 0:
            continue
        valid = c["pass"] + c["fail"]
        rate = c["pass"] / valid if valid else float("nan")
        invalid = (n - valid) / n
        mark = ""
        if knee is None and (
            invalid > cfg["knee_invalid"]
            or (prev_rate is not None and valid and prev_rate - rate > cfg["knee_drop"])
        ):
            knee = b
            mark = "  <-- knee"
        print(f"{b:<14}{n:>5}" + "".join(f"{c[k]:>13}" for k in cols)
              + f"{rate:>11.2f}{invalid:>9.2f}{mark}")
        if valid:
            prev_rate = rate
    print()
    if knee:
        print(f"knee at {knee}: pass rate drops > {cfg['knee_drop']:.0%} or invalid "
              f"> {cfg['knee_invalid']:.0%}. If timeouts dominate, raise the step "
              f"cap and re-run before reading this as a model limit.")
    else:
        print("no knee found in the measured range; extend the ladder upward.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
