---
name: team-engine-property-tests
description: "Use for engine work involving property tests in an approved engineering team task."
---

# Engine — Core Logic & Performance: Property Tests

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Derive properties from domain invariants and generate meaningful inputs with shrinking and deterministic reproduction.

## Evidence and output
Invariant coverage with reproducible failures.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
