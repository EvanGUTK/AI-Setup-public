---
name: team-backend-service-layer
description: "Use for backend work involving service layer in an approved engineering team task."
---

# Backend — Services & APIs: Service Layer

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Separate request handling from domain operations and persistence; reuse existing patterns.

## Evidence and output
Focused service logic with invariant tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
