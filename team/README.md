# Claude/Codex agent teams: usage guide

After installing (see the repository `README.md`), open a **new shell** (WSL, Linux or macOS terminal) in your project directory and run:

```bash
claude-team "I want to build a scheduling app"
codex-team "I want to add reporting to this app"
```

Both launch Chief in tmux (with permission bypass when you installed with `--yolo`). Chief's startup prompt (`bootstrap-claude.txt` or `bootstrap-codex.txt`, chosen by the launcher) tells it to run `agent-team spawn validator` first, wait for Validator's acknowledgement with `agent-team inbox`, propose a detailed plan, and wait for your approval before launching builders. This is a model-driven startup instruction, not a daemon that can guarantee a successful spawn. If tmux, authentication or model access fail, Chief must report the failure and stop gated delivery.

Chief is your only point of contact: Validator and workers send questions and blockers to Chief, never to you. Work arrives one user-testable increment at a time. After each, Chief verifies it (tests, Validator, live check), tells you what changed and exactly how to test it (with the demo URL and stop instructions), then waits for your feedback or go-ahead before starting the next. No autonomous loops (`/loop`, continuous or ralph-style agent loops) run unless you explicitly ask for one.

Claude Chief/Validator use Opus 5.5 high; workers use Sonnet 5.5 high. Codex Chief/Validator use GPT-6.1-Sol high; workers use GPT-6-Luna high. High is the default; difficult work can escalate to xhigh.

## Pane teams

Every agent is a visible tmux pane, not an in-process subagent. Teams are provider-exclusive: `claude-team` runs only Claude agents and `codex-team` only Codex agents. The launcher records the provider on the tmux session and exports `AGENT_TEAM_PROVIDER`, `AGENT_TEAM_SESSION`, `AGENT_TEAM_ROLE`, `AGENT_TEAM_STATE` and `AGENT_TEAM_CHIEF_PANE` to Chief and every spawned pane.

```bash
agent-team spawn backend --task reporting -C ../AI-Setup-worktrees/reporting-backend
agent-team send validator "review abc1234"      # durable mailbox file + one-line pane notice
agent-team inbox                                # read and archive unread messages
agent-team panes                                # registry with live/dead status
```

`spawn` opens the pane in Chief's window, titles it by role/task, re-tiles the layout (and again when a pane closes), and opens a new window in the same session once the window holds `AGENT_TEAM_MAX_PANES` panes (default 6). Messages are files under `$AGENT_TEAM_STATE/mailbox/<role>/` (state lives in `~/.agent-team/state/<session>/`); the pane notice only points at the file, so handoffs survive a missed notice. tmux hosts the terminals; it is not a protocol. A separate team of the other provider shares no bus, so exchange durable handoff files and agree ownership.

Check the installation at any time with `agent-team doctor` (add `--json` for machine-readable output); each missing item prints its exact fix command.

Detach tmux with `Ctrl-b d`; list sessions with `tmux ls`; reattach with `tmux attach -t <session>`. Exit Chief normally when finished. Do not kill a tmux session while its workers are writing. Inside an existing tmux session the launcher runs Chief in the current pane. `--no-tmux` runs directly. Options should precede the quoted prompt, for example `codex-team -C /path/to/project "app idea"`.

## Rules and roles

- Shared source: `~/.agent-team/UNIVERSAL.md`.
- Claude automatically loads `~/.claude/CLAUDE.md`.
- Codex automatically loads `~/.codex/AGENTS.md` (an existing AGENTS.override.md takes precedence; none is created here).
- Role roster: `~/.agent-team/ROSTER.md`, with detailed `roles/<role>.md`.
- Agent definitions (used as each pane's role): `~/.claude/agents/<role>.md` and `~/.codex/agents/<role>.toml`.
- Chief startup prompts: `~/.agent-team/bootstrap-claude.txt` and `bootstrap-codex.txt`, with `{{PROVIDER}} {{CHIEF_MODEL}} {{VALIDATOR_MODEL}} {{WORKER_MODEL}} {{EFFORT}}` filled from `models.json`.
- 120 personal skills: ten per role, in `~/.agent-team/skills/`, discovered by Claude from `~/.claude/skills/` and Codex from `~/.agents/skills/`.
- CCPM is a skill, with its bundled references, in both discovery directories. ECC uses each CLI's native plugin installer.
- Preference memory: `~/.agent-team/memory/preferences.md`; per-role notes: `memory/<role>/MEMORY.md`. Claude also supports its native user agent memory. Learning updates notes/skills; it does not train model weights.

Chief, Validator, Architect, Product, Backend, Frontend, Engine, Data, QA, Security, Platform and Integrator are installed globally. Chief chooses specialists after you approve a plan. New roles are created only for a real missing capability.

## Worktrees and local gates

```bash
agent-team worktree backend reporting
# Prints a sibling worktree and feat/reporting-backend branch.
```

Pass that directory to `agent-team spawn -C`; each agent verifies `pwd` equals it before any edit, and Chief checks each pane's cwd with `agent-team panes`. Agent-definition isolation settings are not relied on; the actual cwd is what matters. Do not let agents concurrently edit the same checkout. Chief/Integrator reserve shared files and integrate in dependency order.

Run focused atomic tests, appropriate integration checks and local CodeRabbit review. Put review reports **outside the tracked worktree**, as JSON, including exact `git rev-parse HEAD`, authority, verdict and concrete passing checks. Example:

```json
{"authority":"validator","sha":"<exact HEAD>","verdict":"pass","checks":[{"name":"local tests and review","status":"pass","evidence":"Commands, results and resolved findings"}]}
```

Use `authority: chief` in Chief’s separate report. A failed or missing verdict never grants approval. Validator and Chief record their own approvals after independent review:

```bash
agent-team gate record validator --report /tmp/validator-review.json
agent-team gate record chief --report /tmp/chief-review.json
agent-team gate status
agent-team gate push --remote origin
```

The push helper rejects dirty trees, missing/stale approval, changed evidence, main/master and the remote default branch, distinct/multiple fetch/push destinations and URL rewrite config; it pushes the approved object ID without force. Records live in the repository's shared Git metadata. It is a local workflow helper, not a tamper-proof authority service or an OS-wide interception of raw git. Raw `git push` can bypass the helper, so the universal rule still requires agents to use the gate. Any new commit needs fresh approval. CodeRabbit command completion alone is not a clean review. User merge approval remains required unless explicitly delegated.

No remote CI/CD is created. Existing repository workflows can trigger on a push; this setup cannot control them without separate repository changes.

## Windows and synchronization (WSL only)

On plain Linux and macOS there is no Windows mirror and `agent-team sync` has nothing to do.

On WSL, the Windows mirror lives under `%USERPROFILE%\.claude`, `.codex`, `.agents` and `.agent-team`. PowerShell profiles load the personal launcher functions. `claude-team` and `codex-team` from Windows invoke Ubuntu WSL with tmux and safely pass the current directory and prompt. Normal `claude`/`codex` stay native Windows (they default to bypass only if you installed with `--yolo`). Team sessions started from Windows run in WSL tmux and are pane teams like any other; plain native Windows `claude`/`codex` are single sessions, not teams.

WSL is the shared source of truth. After learning or skill changes run `agent-team sync` to refresh Windows snapshots. Windows team sessions already use WSL memory live. Native Windows agents should write durable shared learning through WSL or reconcile it to the WSL source before syncing.

Open new shells to load functions/PATH changes. CLI permission defaults do not override higher-priority organization policy, project restrictions, managed runtime settings or an explicit safer CLI override.

Backups of changed configuration are in `~/.agent-team/backups/<timestamp>/`, preserving original path structure. To undo, run `./install.sh --restore <timestamp>` from the repository (see `INSTALLATION.md` for manual removal), and restart shells. Keep backups private; old configuration can contain sensitive values.

## Other tools

Herdr (an alternative terminal workspace manager) and Hermes are optional, independent tools that this installer does not install; the team commands deliberately use tmux. Credentials are never copied between tools.
