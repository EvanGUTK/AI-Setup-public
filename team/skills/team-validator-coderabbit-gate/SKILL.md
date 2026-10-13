---
name: team-validator-coderabbit-gate
description: "Use for validator work involving coderabbit gate in an approved engineering team task."
---

# Validator — Independent Gatekeeper: Coderabbit Gate

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Run coderabbit review --agent --base <base> locally. Inspect structured findings; a successful command is not proof of a clean review. Handle authentication failure as pending.

## Evidence and output
Recorded review command, findings and dispositions.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
