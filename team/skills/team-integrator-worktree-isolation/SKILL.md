---
name: team-integrator-worktree-isolation
description: "Use for integrator work involving worktree isolation in an approved engineering team task."
---

# Integrator — Git & Release Coordinator: Worktree Isolation

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Create sibling worktrees using agent-team worktree <role> <task>; pass the directory to `agent-team spawn -C`. Confirm the `pwd` of the pane, branch and root equal the assignment before edits; do not rely on agent-definition isolation.

## Evidence and output
Unique role worktree and topic branch, with the verified cwd of the pane.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
