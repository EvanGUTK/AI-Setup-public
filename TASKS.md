# Tasks

Tracking issue: private tracker issues 1 (original setup)

- [x] Inspect WSL and Windows CLI versions and existing plugins/config.
- [x] Install shared rules and YOLO defaults while preserving existing hooks.
- [x] Create 12 global native roles and 120 focused skills.
- [x] Configure Chief/Validator startup prompts and model defaults.
- [x] Install worktree and exact-SHA push helpers.
- [x] Install WSL/Windows team launchers and profile integration.
- [x] Verify CCPM and ECC for both providers on both operating environments.
- [x] Verify existing Herdr and install official Hermes in WSL.
- [x] Complete 22 local behavioral tests; independent review corrections implemented.
Publication gate: run CodeRabbit locally, resolve findings and record exact-SHA approvals.
Delivery: push the approved topic branch and open a linked PR; user controls merge. Track final publication state on issue #1 and its PR.

## Issue #3: pane-based, provider-exclusive teams

- [x] Provider-specific Chief prompts `team/bootstrap-claude.txt` and `team/bootstrap-codex.txt` (remove `bootstrap.txt`); seeds in `build_setup.py`.
- [x] Universal rules, Chief/Validator roles, team-bootstrap, agent-selection, worktree-isolation, project-plan and progress-steering skills, ROSTER and docs describe pane-per-agent, tiled layout, overflow window, file mailbox with pane notice, and Chief as the only user contact.
- [x] Delivery cadence: one user-testable increment at a time; no autonomous loops unless the user asks.
- [ ] Platform: `agent-team spawn/send/inbox/panes`, launcher provider identity, bootstrap rendering, `sync` of both bootstrap files, worker prompt rules and tests (`team/team.py`, `team/install_launchers.py`, `tests/test_team.py`).
- [ ] Integration: Chief integrates both branches, runs `python3 -m unittest discover -s tests`, Validator review, live pane-team check and PR linked to #3.

## Issue #5: one-prompt install for any user

- [ ] Platform: `install.sh` (dry-run, backups, restore, idempotent, `--home`, WSL Windows mirror, bash 3.2/BSD), consolidated `install.ps1`, `agent-team doctor [--json]`, path de-hard-coding in `team/*` and `tests/test_team.py`.
- [ ] QA: black-box `tests/test_install.py` and `tests/fixtures/**` (Linux, simulated macOS, WSL; idempotency, backups, restore, dry-run writes nothing, public-data scan).
- [x] Architect: root `CLAUDE.md` / `AGENTS.md` install runbook plus contributor notes; `README.md`, `team/README.md`, `PROJECT.md`, `ARCHITECTURE.md`, `INSTALLATION.md`, `TASKS.md`, `REVIEW.md`, `.gitignore` rewritten for public readers.
- [ ] Integration: Chief merges the three branches, runs `python3 -m unittest discover -s tests`, Validator review, live sandbox install (`--home`), PR linked to #5.
