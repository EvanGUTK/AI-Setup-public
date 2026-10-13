---
name: team-data-transactions
description: "Use for data work involving transactions in an approved engineering team task."
---

# Data — Storage & Integrity: Transactions

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Define atomic boundaries, isolation and retry handling; test concurrent conflicts and partial failures.

## Evidence and output
Transaction semantics and tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
