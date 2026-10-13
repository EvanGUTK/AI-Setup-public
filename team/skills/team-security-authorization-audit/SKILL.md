---
name: team-security-authorization-audit
description: "Use for security work involving authorization audit in an approved engineering team task."
---

# Security — Application Reviewer: Authorization Audit

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Trace role and object-level checks; test cross-tenant, cross-user and privilege escalation denials locally.

## Evidence and output
Authorization findings and denial evidence.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
