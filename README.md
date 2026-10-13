# AI-Setup

A portable Claude Code and Codex "agent team" setup: shared engineering rules, 12 specialised roles (Chief, Validator, Architect, Product, Backend, Frontend, Engine, Data, QA, Security, Platform, Integrator), 120 focused skills, and `claude-team` / `codex-team` launchers that run each agent as its own tmux pane. Work is planned first, built in isolated git worktrees, reviewed locally, and merged only when you say so. No remote CI is created.

## Install with one prompt

```bash
git clone https://github.com/EvanGUTK/AI-Setup-public
cd AI-Setup-public
claude        # or: codex
```

Then tell the agent: **"implement this in my system"**.

The repository's `CLAUDE.md` / `AGENTS.md` contain the runbook the agent follows:

1. `./install.sh --dry-run` shows every planned change and writes nothing.
2. It asks you once, in a single question, about the steps that need `sudo` (system packages such as tmux, gh, git) and whether to turn on the optional YOLO defaults (see below).
3. `./install.sh` installs. Every file it changes is backed up first, and a second run changes nothing.
4. After you open a new terminal (so the launchers and `PATH` load), `agent-team doctor` checks the result and reports pass/fail, with the exact fix command for anything missing.
5. It lists the logins you still do by hand.

You can also run it yourself, without an agent:

```bash
./install.sh --dry-run
./install.sh                     # add --yes to accept system-package installs, --no-system to skip them
agent-team doctor
```

### Options

| Option | Effect |
| --- | --- |
| `--dry-run` | Print planned changes; write nothing. |
| `--yes` | Accept the system-package (sudo) step without prompting. |
| `--no-system` | Skip system packages; list what to install by hand. |
| `--yolo` | Opt in to YOLO defaults: plain `claude`/`codex` and the team launchers bypass permission prompts. Off by default; managed organisation policy still takes precedence. |
| `--home DIR` | Install into `DIR` instead of `$HOME` (sandbox/testing). |
| `--windows-home DIR` / `--no-windows` | WSL only: choose or skip the Windows mirror. |
| `--restore TIMESTAMP` | Restore the backup in `~/.agent-team/backups/TIMESTAMP/`. |

## Platforms

| Platform | How |
| --- | --- |
| WSL / Ubuntu | `./install.sh`. Also mirrors to your Windows profile; run `install.ps1` from PowerShell for the Windows launchers. |
| Linux | `./install.sh`. apt, dnf and pacman are detected; other package managers get printed manual steps. |
| macOS | `./install.sh`. Needs [Homebrew](https://brew.sh) for system packages; works with the stock bash 3.2. |
| Windows | Run the installer from WSL. `install.ps1` then adds the PowerShell profile functions and `claude-team` / `codex-team` `.cmd` launchers, which call WSL. |

## Prerequisites and manual steps

The installer checks for python3 (3.9+), git, tmux, gh, the CodeRabbit CLI, and the `claude` and/or `codex` CLI. ECC and CCPM plugins are installed through each CLI's plugin mechanism when that CLI is installed and logged in; otherwise `agent-team doctor` marks them missing with the command to run.

Your own `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are kept: the setup's global rules are added as a managed block between marker comments, and re-running replaces only that block.

Logins are never automated. Do these yourself:

```bash
claude            # then /login
codex login
gh auth login
coderabbit auth login
```

## Use it

In a new shell, from your project directory:

```bash
claude-team "I want to build a scheduling app"
codex-team "I want to add reporting to this app"
```

Chief proposes a plan and waits for your approval, then delegates to roles in separate tmux panes, one user-testable increment at a time. See [team/README.md](team/README.md) for the full guide (pane teams, messaging, worktrees, review gates, synchronisation).

## Repository map

| Path | Purpose |
| --- | --- |
| `install.sh`, `install.ps1` | Installers (POSIX/WSL and Windows). |
| `team/` | The package copied to `~/.agent-team`: rules, roles, skills, bootstrap prompts, `team.py` (the `agent-team` CLI), deployers. |
| `tests/` | Unit and black-box install tests: `python3 -m unittest discover -s tests -v`. |
| `PROJECT.md`, `ARCHITECTURE.md`, `INSTALLATION.md`, `TASKS.md`, `REVIEW.md` | Scope, design, install/restore/uninstall, work log, local review record. |
| `CLAUDE.md`, `AGENTS.md` | Install runbook for agents plus contributor notes. |

## Safety

The installer never reads or copies credentials, never pushes anywhere, and does not enable remote CI. Backups of changed configuration can contain sensitive values from your old config; keep them private. Managed organisation policy and project restrictions take precedence over the permission defaults this setup configures.
