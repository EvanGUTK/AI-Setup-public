---
name: team-security-security-fix-check
description: "Use for security work involving security fix check in an approved engineering team task."
---

# Security — Application Reviewer: Security Fix Check

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Reproduce an issue locally, verify the fix blocks the original case and confirm legitimate behavior still works.

## Evidence and output
Fix verification and regression evidence.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
