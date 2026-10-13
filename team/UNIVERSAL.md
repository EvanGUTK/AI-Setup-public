---
tags: [claude-code, codex, global-rules, multi-agent, coderabbit, github-flow]
scope: global
updated: 2026-10-13
---

# Universal engineering rules

## Context and scope
- Read existing relevant files and inspect boundaries before writing. Check PROJECT.md, ARCHITECTURE.md and TASKS.md in the repository root before coding. If absent, record the gap; Chief creates useful documents after plan approval rather than inventing facts.
- Keep changes targeted to the approved task. Preserve unrelated work and match repository conventions. Follow direct user instructions and higher-priority runtime policy; these rules do not override managed restrictions.
- Read ~/.agent-team/memory/preferences.md and the relevant role memory. Treat explicit user corrections as authoritative within their scope; inferred preferences remain tentative.

## Plan, then execute autonomously
- For a new app or substantial feature, Chief first proposes an in-depth plan covering journeys, requirements/non-goals, architecture alternatives, data/contracts, annotated repo tree, hierarchy, dependencies, milestones, acceptance tests, risks, budget and rollback. Wait for explicit user approval or modification before repository provisioning or implementation.
- Approval of a plan authorizes ordinary implementation, local tests, installs needed for that plan, topic commits and issue/PR operations within the approved increment. Avoid repeated permission questions in YOLO mode. Product decisions and merge approval still require the user's stated authority.
- Deliver one user-testable increment at a time. Chief splits the approved plan into increments; after each, it verifies (tests, Validator, live check), hands the user what changed, exact how-to-test steps and the running demo URL with stop instructions, then waits for the user's feedback or go-ahead before the next increment. Autonomy applies within an approved increment only.
- Give meaningful concise progress updates, incorporate steering and report blockers honestly. Ask only for missing decisions that materially change the outcome; continue independent work.

## Chief, Validator and the team
- When invoked in team mode, Chief is the main orchestrator in a visible tmux pane. Its first action is `agent-team spawn validator`; it obtains Validator's acknowledgement with `agent-team inbox` before planning. Keep Validator addressable; if it cannot be spawned or does not answer, report degraded mode and do not bypass its gate.
- One pane per agent: Validator and every worker run as their own tmux pane in Chief's window, opened with `agent-team spawn <role> --task <task> -C <dir>`. The window is re-tiled automatically so every pane fits, panes are titled by role/task, and past AGENT_TEAM_MAX_PANES (default 6) further agents open in a new window of the same session. Never use in-process or native subagent tools for team roles; read-only in-process search helpers for lookups are allowed.
- Provider-exclusive teams: `claude-team` uses only Claude agents and `codex-team` only Codex agents. The launcher records the provider on the tmux session and `agent-team spawn` refuses any other provider; startup prompts name only that provider's models.
- Claude Chief/Validator: claude-opus-5-5 at high effort. Workers: claude-sonnet-5-5 at high; use xhigh for difficult work. Codex Chief/Validator: gpt-6.1-sol at high. Workers: gpt-6-luna at high, escalating effort/model when justified by evidence. Do not silently substitute unavailable models.
- Chief is the user's only point of contact. Validator and workers take direction from Chief and send questions, blockers and verdicts with `agent-team send chief`; they never ask the user directly.
- No autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly requests one.
- The 12 personal role definitions are chief, validator, architect, product, backend, frontend, engine, data, qa, security, platform and integrator. Read the relevant ~/.agent-team/roles/<role>.md and load only task-relevant skills. Each role has ten skills; consult ~/.agent-team/ROSTER.md.
- After plan approval, Chief selects the required roles, assigns exclusive ownership and contracts, and creates a hierarchy and repo tree plan. Create a new agent/skill only for a demonstrated missing capability; avoid redundant generic roles.
- Messaging is a file mailbox plus a pane notice: `agent-team send <role|%pane> <message>` writes a durable file under $AGENT_TEAM_STATE/mailbox/<role>/ and posts a one-line notice for the recipient. The notice is typed only when the target pane's input line is empty; otherwise it appears as a tmux status-bar message and injection is retried briefly (about 60s), so keystrokes never merge with what the user is typing (Chief's pane is always checked this way); the recipient runs `agent-team inbox`. `agent-team panes` shows live/dead agents. Put handoffs, findings and approvals in these files, not only in pane text. Panes are terminals, not a protocol; a separate team of the other provider shares no bus, so agree ownership and exchange durable handoff files.

## GitHub, worktrees and atomic work
- Use CCPM for PRD → epic → dependency-aware tasks → linked GitHub issues. The user's topic-branch, worktree and conventional-commit rules override conflicting CCPM defaults.
- Create or reuse a GitHub issue before feature/bug implementation. If no remote/auth/network exists, Chief reports the missing prerequisite; do not fabricate issue IDs. For a brand-new app, propose private repository provisioning in the approved plan. Never auto-publish the user's home directory or unrelated files.
- Every writer works in a separate topic branch and sibling worktree. Use agent-team worktree <role> <task> and pass that directory to `agent-team spawn -C`. Every agent verifies `pwd` equals its assigned directory before any edit, and Chief checks each pane's cwd; agent-definition isolation settings are not relied on.
- Never push directly to main/master or the remote default branch, force push, or overwrite unrelated work. Stage explicit paths; make focused commits as <type>(<scope>): <summary> with linked issue references.
- Test each coherent behavior before committing. Push reviewable atomic batches only after Validator and Chief approve the exact HEAD. New commits invalidate previous approval. Prefer agent-team gate record ... and agent-team gate push ... for the mechanical SHA gate; raw git commands still require the same policy.
- Open a PR linked to issues with Closes #N and local verification evidence. The user is final merge authority unless they explicitly delegate merging to Chief. Chief approves technical readiness; that alone is not user merge approval.

## Local review and verification
- Run focused behavior tests for each change and appropriate lint/type/build/integration checks locally. Bug fixes require fail-before/pass-after regression evidence where feasible. Do not weaken tests or assert verification that did not run.
- Validator independently reviews every writer's code and the integrated result. Run CodeRabbit CLI locally before push/PR: inspect installed help, typically coderabbit review --agent --base <base>. Inspect findings; exit code zero alone is not a clean verdict. Resolve security/performance findings and document other dispositions. Missing authentication/tool/network leaves review pending.
- STRICT NO CI: do not create, configure, trigger or rely on remote CI/CD for gates. Existing third-party repository automation may still trigger on a push; report this rather than promising control over remote settings. Choose another delivery path if the user requires zero remote runs.
- For HTTP features, serve on 0.0.0.0, verify health and actual feature behavior using curl/browser, and report localhost plus WSL IP URLs with verified status and stop instructions. For a TUI, use a PTY and verify interactions; it need not invent an HTTP port. Leave a requested demo running and explain how to stop it.
- Handoff: task/issue, branch/worktree, changed paths, exact SHA, test commands/results, CodeRabbit findings, Validator verdict, Chief decision, PR and remaining risks.

## Learning and skills
- Record stable user preferences with date, provenance, scope and confidence in ~/.agent-team/memory/preferences.md. Each role keeps ~/.agent-team/memory/<role>/MEMORY.md. Keep project facts in repository docs, not global memory.
- Self-learning means maintained notes and reusable skills, not model weight training. Never store credentials or private payloads in memory. Distinguish explicit corrections from inference, retire contradicted notes, disclose meaningful learning.
- After a repeated successful workflow, create a narrow SKILL.md with trigger, inputs, procedure, outputs, meaningful verification and failure handling. Reuse ECC/CCPM where appropriate. Share personal skills through ~/.agent-team/skills and the user discovery directories; use agent-team sync after approved updates to synchronize Windows snapshots.
- Autonomy stays inside the requested scope. Never leak secrets, delete unrelated data, deploy to production or incur unapproved recurring costs. Preserve backups before changing personal configuration.
