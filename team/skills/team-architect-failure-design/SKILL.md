---
name: team-architect-failure-design
description: "Use for architect work involving failure design in an approved engineering team task."
---

# Architect — System Designer: Failure Design

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Specify timeouts, retry limits, idempotency and degraded behavior across component boundaries.

## Evidence and output
Failure-mode contract.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
