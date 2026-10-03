# EVAL_PLAN: <dataset name> v<version>

## 0. Intake
- Purpose: evaluation | testing/regression | training
- Existing assets: tasks (n=), environment/DB, tools (n=), policy docs (n=), grader, past runs
- Visibility map:
  | Actor | Sees |
  |---|---|
  | Agent under test | |
  | User simulator | |
  | Grader | |
- Scoring unit:

## 1. Taxonomy (frozen YYYY-MM-DD)
| Axis | Values | Field |
|---|---|---|
| Category | | |
| Workflow stage | | |
| Tier (rule file: ) | | |
| Intent | legit / ambiguous / adversarial / control | |

Cell quotas:

## 2. Generation
| Rung | Items | Notes |
|---|---|---|
| 1 curate | | |
| 2 perturb | | |
| 3 template | | |
| 4 rule-to-boundary | | |
| 5 world build | | |

Matched controls: n pairs
Compile command:

## 3. Cleaning
- ID standard:
- Removed fields:
- Kept signals:
- Gates passed: sync / integrity / leak scan / exposure test / label re-check
- Hashes: tasks= db= policy=

## 4. Splits (seed= )
| Split | n | Strata covered | Notes |
|---|---|---|---|
Group key:
Hidden slice: n, hashes in

## 5. Length and gradeability
- Length distribution: median / p90 / max (turns, tokens)
- Knee: <bucket>, cause:
- Step cap chosen:
- Assertion classes: clean n / medium n / hard n
- Items with no clean check:
- Override log location:

## 6. Infrastructure audit
| Category | Label | Control that would solve it |
|---|---|---|
Judgment-only share:

## 7. Not reportable yet (and why)
-
