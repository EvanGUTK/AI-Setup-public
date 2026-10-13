---
name: team-validator-atomic-test-review
description: "Use for validator work involving atomic test review in an approved engineering team task."
---

# Validator — Independent Gatekeeper: Atomic Test Review

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Check that each commit has focused behavior coverage, regressions fail on the old implementation, and assertions test outcomes.

## Evidence and output
Per-commit test evidence and gaps.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
