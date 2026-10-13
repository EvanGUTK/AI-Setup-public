#!/usr/bin/env bash
# AI-Setup installer: puts the agent team (roles, skills, rules, launchers) on this machine.
# Works on Ubuntu/Debian/Fedora/Arch (Linux and WSL) and macOS (Homebrew). Windows users run it
# from WSL, then install.ps1 adds the Windows launchers. Compatible with bash 3.2 and BSD tools.
#
#   ./install.sh [--dry-run] [--yes] [--no-system] [--yolo | --no-yolo] [--home DIR]
#                [--windows-home DIR | --no-windows] [--restore TIMESTAMP]
#
#   --dry-run       print every planned change and system command; write and run nothing
#   --yes           run the system-package install (sudo) without asking
#   --no-system     never touch system packages; list what is missing instead
#   --yolo          opt in to YOLO defaults: agents skip permission prompts (off by default)
#   --no-yolo       turn YOLO defaults off again (removes the marker and the bypass keys it added)
#   --home DIR      install into DIR instead of $HOME (sandbox); every write stays under DIR
#   --windows-home  mirror to this Windows profile directory (default: auto-detected on WSL)
#   --no-windows    skip the Windows mirror
#   --restore TS    put back the files saved under <home>/.agent-team/backups/TS
#
# Logins are never automated; the summary lists the commands you still have to run.

DRY=0; YOLO=0; NO_YOLO=0; HOME_SET=0; WIN_SET=0; RESTORE_SET=0; YES=0; NO_SYSTEM=0; HOME_DIR=""; WIN_HOME=""; NO_WIN=0; RESTORE=""

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; }
die() { echo "install.sh: $*" >&2; exit 1; }
usage_error() { echo "install.sh: $*" >&2; echo "Try: ./install.sh --help" >&2; exit 2; }
step() { echo; echo "==> $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --yes|-y) YES=1 ;;
    --no-system) NO_SYSTEM=1 ;;
    --yolo) YOLO=1 ;;
    --no-yolo) NO_YOLO=1 ;;
    --no-windows) NO_WIN=1 ;;
    --home) [ $# -ge 2 ] || usage_error "--home needs a directory"; HOME_DIR="$2"; HOME_SET=1; shift ;;
    --home=*) HOME_DIR="${1#--home=}"; HOME_SET=1 ;;
    --windows-home) [ $# -ge 2 ] || usage_error "--windows-home needs a directory"; WIN_HOME="$2"; WIN_SET=1; shift ;;
    --windows-home=*) WIN_HOME="${1#--windows-home=}"; WIN_SET=1 ;;
    --restore) [ $# -ge 2 ] || usage_error "--restore needs a backup timestamp"; RESTORE="$2"; RESTORE_SET=1; shift ;;
    --restore=*) RESTORE="${1#--restore=}"; RESTORE_SET=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage_error "unknown option: $1" ;;
  esac
  shift
done

[ "$HOME_SET" = 1 ] && [ -z "$HOME_DIR" ] && usage_error "--home needs a non-empty directory"
[ "$WIN_SET" = 1 ] && [ -z "$WIN_HOME" ] && usage_error "--windows-home needs a non-empty directory"
[ "$WIN_SET" = 1 ] && [ "$NO_WIN" = 1 ] && usage_error "--windows-home and --no-windows conflict"
[ "$YOLO" = 1 ] && [ "$NO_YOLO" = 1 ] && usage_error "--yolo and --no-yolo conflict"
if [ "$RESTORE_SET" = 1 ]; then
  case "$RESTORE" in
    [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;;
    *) usage_error "--restore needs a backup timestamp such as 20260101T120000Z (see <home>/.agent-team/backups)" ;;
  esac
fi

REPO="$(cd "$(dirname "$0")" && pwd -P)"
[ -f "$REPO/team/build_setup.py" ] || die "run this from an AI-Setup checkout (team/build_setup.py not found next to install.sh)"

# ---- home and Windows target ---------------------------------------------
if [ -n "$HOME_DIR" ]; then
  case "$HOME_DIR" in /*) ;; *) HOME_DIR="$PWD/$HOME_DIR" ;; esac
  [ "$DRY" = 1 ] || mkdir -p "$HOME_DIR" || die "cannot create $HOME_DIR"
  export HOME="$HOME_DIR"
fi
[ -n "${HOME:-}" ] || die "HOME is not set"
if [ "$NO_WIN" = 1 ]; then export AGENT_TEAM_WINDOWS_HOME=none
elif [ -n "$WIN_HOME" ]; then
  case "$WIN_HOME" in /*) ;; *) WIN_HOME="$PWD/$WIN_HOME" ;; esac
  export AGENT_TEAM_WINDOWS_HOME="$WIN_HOME"
elif [ -n "$HOME_DIR" ]; then export AGENT_TEAM_WINDOWS_HOME=none   # a sandbox never touches the real Windows profile
elif [ -z "${AGENT_TEAM_WINDOWS_HOME+x}" ]; then :
fi

# ---- platform detection ----------------------------------------------------
UNAME_S="$(uname -s 2>/dev/null || echo unknown)"
UNAME_R="$(uname -r 2>/dev/null || echo unknown)"
case "$UNAME_S" in
  Darwin) OS=macos ;;
  Linux) OS=linux ;;
  *) OS=other ;;
esac
IS_WSL=0
if [ "$OS" = linux ]; then
  case "${AGENT_TEAM_WSL:-}" in
    1) IS_WSL=1 ;;
    0) IS_WSL=0 ;;
    *) if [ -n "${WSL_DISTRO_NAME:-}" ]; then IS_WSL=1
       else case "$UNAME_R" in *[Mm]icrosoft*|*WSL*) IS_WSL=1 ;; esac; fi ;;
  esac
fi
export AGENT_TEAM_WSL="$IS_WSL"
PM=""
if [ "$OS" = macos ]; then command -v brew >/dev/null 2>&1 && PM=brew
elif [ "$OS" = linux ]; then
  for candidate in apt-get dnf pacman; do
    if command -v "$candidate" >/dev/null 2>&1; then PM="$candidate"; break; fi
  done
fi
LABEL="$OS"; [ "$IS_WSL" = 1 ] && LABEL="linux (WSL)"
if [ "$OS" = macos ] && [ -z "$PM" ]; then
  echo "Homebrew is not installed. Get it from https://brew.sh, then re-run ./install.sh (or install tmux, gh and git yourself)."
fi

# One backup directory name for every step of this run, so --restore undoes all of it.
if [ -n "$RESTORE" ]; then STAMP="$RESTORE"
else
  AGENT_TEAM_BACKUP_STAMP="${AGENT_TEAM_BACKUP_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
  STAMP="$AGENT_TEAM_BACKUP_STAMP"
fi
export AGENT_TEAM_BACKUP_STAMP="$STAMP"
export PYTHONDONTWRITEBYTECODE=1
CHANGE_LOG="$(mktemp "${TMPDIR:-/tmp}/ai-setup-changes.XXXXXX")" || CHANGE_LOG=""
[ -n "$CHANGE_LOG" ] && export AGENT_TEAM_CHANGE_LOG="$CHANGE_LOG" && trap 'rm -f "$CHANGE_LOG"' EXIT
[ "$YOLO" = 1 ] && export AGENT_TEAM_YOLO=1
[ "$NO_YOLO" = 1 ] && export AGENT_TEAM_NO_YOLO=1

have_python() { command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }
DRYFLAG=""; [ "$DRY" = 1 ] && DRYFLAG="--dry-run"

# ---- restore -----------------------------------------------------------------
if [ -n "$RESTORE" ]; then
  have_python || die "python3 >= 3.9 is required"
  step "Restore backup $RESTORE ($HOME/.agent-team/backups/$RESTORE)"
  python3 "$REPO/team/build_setup.py" --restore "$RESTORE" $DRYFLAG
  exit $?
fi

echo "AI-Setup install: $LABEL, home $HOME${PM:+, package manager $PM}$([ "$DRY" = 1 ] && echo ', DRY RUN: nothing will be written')"

# ---- prerequisites -------------------------------------------------------------
step "Checking prerequisites"
MISSING_PKGS=""   # package-manager package names
MISSING_TOOLS=""  # human names
pkg_name() {      # tool -> package name for $PM
  case "$PM:$1" in
    pacman:python3) echo python ;;
    brew:python3) echo python ;;
    pacman:gh) echo github-cli ;;
    *) echo "$1" ;;
  esac
}
need() {          # need <tool>
  tool="$1"
  if [ "$tool" = python3 ]; then
    if have_python; then echo "  ok   python3 ($(python3 --version 2>&1))"; return; fi
  elif command -v "$tool" >/dev/null 2>&1; then echo "  ok   $tool"; return; fi
  echo "  MISSING  $tool"
  MISSING_TOOLS="$MISSING_TOOLS $tool"
  MISSING_PKGS="$MISSING_PKGS $(pkg_name "$tool")"
}
need python3
need git
need tmux
need gh
MANUAL=""
for tool in claude codex coderabbit; do
  if command -v "$tool" >/dev/null 2>&1 || [ -x "$HOME/.local/bin/$tool" ]; then echo "  ok   $tool"
  else
    case "$tool" in
      claude) hint='curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh && bash /tmp/claude-install.sh' ;;
      codex) hint='npm install -g @openai/codex' ;;
      coderabbit) hint='curl -fsSL https://cli.coderabbit.ai/install.sh -o /tmp/coderabbit-install.sh && sh /tmp/coderabbit-install.sh' ;;
    esac
    echo "  missing  $tool (optional; install it yourself: $hint)"
    MANUAL="$MANUAL
    $hint"
  fi
done

# ---- system packages (the only sudo step) -----------------------------------
if [ -n "$MISSING_PKGS" ]; then
  step "System packages needed:$MISSING_TOOLS"
  SUDO=""
  if [ "$PM" != brew ] && [ "$(id -u 2>/dev/null)" != 0 ]; then SUDO="sudo "; fi
  case "$PM" in
    apt-get) SYS_CMD="${SUDO}apt-get update && ${SUDO}apt-get install -y$MISSING_PKGS" ;;
    dnf) SYS_CMD="${SUDO}dnf install -y$MISSING_PKGS" ;;
    pacman) SYS_CMD="${SUDO}pacman -S --needed --noconfirm$MISSING_PKGS" ;;
    brew) SYS_CMD="brew install$MISSING_PKGS" ;;
    *) SYS_CMD="" ;;
  esac
  if [ -z "$SYS_CMD" ]; then
    echo "  No supported package manager found. Install manually:$MISSING_TOOLS"
  elif [ "$NO_SYSTEM" = 1 ]; then
    echo "  Skipped (--no-system). To install yourself run:"; echo "    $SYS_CMD"
  elif [ "$DRY" = 1 ]; then
    if [ -n "$SUDO" ]; then echo "  SUDO REQUIRED. Would run: $SYS_CMD"; else echo "  Would run: $SYS_CMD"; fi
  else
    GO=0
    if [ "$YES" = 1 ]; then GO=1
    elif [ -t 0 ]; then
      printf '  Run "%s" now? [y/N] ' "$SYS_CMD"; read -r reply </dev/tty || reply=""
      case "$reply" in y|Y|yes|YES) GO=1 ;; esac
    fi
    if [ "$GO" = 1 ]; then
      echo "  Running: $SYS_CMD"
      if sh -c "$SYS_CMD"; then :; else echo "  The system install failed; run it yourself:"; echo "    $SYS_CMD"; fi
    else
      echo "  Not confirmed (pass --yes to allow it). To install yourself run:"; echo "    $SYS_CMD"
    fi
  fi
fi
if ! have_python; then
  if [ "$DRY" = 1 ]; then echo "  (python3 3.9+ is missing: a real run needs it installed first)"
  else die "python3 >= 3.9 is required and was not found. Install it, then run ./install.sh again."; fi
fi

# ---- install ---------------------------------------------------------------------
if have_python; then
  step "Installing team package, roles, skills and rules"
  python3 "$REPO/team/build_setup.py" --package-from "$REPO/team" $DRYFLAG || die "build_setup failed"
  step "Installing launchers, shell integration, plugins and (WSL) the Windows mirror"
  if [ "$DRY" = 1 ]; then LAUNCHER="$REPO/team/install_launchers.py"; else LAUNCHER="$HOME/.agent-team/install_launchers.py"; fi
  python3 "$LAUNCHER" $DRYFLAG || die "install_launchers failed"
fi

# ---- summary ---------------------------------------------------------------------
CHANGED=1
if [ -n "$CHANGE_LOG" ]; then
  CHANGED=0
  while read -r count; do CHANGED=$((CHANGED + count)); done < "$CHANGE_LOG"
  rm -f "$CHANGE_LOG"
fi
echo
[ "$CHANGED" = 0 ] && echo "No changes needed."
if [ "$DRY" = 1 ]; then
  echo "Dry run finished; nothing was changed. Re-run without --dry-run to install."
  if [ -n "$MISSING_PKGS" ] && [ "$NO_SYSTEM" = 0 ]; then echo "System packages need confirmation (sudo): re-run with --yes to allow them."; fi
  exit 0
fi
step "Doctor"
PATH="$HOME/.local/bin:$PATH" python3 "$HOME/.agent-team/team.py" doctor || echo "(doctor reported problems above; the install itself finished)"
echo
if [ -d "$HOME/.agent-team/backups/$STAMP" ]; then
  echo "Done. Backups of anything changed: $HOME/.agent-team/backups/$STAMP (undo with ./install.sh --restore $STAMP)"
else
  echo "Done."
fi
echo
echo "Next: log in once (never automated):"
echo "  claude          then type /login"
echo "  codex login"
echo "  gh auth login"
echo "  coderabbit auth login"
if [ -n "$MANUAL" ]; then echo "Install the missing tools first:$MANUAL"; fi
echo "Then open a new terminal (or: exec \$SHELL -l) and check with: agent-team doctor"
exit 0
