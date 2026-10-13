---
name: team-engine-numeric-correctness
description: "Use for engine work involving numeric correctness in an approved engineering team task."
---

# Engine — Core Logic & Performance: Numeric Correctness

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Define precision, units, rounding and overflow behavior; check extreme values and avoid silent conversions.

## Evidence and output
Numerical contract and boundary tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
