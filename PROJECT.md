# AI-Setup

A portable, one-prompt-installable Claude Code and Codex agent-team setup for WSL/Ubuntu, Linux, macOS and Windows (via WSL).

Behavior it provides: YOLO defaults, shared rules, Chief/Validator team startup, user-approved detailed planning, isolated writer worktrees, atomic tests and commits, local CodeRabbit review, exact-commit push gates, user-controlled merges, no remote CI, CCPM/ECC integration, 12 specialised roles with ten skills each, and shared preference memory.

## Goals

- A new user clones the repository, starts `claude` or `codex`, says "implement this in my system", and ends with a working, verified setup plus a short list of manual login steps.
- Installation is previewable (`--dry-run`), backed up, idempotent and restorable.
- The repository is public: it ships no credentials, session history, private project data, configuration backups or machine-specific paths.

## Non-goals

- Automating logins or storing credentials.
- Remote CI/CD, auto-merge, or pushing on the user's behalf.
- Installing Windows-native agents with team support (team sessions always run in tmux via WSL, Linux or macOS).
- Supporting package managers beyond apt, dnf, pacman and Homebrew; others get printed manual steps.

## Layout

- `install.sh`, `install.ps1`: entry points. `team/`: the package copied to `~/.agent-team`. `tests/`: unit and black-box tests.
- Docs: `README.md` (overview), `team/README.md` (usage guide), `ARCHITECTURE.md`, `INSTALLATION.md`, `TASKS.md`, `REVIEW.md`; `CLAUDE.md` / `AGENTS.md` carry the agent install runbook and contributor notes.

## Install and checks

See `README.md` for the one-prompt flow and `INSTALLATION.md` for restore and uninstall. Verify an installation with `agent-team doctor`. Repository tests: `python3 -m unittest discover -s tests -v`. No remote CI workflow is provided.
