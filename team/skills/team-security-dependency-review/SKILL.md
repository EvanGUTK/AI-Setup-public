---
name: team-security-dependency-review
description: "Use for security work involving dependency review in an approved engineering team task."
---

# Security — Application Reviewer: Dependency Review

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Check exact dependency versions and official advisories relevant to reachable application paths.

## Evidence and output
Relevant dependency findings.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
