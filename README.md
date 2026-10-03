# ORCHESTRATION_SKILL

Skills for building and auditing agent evaluation data. Dataset- and
benchmark-agnostic. Lessons are drawn from FraudBench
(`references/case_study_fraudbench.md`).

## eval-data-orchestrator

| Phase | What | Where |
|---|---|---|
| 0 Intake | purpose, assets, visibility map | SKILL.md, `scripts/inventory.py` |
| 1 Taxonomy | axes, rule-based tiers, matched controls | `references/taxonomy_and_tiers.md`, `scripts/classify.py` |
| 2 Generate | 5 rungs incl. cold start from policy + tools | `references/synthesis_cold_start.md` |
| 3 Clean | de-leak IDs/fields, integrity, exposure test | `references/cleaning_and_leakage.md`, `scripts/leak_scan.py` |
| 4 Split | stratified, group-aware, hidden slice | `scripts/split.py` |
| 5 Length + grading | length knee, clean vs hard assertions, overrides | `references/length_and_gradeability.md`, `scripts/length_ladder.py` |
| 6 Infra audit | OAuth / RBAC / verify-oracle / step-up / dual control | `references/external_infra_audit.md` |

Install for Claude Code (symlink, so edits here stay live):

    ln -s "$PWD/eval-data-orchestrator" ~/.claude/skills/eval-data-orchestrator

Test prompts: `eval-data-orchestrator/evals/evals.json`.
