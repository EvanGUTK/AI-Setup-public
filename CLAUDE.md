# AI-Setup: agent instructions

This repository packages a Claude Code / Codex "agent team" setup: shared engineering rules, 12 role definitions, 120 skills, `agent-team` tmux pane-team tooling, and installers for WSL/Ubuntu, Linux, macOS and Windows. Which section below applies depends on what the user asked.

## 1. Install runbook — ONLY when the user asks to install this repo

Trigger: the user asks to install, implement, set up or deploy **this** repository on their system (for example "implement this in my system", "install this", "set this up for me"). If the user asked for anything else, skip to section 2 and do not run any installer.

Follow these steps in order. Run commands from the repository root. Do not edit repository files during an install.

1. **Preview.** Run `./install.sh --dry-run`. Read the output and show the user a short summary of what would change: system packages, files copied under `~/.agent-team`, config files touched (each is backed up first), shell rc block, Windows mirror (WSL only). The dry run writes nothing.
2. **Confirm once.** Ask the user a single combined question covering (a) the sudo/system-package steps the dry run listed and (b) whether to enable the opt-in YOLO defaults (`--yolo`: plain `claude`/`codex` and the team launchers default to bypassing permission prompts; managed organisation policy still wins). Recommend nothing beyond describing both; do not enable `--yolo` unless the user says yes. If they decline sudo, or none is available, use `--no-system` and report the packages they must install by hand. Do not ask repeated permission questions for the ordinary file steps; approval of the install covers them.
3. **Install.** Run `./install.sh` (add `--yes` once the user has approved the system-package step, or `--no-system` if they declined it; add `--yolo` only if they opted in). Useful options:
   - `--home DIR` installs into `DIR` instead of `$HOME` (sandbox or testing).
   - `--windows-home DIR` / `--no-windows` choose or skip the Windows mirror on WSL (override detection with `AGENT_TEAM_WINDOWS_HOME`).
   - `--restore TIMESTAMP` restores a backup from `~/.agent-team/backups/<TIMESTAMP>/`.
4. **Verify.** Tell the user the launchers and `PATH` changes load in a new terminal. Run `agent-team doctor` from a new terminal (or `source` the rc file the installer reported, if the command is not yet on `PATH`). Use `agent-team doctor --json` if you need to parse it. Every failing row prints its exact fix command.
5. **Report.** Tell the user which checks passed or failed, what failed and the fix command for each, and the remaining manual steps below. Do not claim success for a check that failed or did not run.

Manual steps the installer never automates (credentials stay with the user): `claude` then `/login`; `codex login`; `gh auth login`; `coderabbit auth login`. ECC and CCPM plugins are installed through each CLI's plugin mechanism when that CLI is present and authenticated; otherwise `agent-team doctor` marks them missing and prints the command.

Platform notes:

- **WSL/Ubuntu:** Linux install plus a Windows mirror (the installer finds the Windows profile via `cmd.exe /c echo %USERPROFILE%`). Windows-side launchers need `install.ps1` run from PowerShell; mention this to Windows users.
- **Native Windows with WSL available:** run the installer from inside WSL. `install.ps1` only adds the PowerShell profile functions and `claude-team` / `codex-team` `.cmd` launchers that call WSL.
- **Native Windows without WSL:** use `install-native.ps1` instead of `install.sh` (see the native runbook below). Pane teams are not available there.
- **Linux:** apt, dnf and pacman are detected. On any other package manager the installer prints the manual steps.
- **macOS:** requires Homebrew for system packages; the installer is bash 3.2 and BSD-tool compatible.
- The install is idempotent: a second run changes nothing. Every changed file is backed up before it is overwritten.
- Global rules (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`) are written as a managed block between BEGIN/END marker comments. The user's own content in those files is preserved, and re-running replaces only the block.

Never push, force-push or open a PR as part of an install. Never paste credentials into files. If a step fails, stop, report the exact error and the fix command, and wait for the user.

### Native Windows runbook (no WSL)

Use this instead of steps 1 to 4 when the machine is Windows without WSL. Run from the repository root in PowerShell.

1. **Preview.** `powershell -ExecutionPolicy Bypass -File .\install-native.ps1 -DryRun`. Summarize what it would change. It writes nothing.
2. **Confirm once.** Ask one question: install the core plugin set only, or also the optional tier (`-All`: language servers, hosted-service plugins, response-style plugins). Mention that `caveman` and `ponytail` change behavior at every session start.
3. **Install.** Run the script without `-DryRun` (add `-All` if the user chose it). It backs up every file it changes under `~/.agent-team/backups/<timestamp>/`. `-Restore <timestamp>` and `-Uninstall` undo it.
4. **Verify.** Read the script's summary. A non-zero exit means a step reported a `PROBLEM` line; report each one with its fix. Do not claim success for a step that failed or was skipped.
5. **Report.** List the manual steps the script printed: `/login` in `claude` (account-synced plugins and logins for plugins marked `login` in `native/plugins.json`), `gh auth login`, `coderabbit auth login`. State that pane teams are unavailable on native Windows.

Plugins and the manifest live in `native/plugins.json`. Third-party code is fetched at install time from pinned marketplaces and commits and is never copied into this repository. Do not edit that manifest during an install.

## 2. Contributing to this repository

For any task other than installing, treat this as an ordinary codebase and follow the workflow in `team/UNIVERSAL.md` (the shared engineering rules) plus these notes.

- **Layout:** `install.sh` / `install.ps1` entry points; `team/` is the package that is copied to `~/.agent-team` (rules, roles, skills, bootstrap prompts, `team.py` = the `agent-team` CLI, `build_setup.py` and `install_launchers.py` = deployers); `tests/` holds the unit and black-box install tests.
- **Docs:** `README.md` (overview and quick start), `PROJECT.md` (scope and goals), `ARCHITECTURE.md` (boundaries and contracts), `INSTALLATION.md` (install, restore, uninstall), `TASKS.md` (work log), `REVIEW.md` (local review record), `team/README.md` (how to use the installed team).
- **Public repository:** no personal names, absolute home paths, emails, tokens, machine details or private history in tracked files. Use `$HOME`, `~`, `%USERPROFILE%` and placeholders. Tests scan tracked files for this.
- **Portability:** `install.sh` must run under bash 3.2 with BSD tools (no GNU-only flags, no associative arrays). Never hard-code a user path; derive it from `HOME`, `--home` or detection.
- **Copies must match:** content seeded by `build_setup.py` and the files under `team/` must stay identical; change both together.
- **Tests:** `python3 -m unittest discover -s tests -v`. Write the test first; bug fixes need a fail-before / pass-after regression. No remote CI is configured and none should be added.
- **Git:** work on a topic branch in a sibling worktree, make conventional commits (`<type>(<scope>): <summary>`) that reference the issue, stage explicit paths, never push to the default branch or force-push. Review locally (including CodeRabbit CLI) before pushing; the repository owner approves merges.
