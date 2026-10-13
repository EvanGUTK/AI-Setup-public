---
name: team-backend-error-contract
description: "Use for backend work involving error contract in an approved engineering team task."
---

# Backend — Services & APIs: Error Contract

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Return actionable stable errors without secrets; preserve original context in appropriate internal diagnostics.

## Evidence and output
Error mapping and tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
