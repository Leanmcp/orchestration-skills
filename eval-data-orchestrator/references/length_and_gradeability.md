# Length limits and gradeability

## Part A: how long can you test?

"Length" has several independent dimensions. Measure each one:

| Dimension | Measured as | Common breakpoints |
|---|---|---|
| Turns | user+agent messages | step caps hit, simulator drift, attacker gives up |
| Tool calls | count per episode | step caps, repeated calls, loops |
| Context tokens | prompt tokens at the last call | model window, quality drop before the window |
| Policy/corpus size | tokens of rules in context or retrieved | retrieval misses, rule confusion |
| Tool-output size | tokens per observation | large dumps push policy out of attention |
| Phases/goals | distinct sub-goals | agent finishes goal 1 and stops |

### Ladder procedure

1. Pick 1-2 dimensions. Bucket existing items by them, or create padded
   variants of a few items (extra benign turns, larger histories, more records
   in tool outputs) while keeping the decisive fact and label fixed.
2. Run a small pilot (a few items per bucket, 1-3 trials) on one cheap and one
   strong model.
3. For each bucket record: pass, fail, timeout/max_steps, simulator_invalid,
   infra_error. Feed results to `scripts/length_ladder.py`.
4. The **knee** is the first bucket where pass rate drops sharply relative to
   the previous bucket, or invalid+timeout exceeds ~10%. Above the knee, either
   raise caps (if timeouts) or report that range separately.

### Rules

- Timeouts are not failures of judgment. If a step cap ends episodes before the
  decision point, the cap is too low. Raise it for all models and re-run.
- Report the length distribution of the final set (median, p90, max) so readers
  know which regime was tested.
- Separate "the model got worse with length" from "the grader got worse with
  length". Long transcripts degrade LLM judges too; spot-check judge accuracy
  on the longest bucket.
- Prefer retrieval over stuffing the whole policy in context when the corpus is
  large, but then measure retrieval recall separately with gold documents.

## Part B: where grading is clean vs hard

Classify each assertion in each item.

| Class | Examples | Grade with |
|---|---|---|
| Clean | prohibited tool not called; DB end-state diff; exact secret string absent; specific escalation tool called | code |
| Medium | final disposition; correct ordering of calls; required verification logged before a write | code first, judge for tie-breaks |
| Hard | recognized the red flag; stated the correct reason; did not imply the value; tone; paraphrased disclosure ("your email ends in starmail") | LLM judge + human audit |

Aim for every item to have at least one clean check. A judge alone is weak
evidence for high-stakes action safety.

### Where context stays clean

- Short, single-goal episodes with deterministic end-state checks.
- Tools that return only what the agent needs (no full record dumps).
- Fixed clocks, normalized formats, opaque IDs.

### Where outputs get hard and results may need changing

- **Paraphrased leaks**: the agent never states the secret verbatim but
  confirms or corrects a wrong guess. Regex misses it; judges catch it
  inconsistently. Add a targeted assertion and audit.
- **Refuse-then-act / act-then-apologize**: text says no, tool calls say yes.
  Tool calls win.
- **Correct action, wrong reason**: escalated, but cited the wrong rule. Decide
  up front whether reason matters; if it does, it is a hard assertion.
- **Simulator breaks**: user sim refuses to play the attacker, reveals the
  test, or stops early. Mark `simulator_invalid`, exclude from the
  denominator, report the count.
- **Infra errors**: rate limits, 403 daily caps, context overflow produce
  empty turns scored 0. Mark `infra_error` and re-run; never report as model
  failure.
- **Over-strict assertions**: penalize a safe alternative (e.g. escalating
  instead of refusing when both are safe). Fix the assertion, bump version,
  re-grade all models.

### Override protocol

Every change to a recorded result goes in an overrides file:
`{run_id, item_id, old, new, reason_code, evidence, who, date}`. Reason codes:
`infra_rerun`, `sim_invalid`, `cap_raised`, `deterministic_overrules_judge`,
`assertion_fixed_vX`. Report override counts per model next to the score.

## Part C: human audit

Audit a stratified sample (every category × tier cell), plus every judge
disagreement and every override. Two auditors on a subset to estimate
agreement. Record the judge's accuracy against auditors per assertion class.
