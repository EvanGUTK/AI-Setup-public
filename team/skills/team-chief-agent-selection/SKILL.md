---
name: team-chief-agent-selection
description: "Use for chief work involving agent selection in an approved engineering team task."
---

# Chief — Orchestrator: Agent Selection

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Choose the smallest sufficient specialist set and concurrency. Explain a missing capability before creating a new role; give it narrow outputs and skills. Open each agent with `agent-team spawn <role> --task <task> -C <worktree>`, using only agents of the team provider; the window re-tiles automatically and overflows to a new window past AGENT_TEAM_MAX_PANES.

## Evidence and output
Role hierarchy with capability justification and the spawn command for each agent.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
