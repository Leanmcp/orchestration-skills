#!/usr/bin/env python3
"""Scan runtime-visible data for answer leakage.

Two checks over the strings you mark as runtime-visible:
  1. forbidden tokens (e.g. "mule", "victim", "scam") anywhere in an identifier;
  2. semantic-looking identifiers: an ID matching `id_regex` whose suffix after
     the type prefix contains a run of >= `min_word_len` letters that is not
     plain hex (e.g. chk_ext_hospital_mule, u_32_admin).

Forbidden tokens are also reported in free text, but listed separately because
free text often holds intentional adversarial content; use `allow_substrings`
or `free_text_paths_ignore` for those.

Config (see assets/leak_config.example.json):
{
  "id_field": "id",
  "list_path": null,
  "scan_paths": ["user_scenario.instructions", "user_scenario.known_info"],
  "extra_files": [{"path": "db.json", "scan_paths": [""]}],
  "id_regex": "\\\\b(?:u|chk|sav|biz|dbc|btxn|acct)_[A-Za-z0-9_]+\\\\b",
  "forbidden_tokens": ["fraud", "scam", "mule", "victim", "attacker"],
  "allow_substrings": [],
  "free_text_paths_ignore": [],
  "min_word_len": 4
}
Use "" in scan_paths to scan the whole item / file.

  python leak_scan.py tasks/ --config leak_config.json
Exit code 1 if any identifier leak is found (useful in CI).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

from _common import get_all, item_id, iter_strings, load_config, load_items

HEX = re.compile(r"^[0-9a-fA-F]+$")


def semantic_parts(identifier: str, min_len: int) -> list[str]:
    """Letter runs in the ID (after the first underscore) that look like words."""
    _, _, suffix = identifier.partition("_")
    runs = re.findall(r"[A-Za-z]+", suffix)
    return [r for r in runs if len(r) >= min_len and not HEX.match(r)]


def scan_strings(strings, cfg, source, id_hits, text_hits):
    id_re = re.compile(cfg["id_regex"]) if cfg.get("id_regex") else None
    tokens = [t.lower() for t in cfg.get("forbidden_tokens", [])]
    allow = [a.lower() for a in cfg.get("allow_substrings", [])]
    ignore = cfg.get("free_text_paths_ignore", [])
    min_len = int(cfg.get("min_word_len", 4))
    ext_ok = set(cfg.get("allowed_id_words", ["ext"]))

    for path, s in strings:
        low = s.lower()
        if id_re:
            for m in id_re.finditer(s):
                ident = m.group(0)
                il = ident.lower()
                bad_tok = [t for t in tokens if t in il]
                words = [w for w in semantic_parts(ident, min_len)
                         if w.lower() not in ext_ok]
                if bad_tok or words:
                    id_hits[ident].add(f"{source}:{path}"
                                       f" tokens={bad_tok} words={words}")
        if any(path.startswith(p) for p in ignore if p):
            continue
        for t in tokens:
            if t in low and not any(a in low for a in allow):
                text_hits[t].add(f"{source}:{path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--config", required=True)
    ap.add_argument("--max-show", type=int, default=5)
    args = ap.parse_args()

    cfg = load_config(args.config)
    id_hits: dict[str, set] = defaultdict(set)
    text_hits: dict[str, set] = defaultdict(set)

    items = load_items(args.src, cfg.get("list_path"))
    for i, it in enumerate(items):
        iid = item_id(it, cfg.get("id_field", "id"), i)
        for sp in cfg.get("scan_paths", [""]):
            for node in get_all(it, sp):
                prefix = sp or ""
                scan_strings(iter_strings(node, prefix), cfg, iid, id_hits, text_hits)

    for extra in cfg.get("extra_files", []):
        with open(extra["path"], encoding="utf-8") as f:
            data = json.load(f)
        for sp in extra.get("scan_paths", [""]):
            for node in get_all(data, sp):
                # scan keys too: DB tables are often keyed by record ID
                keys = []
                if isinstance(node, dict):
                    stack = [("", node)]
                    while stack:
                        p, d = stack.pop()
                        for k, v in d.items():
                            keys.append((f"{p}.{k}" if p else k, k))
                            if isinstance(v, dict):
                                stack.append((f"{p}.{k}" if p else k, v))
                scan_strings(list(iter_strings(node, sp)) + keys, cfg,
                             extra["path"], id_hits, text_hits)

    print(f"identifier leaks: {len(id_hits)}")
    for ident in sorted(id_hits):
        locs = sorted(id_hits[ident])
        print(f"  {ident}  ({len(locs)} locations)")
        for loc in locs[: args.max_show]:
            print(f"      {loc}")
    print(f"\nforbidden tokens in free text (review; may be intentional): "
          f"{len(text_hits)}")
    for tok in sorted(text_hits):
        locs = sorted(text_hits[tok])
        print(f"  '{tok}' in {len(locs)} places, e.g. {locs[: args.max_show]}")
    return 1 if id_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
