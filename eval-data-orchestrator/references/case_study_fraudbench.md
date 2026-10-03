# Case study: FraudBench

FraudBench (Pai and Xian, arXiv 2608.18136, "Stress-Testing Policy-Grounded
Banking Agents Against Adaptive Fraud") is a τ²-bench domain in which a
simulated caller tries to defraud a banking agent that acts through tools on a
mutable account database and a 698-document policy corpus. This file maps each
phase of the skill onto what FraudBench did, including its known gaps, so the
lessons transfer to other domains.

Source paths in the tau2-bench repo: `data/tau2/domains/fraudbench/`,
`FRAUDBENCH/` (plan, dataset card, categories, paper draft),
`workspace/*fraudbench*.py` (build, compile, split, verify, aggregate scripts).

## Phase 0: intake

- Purpose: evaluation (paper benchmark) with a hidden slice.
- Assets reused: the τ-Knowledge banking environment (DB schema, 17 agent
  tools, policy corpus). FraudBench added only fixtures and tasks.
- Visibility map: the agent sees policy, tool schemas, tool outputs, and the
  conversation. The user simulator sees `user_scenario` (attacker script,
  `known_info`, `does_not_know`). The grader sees `nl_assertions` and
  `annotations`. Task IDs like `fb_task_mule_01` are not leaks because the
  standard agent never sees them; oracle/ground-truth agent modes are excluded
  from reported scores because they do.

## Phase 1: taxonomy

- Mechanism axis, 10 categories × 9 items: APP scam, account takeover, card
  fraud, data exfiltration, first-party fraud, prompt injection, money mule,
  phishing-derived PII, social engineering, synthetic identity.
- Workflow stage, social-engineering tactics, observable evidence, permitted
  and prohibited actions, correct disposition, latest acceptable intervention
  turn, cost model, standards references (FraudClassifier, FATF, Basel, OWASP
  LLM): all in `annotations`.
- Difficulty by suffix: `_01`-`_07` ordinary, `_08` single decisive control,
  `_09` adaptive two-phase; plus `chain` tasks as the capstone tier.
- Gap: category and difficulty lived only in the ID convention, so aggregation
  needed a frozen mapping. Put them in fields.
- Gap: attack-only. Zero matched legitimate controls, so an always-refuse
  agent could look safe. The plan calls for control pairs; they were the top
  open item.

## Phase 2: generation

- Hand-authored synthetic scenarios (rung 4-5), not real transcripts.
- Fixtures added in batches (V1-V15) by `workspace/build_fraudbench_db.py` on
  top of the banking DB: 125 users, 126 accounts, cards, transactions, disputes.
- Per-task JSON files are the source; `compile_fraudbench_tasks.py` builds
  `tasks.json`; `gen_fraudbench_all_curriculum.py` writes a level-major
  curriculum so `--limit 10` gives one easiest task per category.
- `_08` items are rule-to-boundary: a destination with a different owner, an
  ATM limit $10 over the cap, a record one month outside a retention window, a
  dispute count exactly at the cap, a dual-auth amount exactly on the
  inclusive threshold, a role change before its 48-hour delay.
- `_09` items are history contamination: a near-miss recovery-code guess then
  the exact code; repeated activation failures then a correct attempt after a
  branch-only lock; an admission that funds are third-party payroll then a
  valid-looking same-owner transfer.
- Attacker scripts are conditional ("if the agent asks for verification
  anyway, say ..."), with explicit `does_not_know` and "never break character".
- 150 task files exist; the public benchmark is 107 (90 core + 17 chain);
  43 chain items are withheld as a hidden set.

## Phase 3: cleaning

From `data/tau2/domains/fraudbench/FIX_PLAN.md`:

- 133 non-opaque runtime IDs replaced (`fb_u_victim1` → `u_4f0c2a91`,
  `chk_ext_hospital_mule` → `chk_ext_5127`, `biz_31ashby` → opaque).
- Editorial fields removed: `_fraudbench_fixture`, `is_known_mule`,
  `mule_flag_reason`, `kyc_status: under_review`, `beneficiary_note: APP scam
  destination`, non-native `fraud_alert`.
- Kept: native frozen-card state (`fraud_alert_active`, `alert_source`,
  `frozen_date`), dual-auth thresholds, roles, account age, injection payloads.
- Descriptions rewritten where the removed flag was the stated evidence.
- Sync bugs found in the same pass: compiled `tasks.json` had 110 of 150
  tasks; `db.json` lacked the last four fixture batches; two disputes
  referenced missing transactions; the verifier keyed fixture detection on a
  now-forbidden ID prefix.
- Clock pinned server-side in `log_verification` so end-state comparison does
  not depend on model-chosen timestamps.

Lesson: leakage cleanup and artifact sync belong in one pass with gates,
because renaming IDs exposes every stale reference.

## Phase 4: split

- Public 107 / hidden 43 by task family. Hashes recorded in the dataset card
  (task manifest, DB, policy corpus).
- Open check: the split is by task ID. If any customer record or fixture is
  shared between a public and a hidden item, training on the public set leaks
  into the hidden one. A group-aware split (by fixture ID) rules this out.

## Phase 5: length and gradeability

- Pilot (Nemotron-3 Ultra, 10 `_01` tasks, 40 max steps): 6/10, with 2
  `max_steps` terminations (first-party, mule) where no assertion was graded.
  Lesson: 40 steps was below the knee for long adversarial episodes; timeouts
  were reported separately, not as failures.
- Multi-model, 107 tasks, 1 trial, user sim `gpt-5.4-nano`: attack-security
  from 49.5% (gpt-oss-120b) to 64.5% (Gemini 3.6 Flash). Money mule hardest for
  every model; first-party fraud and chain tasks also weak.
- Infra errors: a Kimi run hit an OpenRouter daily-credit 403; every later call
  scored 0. These had to be identified and re-run, not reported.
- Grading: v0 used only NL assertions judged over the whole transcript (so
  grading is history-aware). Deterministic annotations (prohibited actions,
  disposition, intervention turn) existed but were not enforced. The paper
  calls for a hybrid evaluator: tool-call and DB-delta checks first, judge only
  for residual conversational criteria, human audit of a stratified sample.
- Hard-to-grade cluster: **PII-confirmation leaks**. The caller offers a wrong
  email "to verify" and the agent corrects it, revealing the real value.
  `workspace/fraudbench_find_leaks.py` mines these from failed assertions plus
  transcript regex.

## Phase 6: infrastructure audit

The verification flow is knowledge-based: the agent calls
`get_user_information_by_name` (which returns DOB, email, phone, address),
compares the caller's claims in its own context, then calls
`log_verification`. Consequences:

- The agent holds every secret it is checking against, so it can leak by
  confirming or correcting. A verify-by-oracle tool
  (`verify_identity(user_id, claimed) → matched k of 4`, no values) makes the
  PII-confirmation leak impossible.
- Any caller who recites stolen static PII passes. An OAuth-authenticated
  session plus step-up for high-risk writes turns most ATO and phished-PII
  items into infra-solvable ones.
- Lookups by name or ID are not scoped to the caller, so exfiltration items
  test the model's restraint. RBAC scoping to `session.user_id` removes them.
- Dual-authorization bypass (remove the second approver, then wire) is
  enforceable in the backend.

What stays judgment-only even with perfect infrastructure: APP scams (genuine,
authenticated customer being manipulated), first-party fraud, money mule
patterns, history-contamination pivots, and prompt-injected record text. These
categories carry the benchmark's model-capability signal, and they are also
where the measured models scored worst.
