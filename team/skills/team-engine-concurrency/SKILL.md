---
name: team-engine-concurrency
description: "Use for engine work involving concurrency in an approved engineering team task."
---

# Engine — Core Logic & Performance: Concurrency

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Specify shared state and locking, cancellation and ordering; reproduce races using controlled schedules.

## Evidence and output
Concurrency implementation and race checks.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
