---
name: team-backend-idempotent-writes
description: "Use for backend work involving idempotent writes in an approved engineering team task."
---

# Backend — Services & APIs: Idempotent Writes

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Define idempotency keys and transaction boundaries; exercise duplicate and concurrent requests.

## Evidence and output
Repeat-safe write behavior.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
