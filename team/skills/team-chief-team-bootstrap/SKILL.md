---
name: team-chief-team-bootstrap
description: "Use for chief work involving team bootstrap in an approved engineering team task."
---

# Chief — Orchestrator: Team Bootstrap

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Run `agent-team spawn validator` (own tmux pane, senior model, high effort) before any other work; Validator sends its acknowledgement on startup; check `agent-team inbox` and confirm the pane with `agent-team panes` for at most about 5 minutes, then report degraded mode to the user instead of waiting or looping indefinitely. Spawn builders only after plan approval. Never use in-process or native subagent tools for team roles; read-only in-process search helpers for lookups are fine.

## Evidence and output
Live Validator pane id and its acknowledgement from the inbox.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
