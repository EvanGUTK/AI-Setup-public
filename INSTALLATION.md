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

### Windows with WSL

Run the installer from WSL (Windows users: open an Ubuntu WSL shell). Then, from PowerShell in the repository, run `.\install.ps1` to add the PowerShell profile functions and the `claude-team` / `codex-team` `.cmd` launchers (under `%USERPROFILE%\.agent-team\bin`) that call WSL. Open new shells afterwards to pick up the updated PATH. Plain `claude` / `codex` stay native Windows CLIs; team sessions run in WSL tmux.

### Native Windows (no WSL)

`install-native.ps1` runs on Windows PowerShell 5.1 or newer and needs only Git and Claude Code (Node.js and `gh` are checked and reported if missing). It does not install pane teams, because they need tmux.

```powershell
powershell -ExecutionPolicy Bypass -File .\install-native.ps1 -DryRun   # show every planned change; writes nothing
powershell -ExecutionPolicy Bypass -File .\install-native.ps1           # install the core set
```

What it does, in order:

1. Checks prerequisites (git, claude, node, gh, bash) and reports anything missing.
2. Writes the universal rules as a managed block in `~/.claude/CLAUDE.md`; your own text in that file is kept.
3. Copies the rules, `TEAM_MODE.md`, roster and roles to `~/.agent-team`, and seeds the memory templates and a blank `preferences.md` only if they do not exist.
4. Installs the 120 team skills and `design-match` into `~/.claude/skills`.
5. Fetches CCPM and the design-systems library (an `INDEX.md` plus one `DESIGN.md` per site) from commits pinned in `native/plugins.json`.
6. Adds the marketplaces and installs the plugins from `native/plugins.json` with `claude plugin install <id> --scope user`.
7. Prints the manual steps left for you.

Options: `-DryRun`, `-All` (also install the optional plugin tier), `-SkipPlugins`, `-SkipExtras` (skip CCPM and design systems), `-Restore <timestamp>`, `-Uninstall`, `-TargetHome DIR` (install under `DIR`, for sandbox testing), `-ManifestPath FILE`. A second run changes nothing. The script exits 1 if any step reported a problem.

`native/plugins.json` splits plugins into a **core** tier (installed by default) and an **optional** tier (`-All`: language servers, hosted-service plugins, response-style plugins). Third-party plugins are fetched from their own marketplaces at install time; this repository does not copy their code. Marketplace plugins are **not pinned**: each marketplace's current version installs, and plugins can run hooks and tools with your user permissions. The `tested` field records the version the manifest was verified with, and the install summary notes any already-installed plugin whose version differs. Read `native/plugins.json` and use `-DryRun` to see every `claude plugin` command before you install. CCPM and the design-systems library are different: they are pinned to exact commits. The manifest also lists 19 plugins that arrive through your claude.ai account instead of a marketplace; they appear after you sign in with the same account and cannot be installed by the script.

Two core plugins change behavior at every session start: `caveman` (terse replies) and `ponytail` (minimal-change coding). Turn them off with "stop caveman" and "stop ponytail", or remove them with `claude plugin uninstall`.

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

Repository tests: `python3 -m unittest discover -s tests -v`. `tests/test_native.py` covers the native installer (manifest checks everywhere; installer runs on Windows only, against a fake `claude` command and local git fixtures, with no network).

Not exercised by tests: a full interactive model-team startup, which depends on tmux, authentication, model access and provider policy. Existing plugin-hook trust configuration is left as is.

## Restore

Every file the installer changes is first copied to `~/.agent-team/backups/<timestamp>/`, preserving its path structure. List them with `ls ~/.agent-team/backups/`, then:

```bash
./install.sh --restore <timestamp>
```

Keep backups private: old configuration can contain sensitive values.

On native Windows the same backups are made by `install-native.ps1`, and a backup also records the files the installer created. `.\install-native.ps1 -Restore <timestamp>` puts back every overwritten file byte for byte and removes everything that run created. It does not undo plugin installs.

## Uninstall

Native Windows: `.\install-native.ps1 -Uninstall` (add `-DryRun` to preview). It removes the managed rules block, the team skills, `design-match`, `ccpm` and `~/.claude/design-systems`, backing each up first. It keeps `~/.agent-team` (your preferences and memory) and all plugins, and prints one `claude plugin uninstall <id>` line per manifest plugin if you want those gone too.

Everywhere else:

1. Optionally restore a backup as above.
2. Remove the managed block (between the `agent-team` marker comments) from your shell rc file, and the PowerShell profile block on Windows.
3. Delete the launcher and shim links the installer created (`claude-team`, `codex-team`, `agent-team`) and, if you no longer want it, `~/.agent-team`.
4. Restart your shells.

## Troubleshooting (native Windows)

| Symptom | Fix |
| --- | --- |
| `running scripts is disabled on this system` | Start the script as shown, with `powershell -ExecutionPolicy Bypass -File ...`. |
| `Filename too long` while adding a marketplace | Run `git config --global core.longpaths true`, then run the installer again. Deep marketplace clones can pass the Windows 260-character path limit. |
| `claude CLI not found: plugins were skipped` | Install Claude Code, open a new terminal so `PATH` updates, and run the script again. Rules, skills and extras were still installed. |
| `git not found: CCPM and the design-systems library were skipped` | Install Git for Windows and run the script again. |
| A plugin marked `login` in `native/plugins.json` does nothing | Sign in: start `claude`, run `/login`, and complete that plugin's own sign-in. Logins are never automated. |
| The `coderabbit` plugin cannot review | It also needs the CodeRabbit CLI and `coderabbit auth login`. The CLI's Windows support is not verified here; use WSL if it is missing. |
| Plugins you expected from your claude.ai account are missing | They are account-synced, not marketplace installs. They appear after `/login` with the same account. |

## Optional tools

Hermes and Herdr are separate tools and are not installed by this setup. To install Hermes, download and inspect its official installer from its project site before running it.
