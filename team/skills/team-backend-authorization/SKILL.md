---
name: team-backend-authorization
description: "Use for backend work involving authorization in an approved engineering team task."
---

# Backend — Services & APIs: Authorization

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Enforce authentication and object-level authorization at service boundaries; test cross-user denial and expiry.

## Evidence and output
Authorization implementation and denial tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
