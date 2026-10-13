<div align="center">

<img src="assets/ai-setup-hero.svg" width="100%" alt="AI-Setup — One brief. One Chief. Visible agents." />

<br />

**A portable Claude Code + Codex engineering-team setup**

*Shared rules · twelve specialist roles · 120 focused skills · visible tmux agents*

[![Platforms](https://img.shields.io/badge/PLATFORMS-WSL2%20%7C%20LINUX%20%7C%20MACOS-174b42?style=for-the-badge&labelColor=121c25)](INSTALLATION.md)
[![Roles](https://img.shields.io/badge/AGENTS-12%20ROLES%20%7C%20120%20SKILLS-278a68?style=for-the-badge&labelColor=121c25)](team/ROSTER.md)
[![Providers](https://img.shields.io/badge/CLI-CLAUDE%20%2B%20CODEX-456ea4?style=for-the-badge&labelColor=121c25)](team/README.md)
[![Checks](https://img.shields.io/badge/TESTING-LOCAL%20ONLY-7a55a0?style=for-the-badge&labelColor=121c25)](REVIEW.md)

[**Quick start**](#quick-start) · [**How it works**](#how-it-works) · [**Agent roster**](#meet-the-team) · [**Install options**](#install-options) · [**Documentation**](#documentation)

</div>

---

> [!IMPORTANT]
> **AI-Setup is a public setup kit—not a hosted AI orchestration service.** It configures local tools and launches Claude-only or Codex-only teams inside tmux. Interactive end-to-end model-team startup has not been fully validated in the repository's local test suite; provider login, model availability, trust prompts, and tmux behavior depend on your installation.

## What is AI-Setup?

AI-Setup gives Claude Code and OpenAI Codex a common operating environment: shared engineering standards, **12 named specialist roles**, **120 skills** (ten per role), and `claude-team` / `codex-team` commands. Chief plans the work and waits for your approval, Validator independently checks results, and editing agents work in **separate Git worktrees**.

| Principle | Behavior |
|:--|:--|
| **Plan before code** | Chief proposes project scope, architecture, dependencies, stack and acceptance criteria |
| **Visible agents** | Each team member gets a native CLI process in its own tmux pane |
| **Explicit ownership** | Editing workers use independent topic branches and worktrees |
| **Atomic verification** | Focused local tests, CodeRabbit review and commit-bound evidence |
| **Review-gated publication** | The local push helper checks two approval records and an exact SHA; merges remain user-controlled |
| **Portable configuration** | Dry runs, backups, restore, WSL mirroring and optional YOLO settings |

## Quick start

### Option A — Let Claude Code or Codex guide installation

```bash
git clone https://github.com/EvanGUTK/AI-Setup-public.git
cd AI-Setup-public
claude                  # or: codex
```

Then tell the agent:

> **Implement this setup in my system. Start with a dry run, explain proposed changes, and ask before installing.**

The repository's `CLAUDE.md` and `AGENTS.md` describe the installation procedure. Authentication is manual.

### Option B — Install directly

```bash
./install.sh --dry-run    # Preview changes; writes nothing
./install.sh              # Interactive installation
# Open a new shell to reload the launchers
agent-team doctor         # Dependency and configuration checks
```

For Windows, run the shell installer **inside Ubuntu/WSL2**, then run `.\install.ps1` from Windows PowerShell to add the Windows launcher integration. Review [full installation instructions](INSTALLATION.md), including backups and restore, first.

## How it works

```mermaid
flowchart TD
    A["Describe your project<br/>and constraints"] --> B["Start Chief + Validator<br/>in a tmux team"]
    B --> C["Chief proposes a detailed<br/>plan and task hierarchy"]
    C --> D{"Approve the plan?"}
    D -- "Revise" --> C
    D -- "Approve" --> E["Select specialist roles<br/>and assign bounded work"]
    E --> F["Isolated Git worktree<br/>for each editing worker"]
    F --> G["Real CLI processes<br/>in separate tmux panes"]
    G --> H["Atomic changes and tests<br/>local CodeRabbit review"]
    H --> I["Validator + Chief review<br/>exact-commit evidence"]
    I --> J{"Verified?"}
    J -- "Fix and retest" --> H
    J -- "Yes" --> K["Guarded topic push<br/>and issue-linked PR"]
    K --> L["User controls merging"]
    classDef lead fill:#154035,stroke:#50cb9b,color:#fff
    classDef gate fill:#503a23,stroke:#e6bc72,color:#fff
    classDef work fill:#1c3241,stroke:#80b5cd,color:#fff
    class A,B,C,L lead
    class D,J gate
    class E,F,G,H,I,K work
```

The workflow is **guided and prompt-driven**, not a separate scheduler guaranteeing automatic agent startup. The Chief's bootstrap prompt instructs it to start Validator first, wait for its acknowledgment, propose a deep plan and obtain user approval before delegation. Team messaging uses durable mailbox files and pane notices.

### Inspect the team, not twelve chat tabs

<div align="center">

<img src="assets/tmux-team-preview.svg" alt="Illustrative tmux grid showing Chief, Validator and four specialist terminal panes" width="100%" />

<sub>Concept illustration; not a captured live session.</sub>

</div>

The default limit is **six panes per tmux window** (`AGENT_TEAM_MAX_PANES`). Additional agents open in another window in the same session. A Claude team is Claude-only; a Codex team is Codex-only. Different providers don't automatically share one internal message bus.

## Meet the team

Twelve installed role definitions each have ten accompanying personal skills. Chief selects useful specialists after plan approval rather than launching everyone indiscriminately.

| Role | Specialization | Role | Specialization |
|:--|:--|:--|:--|
| **Chief** | Planning, delegation, user interaction | **Validator** | Independent review and push gate |
| **Architect** | Architecture, contracts, repository design | **Product** | PRDs, journeys, feature scope |
| **Backend** | Services, APIs, backend tests | **Frontend** | UI and interaction |
| **Engine** | Core runtime and algorithms | **Data** | Storage, schema and migrations |
| **QA** | Regression and integration tests | **Security** | Threat modeling and protections |
| **Platform** | Toolchains and system integration | **Integrator** | Worktrees and merge coordination |

Read the [full roster and all 120 skills](team/ROSTER.md).

## Working with teams

```bash
# Start a team from inside your own project
claude-team "I want to build a scheduling app"
codex-team "Add reporting to this application"

# Inspect environment and running team
agent-team doctor
agent-team panes
agent-team inbox

# Create an isolated editing checkout
agent-team worktree backend reporting

# Inspect exact-SHA local review gates
agent-team gate status
```

For teammates, message routing, pane creation, review records and explicit handoffs, follow [the team guide](team/README.md). The local push helper rejects protected-branch destinations and stale or missing evidence—but **raw Git commands can bypass that helper**; it is a workflow guard, not a system-level security sandbox.

## Install options

| Flag | What it does |
|:--|:--|
| `--dry-run` | Prints expected changes without writing |
| `--yes` | Accepts system-package installation without another prompt |
| `--no-system` | Skips package installation |
| `--yolo` | Opts into permission-bypass defaults where permitted |
| `--home DIR` | Installs under another home for sandbox testing |
| `--windows-home DIR` / `--no-windows` | Controls WSL-to-Windows mirroring |
| `--restore TIMESTAMP` | Restores a recorded backup |

**Permission bypass is OFF by default.** The optional `--yolo` setting can allow a CLI to edit files and run commands without ordinary approval prompts. Use it only in a trusted, contained environment. Organization and project policies may still disallow it.

| Platform | Team sessions |
|:--|:--|
| **Windows / WSL2** | Teams run inside WSL tmux; PowerShell launchers forward team commands |
| **Linux** | Direct terminal + tmux; apt/dnf/pacman prerequisites |
| **macOS** | Direct terminal + tmux; Homebrew supported |

The installer checks Python 3.9+, Git, tmux, GitHub CLI, CodeRabbit and installed Claude/Codex CLIs. ECC and CCPM integration is handled through their supported plugin/skill mechanisms; provider logins are never automated.

## Repository layout

```text
AI-Setup-public/
├── README.md
├── assets/                # Brand artwork and tmux pane diagram
├── install.sh             # WSL, Linux and macOS installation
├── install.ps1            # Windows PowerShell integration
├── team/
│   ├── team.py            # CLI, tmux panes, mailboxes, worktrees and gates
│   ├── build_setup.py     # Role, skill and rules deployment
│   ├── install_launchers.py
│   ├── bootstrap-claude.txt
│   ├── bootstrap-codex.txt
│   ├── models.json        # Requested provider models and effort
│   ├── ROSTER.md
│   ├── UNIVERSAL.md
│   ├── roles/
│   ├── skills/
│   └── README.md
├── tests/                 # Behavioral and installation tests
├── PROJECT.md
├── ARCHITECTURE.md
├── INSTALLATION.md
├── TASKS.md
├── REVIEW.md
├── CLAUDE.md
└── AGENTS.md
```

## Documentation

| Guide | Focus |
|:--|:--|
| [Installation](INSTALLATION.md) | Setup, verification, backup, restore and uninstall |
| [Operator guide](team/README.md) | Starting panes, sending messages, worktrees and Git gates |
| [Architecture](ARCHITECTURE.md) | System boundaries, provider exclusivity, persistence and known limits |
| [Specialist roster](team/ROSTER.md) | All twelve roles and their ten skills |
| [Project definition](PROJECT.md) | Goals, constraints, public repository requirements |
| [Review history](REVIEW.md) | Local CodeRabbit findings, fixes and limitations |
| [Implementation tasks](TASKS.md) | Completed and tracked work |
| [Claude instructions](CLAUDE.md) / [Codex instructions](AGENTS.md) | Agent-facing installation guidance |

### Verify the repository locally

```bash
python3 -m unittest discover -s tests -v
```

The repository does not create remote CI/CD workflows. A passing unit suite or installer doctor check **does not prove** that all configured provider models are available or that a live multi-agent team has completed an end-to-end run.

---

<div align="center">

**One brief. One Chief. Visible agents.**

<sub>Public engineering setup project · No license file detected at time of this README update.</sub>

</div>
