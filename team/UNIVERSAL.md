---
tags: [claude-code, codex, global-rules, brainstorm-first, coderabbit, github-flow]
scope: global
updated: 2026-10-27
---

# Universal engineering rules

## Brainstorm first: never code blind
- Trigger: the user discusses a project, sounds like they want to start one, or asks for a feature, change, update, refactor or fix whose full scope is not already pinned down.
- Before any code, scaffolding, task list or plan, run an in-depth brainstorm (use the brainstorming skill when available) until you can state back WHAT is being built, for whom and why.
- Cover: goal and users; the real-world workflow step by step; scope, non-goals and phases; physical and system constraints (hardware, network, OS, existing software, budget); data and integrations; edge cases, failure modes and abuse cases; how success will be tested and demoed.
- Read existing code and docs first so you do not ask what the repo already answers. Ask a few focused questions at a time, most important first, offer options with a recommendation, and keep a running list of open questions.
- Finish by reflecting the full scope back in your own words and getting the user's confirmation. Only then write PROJECT.md (confirmed facts plus open questions, never invented facts) and move to planning.
- Changes to existing software get the same treatment: current behavior, desired behavior, blast radius, regression risk. The brainstorm scales with the change but is never skipped; only a request that is already fully specified (exact file and exact edit) may go straight to code.
- If the user says something is "not for coding yet" or "just context", record it and do not code.

## Scope of these rules
- Full workflow (plan, issue, topic branch and worktree, review gates) for features, bug fixes and refactors in a git repo. Small fully specified edits and non-repo directories: keep the change targeted, follow conventions, verify, no ceremony.
- Follow direct user instructions and higher-priority runtime or managed policy; these rules never override them.
- Team mode (AGENT_TEAM_PROVIDER set, or the user asks for a team): also read ~/.agent-team/TEAM_MODE.md.
- Windows sessions run in PowerShell; agent-team, tmux, gh and coderabbit may live in WSL. Check WSL before reporting a tool missing.

## Context
- Read relevant files and inspect boundaries before writing. Check PROJECT.md, ARCHITECTURE.md and TASKS.md in the repo root; if absent, record the gap rather than inventing facts.
- Read ~/.agent-team/memory/preferences.md at the start of work. Explicit user corrections are authoritative within their scope; inferred preferences stay tentative.
- Keep changes targeted to the approved task, match repository conventions, preserve unrelated work.

## Plan, then execute autonomously
- For a new app or substantial feature, after the brainstorm propose an in-depth plan: journeys, requirements and non-goals, architecture alternatives, data and contracts, annotated repo tree, dependencies, milestones, acceptance tests, risks, budget and rollback. Wait for explicit approval or modification before provisioning or implementation.
- Approval authorizes ordinary implementation, local tests, installs needed for the plan, topic commits and issue/PR operations within the approved increment. Avoid repeated permission questions. Product decisions and merge approval still need the user's stated authority.
- Deliver one user-testable increment at a time: verify it, then hand over what changed, exact how-to-test steps, and the running demo URL with stop instructions, and wait for the user's go-ahead before the next. Autonomy applies within an approved increment only.
- Give concise progress updates, incorporate steering, report blockers honestly, and ask only for decisions that materially change the outcome.
- No autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly requests one.

## Code quality: no spaghetti
- Small single-purpose functions and modules, clear boundaries, one-directional dependencies. No god files, copy-paste duplication, dead code or speculative abstraction. Reuse and extend existing patterns before adding new ones.
- Handle errors explicitly at boundaries; never swallow them or add silent fallbacks. Validate and type data at boundaries. No magic numbers or hard-coded config.
- Every behavior gets a test; a bug fix starts with a failing test. Never weaken tests.
- Use the matching skills when installed: codebase-design, code-simplification, constraint-driven-development, test-driven-development, systematic-debugging.

## Security baseline
- No secrets in code, logs, commits or memory; keep .env out of git and ship .env.example. Validate all external input, use parameterized queries, enforce authorization on every route, escape output, review dependencies, return safe error messages.
- Run security-and-hardening or a security review on anything touching auth, input, files, network or dependencies before a PR.
- Dev and demo servers bind to 127.0.0.1 by default; use 0.0.0.0 only when something else (such as WSL) needs to reach them, and say so.
- Never deploy to production, incur recurring costs, delete unrelated data or leak secrets without explicit approval.

## UI and design
- Before UI work load design-match: pick references, scan live sites for real tokens, write a spec, build from it, and compare screenshots. For artifacts load artifact-design first.
- No AI-slop patterns. Verify in a real browser at 390px and 1440px, including empty, loading and error states, before claiming done.

## Git and GitHub
- Work in a topic branch and sibling worktree; verify `pwd` before any edit. Never push to main/master or the remote default branch, force push, or overwrite unrelated work. Stage explicit paths; commit as <type>(<scope>): <summary> with linked issue references; test each coherent behavior before committing.
- Create or reuse a GitHub issue before feature or bug work. If there is no remote, auth or network, report the missing prerequisite; never fabricate issue IDs. Use CCPM for PRD, epic, tasks and linked issues; these git rules override CCPM defaults. For a brand-new app, propose private repo provisioning in the plan; never auto-publish the home directory or unrelated files.
- Push only after local review of the exact HEAD (a new commit invalidates it). Open a PR with `Closes #N` and local verification evidence. The user is final merge authority unless they explicitly delegate it.

## Local review and verification
- Run focused tests for each change plus the relevant lint, type, build and integration checks. Never assert verification that did not run.
- Run CodeRabbit locally before push or PR (typically `coderabbit review --agent --base <base>`). Inspect findings: exit code zero alone is not a clean verdict. Resolve security and performance findings, document other dispositions; missing auth, tool or network leaves review pending.
- STRICT NO CI: do not create, configure, trigger or rely on remote CI/CD. Existing third-party automation may still trigger on push; report it rather than promising control.
- HTTP features: verify health and real behavior with curl or a browser, report localhost and WSL IP URLs with verified status and stop instructions, and leave a requested demo running. TUI: verify in a PTY.

## Learning and skills
- Record stable user preferences in ~/.agent-team/memory/preferences.md with date, provenance, scope and confidence; project facts belong in repo docs. Never store credentials or private payloads. Separate explicit corrections from inference, retire contradicted notes, disclose meaningful learning.
- After a repeated successful workflow, create a narrow SKILL.md (trigger, inputs, procedure, outputs, verification, failure handling), reusing ECC/CCPM where appropriate. Share through ~/.agent-team/skills; run `agent-team sync` after approved updates.
- Preserve backups before changing personal configuration.
