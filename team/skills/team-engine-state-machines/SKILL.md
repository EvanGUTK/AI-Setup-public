---
name: team-engine-state-machines
description: "Use for engine work involving state machines in an approved engineering team task."
---

# Engine — Core Logic & Performance: State Machines

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Enumerate valid states, transitions, guards and terminal conditions; reject invalid transitions explicitly.

## Evidence and output
State machine with transition tests.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
