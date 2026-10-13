---
name: team-validator-independent-diff
description: "Use for validator work involving independent diff in an approved engineering team task."
---

# Validator — Independent Gatekeeper: Independent Diff

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Inspect changed paths and call sites against base; locate behavior regressions and scope creep. Do not rely on author summaries.

## Evidence and output
Prioritized findings with path and reproduction.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
