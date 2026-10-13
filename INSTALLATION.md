# Installation, restore and uninstall

## Install

From a clone of this repository (or let an agent do it: start `claude` or `codex` here and say "implement this in my system"):

```bash
./install.sh --dry-run     # show every planned change; writes nothing
./install.sh               # install (add --yes to accept sudo steps, --no-system to skip them)
# open a new terminal so PATH and launchers load, then:
agent-team doctor          # verify; every failure prints its fix command
```

`install.sh` detects the OS (WSL, Linux with apt/dnf/pacman, macOS with Homebrew), checks prerequisites (python3 3.9+, git, tmux, gh, CodeRabbit CLI, `claude` and/or `codex`), installs missing system packages only with `--yes` or interactive confirmation, copies `team/` into `~/.agent-team` (seeding memory templates only if absent), then deploys roles, skills, rules, launchers and a managed shell rc block for bash and zsh. On WSL it also mirrors to the Windows profile. A second run changes nothing.

Options: `--dry-run`, `--yes`, `--no-system`, `--yolo` (opt-in: plain `claude`/`codex` and team launchers default to bypassing permission prompts; off unless requested), `--home DIR` (install under `DIR`, for sandbox testing), `--windows-home DIR` or `--no-windows` (WSL only; override detection with `AGENT_TEAM_WINDOWS_HOME`), `--restore TIMESTAMP`.

### Windows

Run the installer from WSL (Windows users: open an Ubuntu WSL shell). Then, from PowerShell in the repository, run `.\install.ps1` to add the PowerShell profile functions and the `claude-team` / `codex-team` `.cmd` launchers (under `%USERPROFILE%\.agent-team\bin`) that call WSL. Open new shells afterwards to pick up the updated PATH. Plain `claude` / `codex` stay native Windows CLIs; team sessions run in WSL tmux.

### Plugins and logins

ECC and CCPM install through each CLI's own plugin mechanism when that CLI is installed and authenticated; otherwise `agent-team doctor` marks them missing and prints the command. Never copy plugin cache contents. Logins are never automated: run `claude` then `/login`, `codex login`, `gh auth login` and `coderabbit auth login`.

## What gets installed

| Component | Location |
| --- | --- |
| Team package (rules, roles, skills, bootstrap prompts, `agent-team` CLI) | `~/.agent-team/` |
| 12 roles per installed provider | `~/.claude/agents/`, `~/.codex/agents/` |
| 120 skills | `~/.agent-team/skills/`, linked into `~/.claude/skills/` and `~/.agents/skills/` |
| Global rules | Managed block (BEGIN/END marker comments) inside `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`; your own content in those files is preserved |
| Launchers | `claude-team`, `codex-team`, `agent-team` on `PATH`; managed block in your shell rc file |
| Windows mirror (WSL only) | `%USERPROFILE%\.claude`, `.codex`, `.agents`, `.agent-team` |

Chief and Validator use Claude Opus 5.5 / GPT-6.1-Sol at high effort; workers use Sonnet 5.5 / GPT-6-Luna at high (see `team/models.json`). Teams are provider-exclusive and every agent is a tmux pane. The setup does not enable Claude's experimental in-process agent teams. No remote CI is added.

## Verification

`agent-team doctor` reports OS, python, git, tmux, gh (+auth), CodeRabbit (+auth), `claude`/`codex` versions, ECC, CCPM, `~/.agent-team` files, 12 roles per installed provider, 120 skills, global rules, launchers on `PATH`, and the Windows mirror (WSL only). It exits non-zero on any failure; `--json` gives machine-readable output.

Repository tests: `python3 -m unittest discover -s tests -v`.

Not exercised by tests: a full interactive model-team startup, which depends on tmux, authentication, model access and provider policy. Existing plugin-hook trust configuration is left as is.

## Restore

Every file the installer changes is first copied to `~/.agent-team/backups/<timestamp>/`, preserving its path structure. List them with `ls ~/.agent-team/backups/`, then:

```bash
./install.sh --restore <timestamp>
```

Keep backups private: old configuration can contain sensitive values.

## Uninstall

1. Optionally restore a backup as above.
2. Remove the managed block (between the `agent-team` marker comments) from your shell rc file, and the PowerShell profile block on Windows.
3. Delete the launcher and shim links the installer created (`claude-team`, `codex-team`, `agent-team`) and, if you no longer want it, `~/.agent-team`.
4. Restart your shells.

## Optional tools

Hermes and Herdr are separate tools and are not installed by this setup. To install Hermes, download and inspect its official installer from its project site before running it.
