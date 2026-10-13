---
name: team-chief-push-approval
description: "Use for chief work involving push approval in an approved engineering team task."
---

# Chief — Orchestrator: Push Approval

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Compare exact HEAD, tests, CodeRabbit findings, Validator verdict and diff scope. Record Chief approval for that SHA; invalidate it on any new commit.

## Evidence and output
Chief push approval tied to exact SHA.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
