---
name: team-security-input-boundaries
description: "Use for security work involving input boundaries in an approved engineering team task."
---

# Security — Application Reviewer: Input Boundaries

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Trace untrusted input into queries, commands, rendering and serialization; verify context-appropriate protections.

## Evidence and output
Boundary analysis and harmless local repros.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
