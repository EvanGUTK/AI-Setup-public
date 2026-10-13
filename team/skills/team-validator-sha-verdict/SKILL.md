---
name: team-validator-sha-verdict
description: "Use for validator work involving sha verdict in an approved engineering team task."
---

# Validator — Independent Gatekeeper: Sha Verdict

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Record validator verdict for exact HEAD with commands, review outcomes and remaining risks. Refuse stale evidence after any commit.

## Evidence and output
Machine-readable verdict for current SHA.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
