---
name: eval-data-orchestrator
description: Design, generate, clean, split, and stress-test datasets for evaluating or training LLM agents, for any benchmark or domain. It covers building a category/tier taxonomy, generating tasks from seeds or from nothing but a policy and a tool list (cold start), removing answer leakage, stratified splits with hidden sets, finding how long a conversation or context can get before results break, mapping which outputs can be graded deterministically and which need a judge or human, and auditing which failures disappear with real infrastructure (OAuth sessions, RBAC scopes, verify-by-oracle tools, step-up auth). Use this skill whenever the user wants to create, extend, synthesize, augment, categorize, tier, split, clean, de-leak, or audit eval or test data; asks "how do I build a benchmark for X", "we don't have enough data", "split these tasks", "how long can the conversations get", "why is the grader unreliable here", or "would auth fix this failure"; or is working on tau-bench-style, tool-use, multi-turn, red-team, or safety benchmarks. Use it even when they only say "make more tasks", "generate test cases", or "is this dataset any good".
---

# Eval Data Orchestrator

Turns any task domain into an evaluation set you can defend, and into separate
test or training data that does not contaminate it. It is not tied to one
dataset or benchmark. The worked example in
`references/case_study_fraudbench.md` shows every phase on a real benchmark;
read it once if you want a concrete picture before starting.

The core idea: **a dataset is only as good as the weakest of its taxonomy, its
leakage hygiene, its grader, and its separation of model judgment from missing
infrastructure.** Most benchmark bugs are in one of those four places, not in
the number of tasks.

## Phase 0: Intake (always do this first)

Before generating anything, build a short inventory. Ask the user only for what
you cannot find in the repo.

1. **Purpose.** Pick one, because it changes the rules:
   - *Evaluation*: frozen, versioned, hashed, a hidden slice, a small number of
     high-quality items, every label audited.
   - *Testing/regression*: fast, deterministic, cheap, covers each code path
     and tool, may be generated freely.
   - *Training (SFT/RL)*: volume and diversity matter more, must share no
     entities, templates, or near-duplicates with the eval set.
2. **Assets that exist.** Tasks, environment/DB, tool schemas, policy or rule
   documents, graders, past run results. Run `scripts/inventory.py` on any task
   file or folder to get counts, field coverage, and length stats.
3. **Visibility map.** Write down exactly what each actor sees: the agent
   under test (system prompt, tool outputs, conversation), the user simulator
   (hidden instructions), and the grader (labels, assertions). Leakage is
   defined against this map. Anything the agent can see is "runtime-visible".
4. **Scoring unit.** What does one item produce: a binary pass, a partial
   score, a DB end state, a transcript? This decides what can be graded
   deterministically (Phase 5).

Write the inventory to `<project>/EVAL_PLAN.md` using
`assets/eval_plan_template.md`. Every later phase appends to it.

## Phase 1: Freeze the taxonomy before writing data

Everything downstream (generation quotas, splits, metrics, failure analysis)
keys off the taxonomy, so changing it late invalidates work. Define 2-4
orthogonal axes:

- **What** is being tested (mechanism, skill, fraud type, intent).
- **Where** in the workflow it bites (verification, write, dispute, disclosure).
- **How hard** (difficulty tier, computed from structure, not vibes).
- **Intent class**: legitimate / ambiguous / adversarial, plus *matched
  controls*. Without controls an always-refuse or always-comply baseline can
  look strong, and over-refusal cannot be measured.

Make tiers **rule-based and computed** from observable task structure (number
of state-changing calls, number of distinct tools, branching, phases, history
dependence). A rule like "≥3 writes using one tool = batch tier; ≥3 writes or
≥3 distinct tools = branching tier" can be checked by script and re-applied
after edits. `scripts/classify.py` applies a JSON rule file to any dataset.

Details, standard tier ladders, and the controls recipe:
`references/taxonomy_and_tiers.md`.

## Phase 2: Generate data (works with zero data)

Choose the cheapest rung that gives enough coverage. Mix rungs, and record
which rung produced each item (`provenance` field, kept out of runtime-visible
data).

| Rung | Have | Method |
|---|---|---|
| 1 | Real items | Curate, relabel, fill taxonomy gaps |
| 2 | A few seeds | Perturb: swap entities, amounts, order, phrasing, tactic |
| 3 | A schema | Template × slot grid over taxonomy cells |
| 4 | Rules/policy docs + tool list only | **Rule-to-boundary synthesis** (below) |
| 5 | Nothing but a domain name | Build a synthetic world first: entities, DB fixtures, policy, tools; then rung 4 |

**Rule-to-boundary synthesis** is the cold-start workhorse. For every rule in
the policy, generate: one case that clearly passes, one that clearly fails,
cases exactly on and one unit either side of every numeric threshold, one case
where every check passes except one ("single decisive control"), and one where
an earlier turn changes the answer for a later, locally valid request
("history contamination"). Then generate a matched legitimate control for every
adversarial item. This yields 6-8 items per rule with known labels and no
external data.

Difficulty ladder that generalizes: ordinary → single decisive control →
adaptive two-phase (probe, fail, pivot) → long chained multi-goal episodes.

Each item is one source file. Compile to a single manifest with a script, never
by hand, and never edit the compiled copy.

Recipes, fixture rules, LLM-generation prompts, and quality gates:
`references/synthesis_cold_start.md`.

## Phase 3: Clean and de-leak

Agents exploit any shortcut. Check every runtime-visible surface:

- **Semantic identifiers.** IDs like `acct_victim`, `chk_ext_mule`,
  `u_admin_ceo` hand over the answer. Use opaque, type-prefixed IDs
  (`u_4f0c2a91`, `chk_ext_6194`) with a frozen old→new mapping.
- **Editorial fields.** `is_known_mule`, `kyc_status: under_review`, notes like
  "scam destination", `_benchmark_fixture` provenance tags. Delete them; keep
  only fields a real system would hold.
- **Keep the signal.** Do not scrub legitimate facts (frozen state, account
  age, permissions, transaction history) or intentional adversarial payloads
  (prompt-injection text). The model is supposed to reason from these.
- **Referential integrity.** Every referenced ID exists, no fixture silently
  overwrites another, compiled manifest equals the per-item sources.
- **Exposure test.** Build one real agent context offline and assert it does
  not contain task IDs, labels, assertions, or hidden simulator instructions.

`scripts/leak_scan.py` scans chosen fields for forbidden tokens and
semantic-looking IDs. Configure it per dataset. Full checklist:
`references/cleaning_and_leakage.md`.

## Phase 4: Split

- **Stratify** by the taxonomy cell (category × tier × intent) so every split
  covers every cell.
- **Group** by shared entity/fixture/template. Items that share a customer
  record, template, or seed must land in the same split, or the train set
  teaches the eval set.
- **Hidden slice**: hold back 15-30% of eval items, publish only their hashes,
  use it to detect contamination later.
- **Curriculum order** (optional): easy→hard, level-major, so `--limit N`
  gives one item per category at the easiest tier.
- Pin a seed, write the manifest of IDs per split, and record hashes.

`scripts/split.py` does stratified, group-aware splitting with a hidden slice.

## Phase 5: Find the length limits and the gradeability map

Two separate questions. Answer both with data from small pilot runs, not
guesses. Details: `references/length_and_gradeability.md`.

**How long can you test?** Run a length ladder: bucket items (or synthetic
padded variants) by turns, tool calls, and context tokens, then plot pass rate
and *invalid* rate per bucket. Look for the knee, where pass rate falls faster
than the task gets harder, or where timeouts appear. Keep these outcomes
separate, never folded into "fail":
`pass`, `fail`, `max_steps/timeout`, `simulator_invalid` (user sim broke
character or refused its role), `infra_error` (rate limit, 403, context
overflow). `scripts/length_ladder.py` buckets any results file.

**Where is grading clean vs hard?** Classify every assertion:

- *Clean (deterministic)*: a prohibited tool was or was not called, DB end-state
  diff, exact value disclosed, terminal action taken. Grade these by code.
- *Medium*: disposition (refuse/escalate/complete) visible in tool calls plus
  text. Code first, judge as backup.
- *Hard (judgment)*: "recognized the red flag", "gave the correct reason",
  "did not imply the value", paraphrased disclosure, tone. These need an LLM
  judge and a stratified human audit.

**When to change a result** (and how): only through a logged override with a
reason, never by editing the score. Legitimate reasons include an infra error
(re-run), simulator invalid (re-run or exclude, reported), timeout caused by a
step cap set too low (raise the cap, re-run all models), judge contradicted by
deterministic evidence (deterministic wins), and an assertion that penalizes a
semantically valid safe behavior (fix the assertion, bump the dataset version,
re-grade everyone). Report all of these counts next to the score.

## Phase 6: External-infrastructure audit

Many agent "failures" exist only because the benchmark makes the model do a
job real infrastructure would do. Separate them, or you measure missing plumbing
instead of model judgment.

For every category (then every failing item), ask: *would a standard control
make this failure structurally impossible?*

| Control | Removes |
|---|---|
| OAuth / authenticated session principal | Knowledge-based identity guessing, impersonation by recited PII |
| Verify-by-oracle tool (`verify(user, claimed) → match count`, never values) | Agent holding secrets in context, leaking by "correcting" a wrong email |
| RBAC / scoped tools | Reading other customers' data, role escalation, exfiltration |
| Step-up auth / MFA for high-risk writes | Single-factor takeover of transfers, contact changes |
| Dual control / approvals in the backend | Insider removing the approver then wiring funds |
| Rate limits and lockouts in the tool | Brute-force probing of codes or PINs |
| Output filters / data-loss prevention | Verbatim secret disclosure |

Label each item **infra-solvable**, **infra-assisted**, or **judgment-only**
(still hard with perfect infra: genuine customer being scammed, first-party
lies, history contamination, policy nuance). Report both arms when possible:
*as-built* and *with infra*. The judgment-only slice is where the benchmark's
real signal lives. Details and the redesign pattern:
`references/external_infra_audit.md`.

## Deliverables

Unless the user asks for less, produce:

1. `EVAL_PLAN.md` filled in from the template (inventory, taxonomy, rung mix,
   leakage rules, split manifest, length knee, gradeability map, infra labels).
2. Per-item source files plus a compile script that builds the manifest.
3. A config for each script used (`leak_scan`, `classify`, `split`).
4. A short findings summary for the user: what is solid, what is weak, which
   numbers should not be reported yet and why.

## Running scripts

Scripts in `scripts/` use only the Python standard library and take a
`--help`. Some users run every script themselves. If the project instructions
say so, write configs and hand over exact commands (prefixed with `time` for
long runs) instead of executing them. Otherwise run them directly.

```
python scripts/inventory.py <tasks.json|tasks.jsonl|tasks_dir> [--category-field PATH | --category-regex REGEX]
python scripts/classify.py <data> --rules rules.json --out tiers.json
python scripts/leak_scan.py <data> --config leak_config.json
python scripts/split.py <data> --config split_config.json --out-dir splits/
python scripts/length_ladder.py <results.json|jsonl> --config ladder_config.json
```

Field paths use dots (`annotations.fraud_mechanism`, `user_scenario.instructions`).
Example configs are in `assets/`.
