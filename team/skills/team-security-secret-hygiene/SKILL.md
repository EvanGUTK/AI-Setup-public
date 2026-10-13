---
name: team-security-secret-hygiene
description: "Use for security work involving secret hygiene in an approved engineering team task."
---

# Security — Application Reviewer: Secret Hygiene

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Review staged diffs and logging paths for sensitive material; use secret names, never values, in findings.

## Evidence and output
Secret-free diff and configuration guidance.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
