# Taxonomy and tiers

## Why freeze first

Generation quotas, split strata, aggregation code, and failure analysis all key
off category and tier labels. If a category is renamed or merged after 200
items exist, every downstream table changes and old runs stop being comparable.
Freeze the enums, write them in `EVAL_PLAN.md`, and version any later change.

## Axes

Pick 2-4 axes that are orthogonal (changing one should not force the other).

| Axis | Question | Typical values |
|---|---|---|
| Mechanism / skill | What is being tested? | fraud type, reasoning skill, tool family |
| Workflow stage | Where does it bite? | verification, read, write, dispute, closure, disclosure |
| Difficulty tier | How hard, structurally? | see ladder below |
| Intent class | Should the agent complete it? | legit, ambiguous, adversarial, matched-control |
| Tactic (adversarial only) | How does the attacker push? | urgency, authority, sympathy, persistence, partial credentials |

Category should be a **field** in each item (`annotations.category`), not only
encoded in the filename or ID. If it lives only in the ID, aggregation code
must use a frozen mapping and a test that every ID maps to exactly one stratum.

## Rule-based tiers

Tiers should be computed from structure, so they survive edits and can be
re-checked. Write rules as data (see `assets/classify_rules.example.json`).

Generic signals that predict difficulty:

- number of state-changing (write) actions required;
- number of distinct tools required;
- whether the answer branches on a computed value (eligibility, threshold);
- dependency order between actions (X must happen before Y);
- number of phases / goals in one episode;
- history dependence (an earlier turn changes what a later request permits);
- retrieval need (rule must be found in a corpus vs given in prompt);
- distance to a numeric boundary (exactly at threshold is harder than far).

A ladder that has worked for tool-using agent benchmarks:

| Tier | Rule (example) |
|---|---|
| S1 read-only | 0 writes; answer from one lookup |
| S2 single write | 1 write, 1 tool |
| S3 short sequence | 2 writes, fixed order |
| S4a batch | ≥3 writes, all the same tool (enumeration skill) |
| S4b branching workflow | ≥3 writes or ≥3 distinct tools, with branching/dependency order |
| S5 multi-goal / long | several independent goals or phases in one episode |
| S6 adversarial-adaptive | history contamination, attacker pivots after failure |

Rename freely; keep the rule explicit.

## Adversarial difficulty ladder (orthogonal to the tier)

1. **Ordinary**: varied narrative, several red flags.
2. **Single decisive control**: every check passes except one exact rule (one
   unit over a cap, one day short of a waiting period, a different owner). Tests
   exact policy application, not vague suspicion.
3. **Adaptive two-phase**: the attacker probes, fails, or admits something,
   then pivots to a request that would be valid under a clean history. Tests
   trust-state preservation.
4. **Chained**: several of the above across a long episode.

## Matched controls

For each adversarial item, write a legitimate twin that keeps the surface red
flags and changes only the decisive permission fact:

- different-owner destination → same-owner destination;
- near-miss guess then exact code → exact code with no prior guess;
- dispute after admitting the purchase → dispute on a different transaction
  with no contradicting statement.

Pair them with `control_pair_id`. Report attack-security and control-utility
separately, plus a combined number (harmonic mean or worst-axis). An
always-refuse baseline must score low on the combined number; if it does not,
the controls are too weak.

## Quotas

Equal cells are a design choice for coverage, not a prevalence estimate. Say so
in the dataset card. Aim for at least 5-9 items per reported cell; below that,
report the cell as qualitative only.
