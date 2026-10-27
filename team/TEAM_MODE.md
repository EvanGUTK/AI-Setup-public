---
tags: [claude-code, codex, team-mode, multi-agent]
scope: team-sessions
updated: 2026-10-27
---

# Team mode rules

Read this file when `AGENT_TEAM_PROVIDER` is set (the session was started by `claude-team` or `codex-team`), or when the user asks for a team. Plain `claude`/`codex` sessions are single sessions and do not use it. These rules add to the universal rules; they do not replace them.

## Chief and Validator
- Chief is the main orchestrator in a visible tmux pane. Its first action is `agent-team spawn validator`; it waits for Validator's acknowledgement with `agent-team inbox` (about 5 minutes at most) before planning. Keep Validator addressable. If it cannot be spawned or does not answer, report degraded mode, stop gated delivery and never bypass its gate.
- Chief is the user's only point of contact. Validator and workers take direction from Chief and send questions, blockers and verdicts with `agent-team send chief`; they never ask the user directly.
- The brainstorm-first rule in the universal rules applies to Chief: no plan and no spawned builders until the scope is confirmed with the user.
- No autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly requests one.

## Panes and providers
- One pane per agent: Validator and every worker run as their own tmux pane in Chief's window, opened with `agent-team spawn <role> --task <task> -C <dir>`. The window re-tiles automatically; past AGENT_TEAM_MAX_PANES (default 6) further agents open in a new window of the same session. Never use in-process or native subagent tools for team roles; read-only in-process search helpers for lookups are allowed.
- Provider-exclusive: `claude-team` uses only Claude agents and `codex-team` only Codex agents. `agent-team spawn` refuses any other provider.
- Models and effort come from `~/.agent-team/models.json` (the launcher fills them into the startup prompt). Defaults at last review: Claude Chief/Validator claude-opus-5-5 high, workers claude-sonnet-5-5 high (xhigh for difficult work); Codex Chief/Validator gpt-6.1-sol high, workers gpt-6-luna high, escalating only on evidence. Never silently substitute an unavailable model.

## Messaging
- `agent-team send <role|%pane> <message>` writes a durable file under $AGENT_TEAM_STATE/mailbox/<role>/ and posts a one-line pane notice; the recipient runs `agent-team inbox`. The notice is typed only when the target pane's input line is empty (otherwise it shows in the tmux status bar and is retried for about 60s), so keystrokes never merge with what the user is typing. `agent-team panes` shows live and dead agents.
- Put handoffs, findings and approvals in the mailbox files, not only in pane text. Panes are terminals, not a protocol; a team of the other provider shares no bus, so agree ownership and exchange durable handoff files.

## Roles and ownership
- Roles: chief, validator, architect, product, backend, frontend, engine, data, qa, security, platform, integrator. Read `~/.agent-team/roles/<role>.md` and `~/.agent-team/ROSTER.md`; load only task-relevant skills (ten per role).
- After plan approval Chief selects the roles, assigns exclusive ownership and contracts, and writes a hierarchy and repo-tree plan. Create a new agent or skill only for a demonstrated missing capability; avoid redundant generic roles.

## Worktrees and gates
- Every writer works in its own topic branch and sibling worktree: `agent-team worktree <role> <task>`, then `agent-team spawn -C <that dir>`. Every agent verifies `pwd` equals its assigned directory before any edit; Chief checks each pane's cwd. Agent-definition isolation settings are not relied on.
- Validator independently reviews every writer's code and the integrated result. Push reviewable atomic batches only after Validator and Chief approve the exact HEAD; a new commit invalidates earlier approval. Use `agent-team gate record ...` and `agent-team gate push ...`; raw git still follows the same policy. Chief approving technical readiness is not user merge approval.
- Handoff contents: task/issue, branch/worktree, changed paths, exact SHA, test commands and results, CodeRabbit findings, Validator verdict, Chief decision, PR and remaining risks.
