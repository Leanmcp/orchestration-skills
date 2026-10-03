# Cleaning and leakage

## Leak surfaces (check against the visibility map)

1. Values the simulated user speaks (IDs, names) that encode the answer.
2. Fields returned by tools (IDs, editorial flags, notes, provenance tags).
3. Initial message history.
4. Any wrapper that serializes the whole task (ID, description, labels) into
   the agent prompt. Common in "oracle" or "ground-truth" agent modes. Exclude
   those modes from reported scores.
5. Filenames or task IDs, only if some wrapper exposes them.

## What to remove

- Identifiers carrying meaning: category, role, relationship, name, outcome,
  geography, purpose (`acct_victim`, `chk_ext_hospital_mule`, `u_32_admin`,
  `btxn_refund_scam01`).
- Editorial fields that state the answer: `is_known_mule`, `risk_label`,
  `beneficiary_note: scam destination`, non-native status fields the real
  system would not have.
- Provenance tags: `_benchmark_fixture`, "added by build script" notes.

## What to keep

- Legitimate operational state: frozen status, alert source, account age,
  permissions, thresholds, dispute counts, history.
- Deliberately adversarial content: prompt-injection payloads in notes or
  descriptions, misleading caller claims. That is the test.
- Evaluator-only labels in evaluator-only fields.
- Stable task IDs, so results stay comparable across versions.

## Neutral ID standard

- Keep a type prefix if useful (`u_`, `acct_`, `txn_`).
- Opaque suffix: random hex or a unique number with no scenario meaning.
- Freeze the old→new mapping once results are published.
- Never reuse an ID for a different record.

## Validation gates

1. **Sync**: every source file parses; IDs unique; filename = ID; compiled
   manifest = sorted compilation of sources.
2. **Referential integrity**: every referenced record exists; internal
   back-references agree; no fixture overwrites another or a base record.
3. **Forbidden-token scan** over runtime-visible fields and IDs
   (`scripts/leak_scan.py`), with allowlists for intentional payloads.
4. **Exposure test**: construct one agent context offline; assert it lacks
   task ID, description, labels, assertions, hidden simulator instructions.
5. **Label re-check**: after cleaning, confirm the label still follows from the
   cleaned data. Removing an editorial flag can remove the only evidence an
   item's label relied on; rewrite the item's evidence, not just the ID.
6. **Assertion hash diff**: hash assertions before and after; only reviewed
   changes allowed.

## Other cleaning

- Deduplicate near-identical items (normalized text, Jaccard or embedding
  similarity above a threshold).
- Normalize formats the grader compares (dates, currency, phone formats).
- Pin clocks: if tools stamp times, stamp server-side from a fixed clock, so
  graders comparing end state do not fail on model-chosen timestamps.
- Record dataset, DB, and policy hashes with every run.
