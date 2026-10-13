#!/usr/bin/env python3
"""Install launchers, shell integration, plugins and the Windows mirror.

Usage: install_launchers.py [--dry-run] [--no-plugins]
Run after build_setup.py (install.sh runs both). Honors the same environment as build_setup.py.
"""
import argparse, json, os, re, shlex, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_setup as B

RC_BEGIN = '# BEGIN PERSONAL AGENT TEAM'
RC_END = '# END PERSONAL AGENT TEAM'
RC_BLOCK = f'\n{RC_BEGIN}\n[ -f "$HOME/.agent-team/shell.sh" ] && . "$HOME/.agent-team/shell.sh"\n{RC_END}\n'
SHELL_SH = '''# Agent-team defaults. Sourced from interactive shells by the managed rc block.
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac
'''
YOLO_SHELL = '''# YOLO defaults (install.sh --yolo): plain `claude` skips permission prompts. AGENT_TEAM_NO_BYPASS=1 turns it off per command.
claude() { "$HOME/.agent-team/claude" "$@"; }
'''

def cmd_launcher(provider):
    """Bytes of %USERPROFILE%\\.agent-team\\bin\\<provider>-team.cmd. install.ps1 only creates a missing file with the same text."""
    return (f'@echo off\r\nrem Starts {provider}-team inside WSL (distro and home come from wsl-target.json).\r\n'
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\\.agent-team\\windows-team.ps1" -Provider {provider} %*\r\n').encode()

def launcher(provider_args):
    return f'#!/bin/sh\nexec python3 {shlex.quote(str(B.ROOT / "team.py"))} {provider_args}"$@"\n'

def rc_files():
    """Shell startup files that get the managed block: existing ones plus the user's login shell."""
    name = Path(os.environ.get('SHELL', '')).name
    home = B.LINUX
    files = []
    if (home / '.bashrc').exists() or name == 'bash':
        mac_login = name == 'bash' and sys.platform == 'darwin' and not (home / '.bashrc').exists()
        files.append(home / ('.bash_profile' if mac_login else '.bashrc'))
    if (home / '.zshrc').exists() or name == 'zsh': files.append(home / '.zshrc')
    return files

def yolo_on():
    return B.yolo_wanted()

def install_launchers():
    binpath = B.LINUX / '.local/bin'
    yolo = yolo_on()
    if os.environ.get('AGENT_TEAM_NO_YOLO') == '1':
        for shim in (binpath / 'codex', B.ROOT / 'claude', B.ROOT / 'codex'):   # only links to our shim, never a user's binary
            if shim.is_symlink() and Path(os.readlink(shim)) == B.ROOT / 'cli-shim': B.remove(shim)
    for provider in ('claude', 'codex'):
        # The interactive shim only injects the YOLO flag, so it is installed with --yolo only.
        # Claude's native install owns ~/.local/bin/claude: keep that vendor path and use the shell function.
        if yolo:
            if provider == 'codex' and not B.present(binpath / provider): B.link(binpath / provider, B.ROOT / 'cli-shim')
            if not B.present(B.ROOT / provider): B.link(B.ROOT / provider, B.ROOT / 'cli-shim')
        B.write(binpath / (provider + '-team'), launcher(f'launch {provider} '), executable=True)
    B.write(binpath / 'agent-team', launcher(''), executable=True)
    B.write(B.ROOT / 'shell.sh', SHELL_SH + (YOLO_SHELL if yolo else ''))
    for rc in rc_files():
        text = B.slurp(rc) if B.present(rc) else ''
        if RC_BEGIN not in text: B.write(rc, text + RC_BLOCK)

def sync_windows():
    if B.WINDOWS is None: return
    if B.DRY:
        print(f'  would synchronize shared rules, roles, skills and memory to {B.WINDOWS}')
    else:
        import team
        team.WINDOWS = B.WINDOWS
        team.sync(argparse.Namespace())
    win = B.WINDOWS / '.agent-team'
    for provider in ('claude', 'codex'):
        B.write_bytes(win / 'bin' / (provider + '-team.cmd'), cmd_launcher(provider))
    if yolo_on(): B.write(win / 'yolo', B.YOLO_MARKER_TEXT)
    elif os.environ.get('AGENT_TEAM_NO_YOLO') == '1': B.remove(win / 'yolo')
    for name in ('windows-profile.ps1', 'windows-team.ps1', 'install.ps1'):
        if (B.ROOT / name).is_file(): B.write_bytes(win / name, (B.ROOT / name).read_bytes())
    # Where the Windows launchers find the Linux side: written here, read by windows-team.ps1.
    B.write(win / 'wsl-target.json', json.dumps({'distro': os.environ.get('WSL_DISTRO_NAME', ''), 'home': str(B.LINUX)}, indent=2) + '\n')

def windows_installer():
    """Run install.ps1 (PowerShell profile + PATH) when the Windows profile was auto-detected."""
    if B.WINDOWS is None: return
    script = B.WINDOWS / '.agent-team/install.ps1'
    manual = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\\.agent-team\\install.ps1"'
    auto = os.environ.get('AGENT_TEAM_WINDOWS_HOME') is None and not os.environ.get('AGENT_TEAM_SKIP_WINDOWS_INSTALLER')
    if B.DRY:
        print('  would run install.ps1 for the Windows PowerShell profile/PATH' if auto else f'  Windows step (manual): {manual}'); return
    powershell = shutil.which('powershell.exe')
    if not (auto and powershell and script.is_file()):
        print(f'Windows PowerShell integration: run this in Windows PowerShell: {manual}'); return
    try:
        win_path = subprocess.run(['wslpath', '-w', str(script)], capture_output=True, text=True, timeout=15).stdout.strip()
        result = subprocess.run([powershell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', win_path], capture_output=True, text=True, timeout=180)
        print(result.stdout.strip())
        if result.returncode != 0: B.warn('install.ps1 failed; run in Windows PowerShell: ' + manual + ' -- ' + result.stderr.strip()[:200])
    except (OSError, subprocess.SubprocessError) as error:
        B.warn(f'could not run install.ps1 ({error}); run in Windows PowerShell: {manual}')

def cli(provider):
    import team
    try: return team.executable(provider)
    except ValueError: return None

def run_plugin(argv, label):
    """Run one plugin command; failures (not logged in, offline) become warnings, never abort."""
    print('  $ ' + ' '.join(shlex.quote(a) for a in argv))
    if B.DRY: return
    try: result = subprocess.run(argv, capture_output=True, text=True, timeout=240)
    except (OSError, subprocess.SubprocessError) as error:
        B.warn(f'{label} failed ({error}); run it manually'); return
    if result.returncode != 0:
        B.warn(f'{label} failed (exit {result.returncode}): {(result.stderr or result.stdout).strip()[:200]} -- run it manually after logging in')

def install_plugins():
    """ECC through each CLI's own plugin lifecycle; CCPM is a skill handled by build_setup."""
    import team
    for provider in B.installed_providers():
        exe = cli(provider)
        if not exe:
            print(f'  {provider}: CLI not installed; skipping ECC plugin'); continue
        _, text = team.cli_output([exe, 'plugin', 'list'], timeout=60)
        if team.plugin_enabled(text, 'ecc@ecc'):
            print(f'  {provider}: ECC plugin already installed'); continue
        if provider == 'claude':
            if 'ecc@ecc' in text:
                run_plugin([exe, 'plugin', 'enable', 'ecc@ecc', '--scope', 'user'], 'claude ECC enable'); continue
            run_plugin([exe, 'plugin', 'marketplace', 'add', 'affaan-m/ECC'], 'claude ECC marketplace add')
            run_plugin([exe, 'plugin', 'install', 'ecc@ecc', '--scope', 'user'], 'claude ECC install')
        else:
            run_plugin([exe, 'plugin', 'marketplace', 'add', 'affaan-m/ECC'], 'codex ECC marketplace add')
            run_plugin([exe, 'plugin', 'add', 'ecc@ecc'], 'codex ECC install')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='print every planned change; write nothing')
    parser.add_argument('--no-plugins', action='store_true', help='skip the ECC plugin step')
    args = parser.parse_args(argv)
    B.DRY = args.dry_run
    if not B.DRY:
        for script in ('team.py', 'cli-shim', 'build_setup.py', 'install_launchers.py'):
            if (B.ROOT / script).is_file(): (B.ROOT / script).chmod(0o755)
    install_launchers()
    sync_windows()
    B.report()
    B.finish()
    if not (args.no_plugins or os.environ.get('AGENT_TEAM_SKIP_PLUGINS')):
        print('Plugins (ECC):')
        install_plugins()
    windows_installer()
    print('Launchers and shell integration ' + ('planned' if B.DRY else 'installed') + ('' if B.WINDOWS is None else ' (Windows mirror included)') + '.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
