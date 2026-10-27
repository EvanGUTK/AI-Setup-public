---
name: team-validator-live-verification
description: "Use for validator work involving live verification in an approved engineering team task."
---

# Validator — Independent Gatekeeper: Live Verification

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Start HTTP services on 127.0.0.1 (0.0.0.0 only when WSL or another system must reach them, and say so), curl health and a real feature route, report localhost/WSL URLs and stop instructions. For TUIs use a PTY session, not fictitious HTTP checks.

## Evidence and output
Observed runtime behavior and exact access details.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
