# Generating data, including from nothing

## Contents
1. Choosing a rung
2. Cold start: build the world first
3. Rule-to-boundary synthesis
4. Perturbation of seeds
5. Using an LLM to draft items
6. Item schema
7. Quality gates before an item enters the set
8. Eval vs test vs training data

## 1. Choosing a rung

| Rung | Input you have | Output quality | Cost |
|---|---|---|---|
| 1 Curate | real items | highest realism, label noise | low |
| 2 Perturb | 5-20 seeds | good, limited diversity | low |
| 3 Template grid | schema + slot values | uniform, can feel templated | very low |
| 4 Rule-to-boundary | policy + tools | precise labels, synthetic language | medium |
| 5 World build | domain name only | fully controlled, least realistic | high once, cheap after |

Mix rungs. Keep a `provenance` field (rung, seed id, generator model, date) in
an evaluator-only part of the item, never in runtime-visible data.

## 2. Cold start: build the world first

When there is no data, there is usually also no environment. Build in this
order, because each step constrains the next:

1. **Entities and state**: users, accounts, orders, records, with realistic
   fields a real system holds. Opaque IDs from the start.
2. **Tools**: read tools and write tools, each with a schema. Mark which
   mutate state. Decide what each read tool returns (this is where secrets can
   leak, see `external_infra_audit.md`).
3. **Policy**: numbered rules with explicit thresholds, preconditions, and
   escalation branches. If the domain has no written policy, write one; a
   benchmark cannot grade compliance with rules that do not exist.
4. **Fixtures per item**: each item adds the minimal records it needs on top of
   a shared base. A build script merges base + fixtures deterministically and
   fails on ID collisions.

## 3. Rule-to-boundary synthesis

For each policy rule R with precondition set P and threshold(s) T:

| Variant | Construction | Label |
|---|---|---|
| clear pass | all of P true, far from T | complete |
| clear fail | key element of P false | refuse/escalate |
| on boundary | value exactly T | per the rule's inclusivity |
| boundary ±1 | T-1 unit, T+1 unit | opposite labels |
| single decisive control | all checks pass but one | refuse that one |
| history contamination | earlier turn changes permission for a later valid-looking request | refuse/escalate |
| matched control | adversarial surface, decisive fact flipped | complete |

Do this for each rule, then cross with tactics (urgency, authority, sympathy,
persistence) for adversarial variants. 30 rules × 7 variants is ~200 items with
known labels and no external data.

## 4. Perturbation of seeds

Change one dimension at a time so the label stays known: entity names, amounts
(staying on the same side of every threshold), turn order, phrasing, tactic,
the channel the claim arrives through. Re-run the label check after each
perturbation, because an amount change can cross a threshold silently.

## 5. Using an LLM to draft items

LLMs draft fast but introduce three systematic bugs: labels that do not match
the fixtures, semantic IDs, and editorial hints in prose the agent can see.
Use them as drafters behind gates:

- Give the generator the frozen schema, the taxonomy cell, the policy rule
  text, and the fixture records. Ask for one item per call.
- Require it to cite which policy rule determines the label.
- Have a second pass (different prompt or model) try to solve the item from
  runtime-visible data only. If the solver's answer disagrees with the label,
  either the label is wrong or the item is ambiguous; send to human review.
- Attacker/user-simulator scripts: write conditional branches ("if the agent
  asks for X, say Y"), list what the simulated user knows and does not know,
  and forbid breaking character. Some safety-tuned simulator models refuse to
  play an attacker; pilot the simulator and track its refusal rate.

## 6. Item schema (generic)

```jsonc
{
  "id": "stable, never reused",
  "runtime": {            // what the agent can see or reach
    "fixtures": ["ids added to the environment"],
    "initial_messages": []
  },
  "user_sim": {           // hidden from the agent
    "instructions": "...", "known_info": "...", "does_not_know": "..."
  },
  "grading": {            // hidden from the agent
    "deterministic": {"prohibited_calls": [], "required_calls": [], "end_state": {}},
    "nl_assertions": [],
    "disposition": "complete | verify_then_complete | refuse | escalate"
  },
  "annotations": {        // hidden, used for strata and analysis
    "category": "", "stage": "", "tier": "", "intent": "",
    "control_pair_id": null, "required_documents": [], "provenance": {}
  }
}
```

Adapt names to the host framework. The split between `runtime` and everything
else is the important part.

## 7. Quality gates

An item enters the set only if it:

1. parses and validates against the schema;
2. references only IDs that exist after the build;
3. passes the leak scan;
4. has a label justified by a cited rule;
5. is solvable from runtime-visible data (a strong model or a human can reach
   the label without hidden info);
6. has at least one deterministic check, or is explicitly marked judge-only;
7. is not a near-duplicate of another item (normalized text similarity).

## 8. Eval vs test vs training data

- **Eval**: fewer items, every label human-checked, frozen and hashed, hidden
  slice withheld, corrections bump the version with a changelog.
- **Test/regression**: one item per code path or tool, deterministic grading
  only, runs in CI in seconds, no LLM in the loop where possible (scripted
  agent or replayed trajectories).
- **Training**: generated at volume from rungs 2-5, with a group-aware split so
  no entity, template, or seed is shared with eval. Keep a contamination check:
  n-gram overlap between train items and eval items.
