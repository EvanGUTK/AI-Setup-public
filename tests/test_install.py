"""Black-box tests for the one-prompt installer (issue #5).

install.sh and `agent-team doctor` are exercised only through their command
line, in throwaway HOME directories, with a sealed PATH made of symlinks to a
whitelist of core utilities plus fake tool binaries from tests/fixtures/fakebin.
Nothing here touches the real HOME, the real package managers, or the network.

Contract: CONTRACT-5.md (platform matrix, install.sh interface, doctor).
Set AI_SETUP_REPO to point the suite at another checkout.
"""
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

REPO = Path(os.environ.get('AI_SETUP_REPO') or Path(__file__).resolve().parents[1]).resolve()
FAKEBIN = Path(__file__).resolve().parent / 'fixtures' / 'fakebin'
INSTALL = REPO / 'install.sh'
REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir
# Built from parts so this file itself passes the public-data scan.
PRIVATE_NAME = 'ego' + 'odman'

ROLES = 12
SKILLS = 120
CORE_UTILS = (
    'bash sh env cp mv rm mkdir rmdir ls cat date dirname basename readlink ln chmod touch sed awk '
    'grep egrep fgrep sort uniq tr cut head tail wc find xargs diff cmp mktemp tee printf test [ true '
    'false python3 git id whoami hostname stat tar gzip gunzip sleep realpath expr od install cksum '
    'sha256sum shasum md5sum getconf dd tput rev nproc patch tty pwd cpio chown'
).split()
PLACEHOLDER_USERS = {
    'user', 'users', 'you', 'me', 'name', 'username', 'yourname', 'youruser', 'example', 'ubuntu',
    'public', 'default', 'tester', 'runner', 'someone', 'alice', 'bob', 'foo', 'x',
}


def snapshot(root):
    """Map relative path -> content fingerprint for everything under root (symlinks not followed)."""
    root = Path(root)
    out = {}
    if not root.exists():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            rel = str(p.relative_to(root))
            if p.is_symlink():
                out[rel] = 'l:' + os.readlink(p)
            elif p.is_dir():
                out[rel] = 'd'
            else:
                out[rel] = 'f:' + sha256(p.read_bytes()).hexdigest()
    return out


def read_text_files(root):
    """Yield (path, text) for every readable text file under root, following no symlinks to dirs."""
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink() and not p.exists():
                continue
            try:
                yield p, p.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue


class Sandbox:
    """A throwaway world: target home, decoy HOME, fake windows home, sealed PATH, fake-call log."""

    def __init__(self, tools=('tmux', 'gh', 'coderabbit', 'claude', 'codex', 'apt-get', 'apt', 'sudo'),
                 uname='Linux', uname_r='6.1.0-generic'):
        self.tmp = tempfile.TemporaryDirectory(prefix='ai-setup-qa-')
        self.base = Path(self.tmp.name)
        self.home = self.base / 'target-root'  # never name it 'home': path scans look for /home/<user>
        self.decoy = self.base / 'decoy-root'
        self.win = self.base / 'winhome'
        self.elsewhere = self.base / 'cwd'
        self.bin = self.base / 'bin'
        self.log = self.base / 'fake.log'
        for d in (self.home, self.decoy, self.elsewhere, self.bin):
            d.mkdir()
        (self.decoy / 'sentinel.txt').write_text('untouched\n')
        self.log.write_text('')
        self.extra_env = {'FAKE_UNAME_S': uname, 'FAKE_UNAME_R': uname_r, 'FAKE_WIN_HOME': str(self.win)}
        for util in CORE_UTILS:
            found = shutil.which(util)
            if found:
                os.symlink(found, self.bin / util)
        self.add_tools(('uname',) + tuple(tools))

    def cleanup(self):
        self.tmp.cleanup()

    def add_tools(self, names):
        for name in names:
            dest = self.bin / name
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            os.symlink(FAKEBIN / name, dest)

    def remove_tools(self, names):
        for name in names:
            dest = self.bin / name
            if dest.is_symlink() or dest.exists():
                dest.unlink()

    def env(self, home_is_target=False, **extra):
        env = {
            'PATH': str(self.bin),
            'HOME': str(self.home if home_is_target else self.decoy),
            'LANG': 'C.UTF-8', 'TERM': 'dumb', 'SHELL': '/bin/bash',
            'FAKE_LOG': str(self.log),
            # hermetic: never clone CCPM from the network during tests
            'AGENT_TEAM_CCPM_REPO': str(self.base / 'no-such-ccpm-repo'),
        }
        env.update(self.extra_env)
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def run(self, args, home_is_target=False, cwd=None, stdin='', script=None, timeout=180, **extra):
        cmd = [str(script or INSTALL)] + list(args)  # executed directly: proves shebang + exec bit work
        env = self.env(home_is_target=home_is_target, **extra)
        return subprocess.run(cmd, cwd=cwd or REPO, env=env, input=stdin, capture_output=True, text=True,
                              timeout=timeout, start_new_session=True)

    def install(self, *flags, home_is_target=False, **kw):
        args = list(flags)
        if not home_is_target and '--home' not in args:
            args = ['--home', str(self.home)] + args
        if '--windows-home' not in args and '--no-windows' not in args and not home_is_target:
            args += ['--no-windows']
        return self.run(args, home_is_target=home_is_target, **kw)

    def doctor(self, *args, home=None, **extra):
        home = Path(home or self.home)
        env = self.env(home_is_target=True, **extra)
        env['HOME'] = str(home)
        env['PATH'] = f'{home / ".local/bin"}:{self.bin}'
        return subprocess.run([str(home / '.local/bin/agent-team'), 'doctor', *args], env=env, cwd=self.elsewhere,
                              capture_output=True, text=True, timeout=120, start_new_session=True)

    def calls(self):
        return [l for l in self.log.read_text().splitlines() if l.strip()]

    def calls_matching(self, pattern):
        rx = re.compile(pattern)
        return [c for c in self.calls() if rx.search(c)]


def output(proc):
    return f'\n--- rc={proc.returncode}\n--- stdout:\n{proc.stdout}\n--- stderr:\n{proc.stderr}'


class InstallTestCase(unittest.TestCase):
    sandbox_kwargs = {}

    def setUp(self):
        self.sb = Sandbox(**self.sandbox_kwargs)
        self.addCleanup(self.sb.cleanup)
        if not INSTALL.is_file():
            self.fail(f'{INSTALL} is missing (platform deliverable, issue #5)')

    def ok(self, proc, msg=''):
        self.assertEqual(proc.returncode, 0, msg + output(proc))
        return proc.stdout + proc.stderr

    def installed_tree(self):
        return snapshot(self.sb.home)

    def backup_dirs(self, home=None):
        b = Path(home or self.sb.home) / '.agent-team' / 'backups'
        return sorted(p for p in b.iterdir() if p.is_dir()) if b.is_dir() else []

    def files_in(self, root):
        return [p for p in Path(root).rglob('*') if p.is_file() and not p.is_symlink()]


# ---------------------------------------------------------------- harness
class HarnessSelfTests(unittest.TestCase):
    """The fixtures themselves must be trustworthy before they judge install.sh."""

    def test_repo_has_the_assets_the_installer_ships(self):
        self.assertEqual(len(list((REPO / 'team/roles').glob('*.md'))), ROLES)
        skills = [p for p in (REPO / 'team/skills').iterdir() if (p / 'SKILL.md').is_file()]
        self.assertEqual(len(skills), SKILLS)

    def test_sealed_path_hides_real_system_tools(self):
        sb = Sandbox(tools=())
        self.addCleanup(sb.cleanup)
        for hidden in ('tmux', 'gh', 'claude', 'codex', 'brew', 'sudo', 'apt-get'):
            r = subprocess.run(['bash', '-c', f'command -v {hidden}'], env=sb.env(), capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, f'{hidden} leaked into the sealed PATH: {r.stdout}')
        for present in ('python3', 'git', 'bash', 'cp'):
            r = subprocess.run(['bash', '-c', f'command -v {present}'], env=sb.env(), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f'{present} missing from sealed PATH')

    def test_fakes_log_and_follow_env(self):
        sb = Sandbox(tools=('tmux', 'gh', 'sudo', 'apt-get', 'claude'))
        self.addCleanup(sb.cleanup)
        def run(cmd, **extra):
            return subprocess.run(['bash', '-c', cmd], env=sb.env(**extra), capture_output=True, text=True)
        self.assertEqual(run('gh auth status').returncode, 1)
        self.assertEqual(run('gh auth status', FAKE_GH_AUTH=0).returncode, 0)
        self.assertEqual(run('uname -s').stdout.strip(), 'Linux')
        self.assertEqual(run('uname -s', FAKE_UNAME_S='Darwin').stdout.strip(), 'Darwin')
        run('sudo apt-get install -y tmux')
        self.assertEqual(sb.calls_matching(r'^sudo apt-get install'), ['sudo apt-get install -y tmux'])
        self.assertEqual(sb.calls_matching(r'^apt-get install'), ['apt-get install -y tmux'])
        self.assertIn('ecc', run('claude plugin list', FAKE_CLAUDE_PLUGINS='ecc ccpm').stdout)

    def test_snapshot_detects_every_kind_of_change(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'a').write_text('1')
            before = snapshot(root)
            self.assertEqual(before, snapshot(root))
            (root / 'a').write_text('2')
            self.assertNotEqual(before, snapshot(root))
            (root / 'a').write_text('1')
            (root / 'sub').mkdir()
            self.assertNotEqual(before, snapshot(root))


# ---------------------------------------------------------------- static properties
class StaticInstallerTests(unittest.TestCase):
    def setUp(self):
        if not INSTALL.is_file():
            self.fail(f'{INSTALL} is missing (platform deliverable, issue #5)')
        self.text = INSTALL.read_text()
        self.code = '\n'.join(l for l in self.text.splitlines() if not l.lstrip().startswith('#'))

    def test_executable_with_bash_shebang_and_valid_syntax(self):
        self.assertTrue(INSTALL.stat().st_mode & stat.S_IXUSR, 'install.sh must be executable (git mode 100755)')
        self.assertRegex(self.text.splitlines()[0], r'^#!(/usr/bin/env bash|/bin/bash)\s*$')
        r = subprocess.run(['bash', '-n', str(INSTALL)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(shutil.which('shellcheck'), 'shellcheck not installed')
    def test_shellcheck_has_no_errors(self):
        r = subprocess.run(['shellcheck', '-S', 'error', str(INSTALL)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_bash32_compatible_constructs_only(self):
        banned = {
            r'\bdeclare\s+-A\b': 'associative arrays need bash 4',
            r'\bmapfile\b|\breadarray\b': 'mapfile/readarray need bash 4',
            r'\$\{[A-Za-z_]\w*(,,|\^\^|,|\^)\}': 'case-modifying expansion needs bash 4',
            r'&>>': '&>> needs bash 4',
            r'\|&': '|& needs bash 4',
            r'\[\[\s+-v\s': '[[ -v ]] needs bash 4.2',
            r'\blocal\s+-n\b': 'namerefs need bash 4.3',
            r'\bcoproc\b': 'coproc needs bash 4',
            r'\bwait\s+-n\b': 'wait -n needs bash 4.3',
            r'%\(.*\)T': 'printf %(..)T needs bash 4.2',
        }
        for rx, why in banned.items():
            m = re.search(rx, self.code)
            self.assertIsNone(m, f'{why}: {m.group(0) if m else ""}')

    def test_no_gnu_only_tool_flags(self):
        banned = {
            r'\breadlink\s+-[a-zA-Z]*[fe]\b': 'readlink -f/-e is GNU only',
            r'\bsed\s+(?:-[A-Za-z]+\s+)*-i\s+(?![\'"]{2}|-)': 'sed -i needs a suffix argument on BSD (use -i.bak)',
            r'\bdate\s+(?:-[A-Za-z]+\s+)*(-d|--date)\b': 'date -d is GNU only',
            r'\bgrep\s+(?:-[A-Za-z]+\s+)*-[a-zA-Z]*P': 'grep -P is GNU only',
            r'\bstat\s+(?:-[A-Za-z]+\s+)*-c\b': 'stat -c is GNU only',
            r'-printf\b': 'find -printf is GNU only',
            r'\bxargs\s+(?:-[A-Za-z]+\s+)*-r\b': 'xargs -r is GNU only',
            r'\bmktemp\s+--': 'mktemp long options are GNU only',
            r'\b(cp|mv|ls|rm|ln)\s+(?:-[A-Za-z]+\s+)*--(parents|preserve|no-clobber|backup|reflink|target-directory)': 'GNU long option',
            r'\bsort\s+(?:-[A-Za-z]+\s+)*-V\b': 'sort -V missing on older macOS',
            r'(^|[|;&(]\s*)timeout\s': 'timeout is not shipped with macOS',
        }
        for rx, why in banned.items():
            m = re.search(rx, self.code, re.M)
            self.assertIsNone(m, f'{why}: {m.group(0) if m else ""}')

    def test_realpath_and_sha256sum_have_portable_fallbacks(self):
        if re.search(r'\brealpath\b', self.code):
            self.assertRegex(self.code, r'command -v realpath|type realpath|which realpath', 'realpath is missing on older macOS')
        if re.search(r'\bsha256sum\b', self.code):
            self.assertIn('shasum', self.code, 'sha256sum is missing on macOS; fall back to shasum -a 256')

    def test_no_curl_pipe_shell_and_no_automated_logins(self):
        self.assertNotRegex(self.code, r'(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh', 'never pipe network content into a shell')
        for rx in (r'(?<!echo )(?<!printf )\bgh\s+auth\s+login\b', r'\bcoderabbit\s+auth\s+login\b', r'\bcodex\s+login\b'):
            for line in self.code.splitlines():
                if re.search(rx, line):
                    self.assertRegex(line, r'echo|printf|cat|<<|["\']', f'login must only be printed, never run: {line}')


class WindowsInstallerStaticTests(unittest.TestCase):
    def setUp(self):
        self.ps1 = REPO / 'install.ps1'
        if not self.ps1.is_file():
            self.fail('install.ps1 is missing (platform deliverable, issue #5)')
        self.text = self.ps1.read_text(encoding='utf-8-sig')

    def test_consolidated_old_windows_scripts_are_gone(self):
        for old in ('team/install-windows.ps1', 'team/install-ecc-windows.ps1'):
            self.assertFalse((REPO / old).exists(), f'{old} must be consolidated into install.ps1 and deleted')

    def test_creates_launchers_that_call_wsl_and_profile_integration(self):
        low = self.text.lower()
        for needle in ('claude-team', 'codex-team', 'wsl', '.cmd', '$profile'):
            self.assertIn(needle, low, f'install.ps1 should mention {needle}')

    def test_is_idempotent_by_construction_and_does_not_hardcode_user_paths(self):
        self.assertNotIn(PRIVATE_NAME, self.text.lower())
        self.assertNotRegex(self.text, r'[A-Za-z]:\\Users\\(?!\$|%)\w+', 'no literal Windows profile paths')

    @unittest.skipUnless(shutil.which('pwsh'), 'pwsh not installed')
    def test_parses_in_powershell(self):
        r = subprocess.run(['pwsh', '-NoProfile', '-Command',
                            f'$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("{self.ps1}",[ref]$null,[ref]$e) | Out-Null; if($e){{$e; exit 1}}'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------------------------------------------------------------- CLI surface
class CommandLineTests(InstallTestCase):
    def test_help_exits_zero_and_documents_every_flag(self):
        text = self.ok(self.sb.run(['--help']))
        for flag in ('--dry-run', '--yes', '--no-system', '--home', '--windows-home', '--no-windows', '--restore'):
            self.assertIn(flag, text)
        self.assertEqual(self.sb.calls_matching(r'install|login'), [])

    def test_unknown_flag_is_rejected_without_side_effects(self):
        before = snapshot(self.sb.home)
        p = self.sb.run(['--home', str(self.sb.home), '--definitely-not-a-flag'])
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertIn('--definitely-not-a-flag', p.stdout + p.stderr)
        self.assertEqual(before, snapshot(self.sb.home))

    def test_flag_missing_its_value_is_rejected(self):
        p = self.sb.run(['--home'])
        self.assertNotEqual(p.returncode, 0, output(p))

    def test_windows_home_and_no_windows_conflict(self):
        p = self.sb.run(['--home', str(self.sb.home), '--windows-home', str(self.sb.win), '--no-windows'])
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertEqual(snapshot(self.sb.home), {})

    def test_script_works_from_any_working_directory(self):
        self.ok(self.sb.install('--no-system', cwd=self.sb.elsewhere))
        self.assertTrue((self.sb.home / '.agent-team/team.py').is_file())
        self.assertEqual(os.listdir(self.sb.elsewhere), [])


# ---------------------------------------------------------------- dry run
class DryRunTests(InstallTestCase):
    def test_dry_run_writes_nothing_anywhere(self):
        before = (snapshot(self.sb.home), snapshot(self.sb.decoy), snapshot(self.sb.win), snapshot(self.sb.elsewhere))
        git_before = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout
        text = self.ok(self.sb.run(['--dry-run', '--home', str(self.sb.home), '--windows-home', str(self.sb.win)]))
        after = (snapshot(self.sb.home), snapshot(self.sb.decoy), snapshot(self.sb.win), snapshot(self.sb.elsewhere))
        self.assertEqual(before, after)
        self.assertEqual(git_before, subprocess.run(['git', 'status', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout)
        self.assertRegex(text.lower(), r'dry[- ]run|would')
        self.assertIn('.agent-team', text, 'dry run must show what it would change')
        self.assertGreater(len(text.splitlines()), 5)

    def test_dry_run_with_yes_never_runs_system_or_plugin_installs(self):
        self.sb.remove_tools(['tmux', 'gh'])
        text = self.ok(self.sb.run(['--dry-run', '--yes', '--home', str(self.sb.home), '--no-windows']))
        self.assertEqual(self.sb.calls_matching(r'^sudo|install|login'), [])
        self.assertIn('tmux', text)
        self.assertEqual(snapshot(self.sb.home), {})

    def test_dry_run_into_a_populated_home_changes_nothing(self):
        self.ok(self.sb.install('--no-system'))
        (self.sb.home / '.bashrc').write_text('export MINE=1\n')
        (self.sb.home / '.agent-team/team.py').write_text('# locally modified\n')
        before = snapshot(self.sb.home)
        self.ok(self.sb.run(['--dry-run', '--home', str(self.sb.home), '--no-windows']))
        self.assertEqual(before, snapshot(self.sb.home))

    def test_dry_run_is_deterministic_enough_to_diff_against_real_run(self):
        text = self.ok(self.sb.run(['--dry-run', '--home', str(self.sb.home), '--no-windows']))
        self.ok(self.sb.install('--no-system'))
        for must in ('.bashrc', 'agent-team', 'claude-team'):
            self.assertIn(must, text, f'dry-run should have announced {must}')


# ---------------------------------------------------------------- fresh install
class FreshInstallTests(InstallTestCase):
    def setUp(self):
        super().setUp()
        self.out = self.ok(self.sb.install('--no-system'))
        self.home = self.sb.home

    def test_team_package_is_copied_without_dev_junk(self):
        for rel in ('team.py', 'build_setup.py', 'install_launchers.py', 'models.json', 'UNIVERSAL.md', 'ROSTER.md'):
            self.assertTrue((self.home / '.agent-team' / rel).is_file(), rel)
        names = {p.name for p in (self.home / '.agent-team').rglob('*')}
        self.assertNotIn('__pycache__', names)
        self.assertNotIn('test_install.py', names)
        self.assertNotIn('.git', names)

    def test_twelve_roles_for_each_provider_and_120_skills(self):
        claude = sorted(p.stem for p in (self.home / '.claude/agents').glob('*.md'))
        codex = sorted(p.stem for p in (self.home / '.codex/agents').glob('*.toml'))
        self.assertEqual(len(claude), ROLES, claude)
        self.assertEqual(claude, codex)
        for skills_dir in ('.claude/skills', '.agents/skills'):
            found = [p for p in (self.home / skills_dir).glob('team-*') if (p / 'SKILL.md').is_file()]
            self.assertEqual(len(found), SKILLS, skills_dir)
        self.assertEqual(len(list((self.home / '.agent-team/skills').glob('team-*/SKILL.md'))), SKILLS)

    def test_global_rules_and_settings_are_valid(self):
        for rel in ('.claude/CLAUDE.md', '.codex/AGENTS.md'):
            self.assertGreater(len((self.home / rel).read_text().strip()), 200, rel)
        json.loads((self.home / '.claude/settings.json').read_text())

    def test_memory_templates_are_seeded(self):
        self.assertTrue((self.home / '.agent-team/memory/preferences.md').is_file())
        for role in (p.stem for p in (self.home / '.claude/agents').glob('*.md')):
            self.assertTrue((self.home / f'.agent-team/memory/{role}/MEMORY.md').is_file(), role)

    def test_launchers_exist_are_executable_and_run(self):
        for name in ('agent-team', 'claude-team', 'codex-team'):
            p = self.home / '.local/bin' / name
            self.assertTrue(p.is_file() and os.access(p, os.X_OK), name)
        env = self.sb.env(home_is_target=True)
        env['PATH'] = f'{self.home / ".local/bin"}:{self.sb.bin}'
        r = subprocess.run([str(self.home / '.local/bin/agent-team'), '--help'], env=env, cwd=self.sb.elsewhere,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, output(r))
        self.assertIn('doctor', r.stdout + r.stderr)

    def test_shell_rc_block_is_added_once_and_puts_launchers_on_path(self):
        rc = (self.home / '.bashrc').read_text()
        self.assertIn('.local/bin', rc + (self.home / '.agent-team/shell.sh').read_text())
        self.assertEqual(rc.count('BEGIN PERSONAL AGENT TEAM') + rc.count('BEGIN AGENT TEAM'), 1)
        probe = subprocess.run(['bash', '-c', '. "$HOME/.bashrc"; command -v agent-team'],
                               env={**self.sb.env(home_is_target=True), 'PATH': str(self.sb.bin)}, capture_output=True, text=True)
        self.assertEqual(probe.stdout.strip(), str(self.home / '.local/bin/agent-team'), output(probe))

    def test_zsh_block_added_when_zshrc_exists(self):
        sb = Sandbox()
        self.addCleanup(sb.cleanup)
        (sb.home / '.zshrc').write_text('# my zsh\n')
        sb.extra_env['SHELL'] = '/bin/zsh'
        self.ok(sb.install('--no-system'))
        z = (sb.home / '.zshrc').read_text()
        self.assertIn('# my zsh', z)
        self.assertEqual(z.count('AGENT TEAM'), 2, 'one BEGIN and one END marker')

    def test_output_ends_with_manual_login_steps_and_never_runs_them(self):
        for step in ('/login', 'codex login', 'gh auth login', 'coderabbit auth login'):
            self.assertIn(step, self.out, f'summary must tell the user: {step}')
        self.assertEqual(self.sb.calls_matching(r'\blogin\b|auth login'), [])

    def test_sandbox_run_touched_only_the_target_home(self):
        self.assertEqual(snapshot(self.sb.decoy), {'sentinel.txt': snapshot(self.sb.decoy)['sentinel.txt']})
        self.assertEqual(snapshot(self.sb.win), {})
        self.assertEqual(os.listdir(self.sb.elsewhere), [])
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout
        self.assertNotIn('team/__pycache__', status)

    def test_no_machine_specific_data_in_installed_files(self):
        needles = [PRIVATE_NAME]
        if REAL_HOME not in ('/', ''):
            needles.append(REAL_HOME.rstrip('/') + '/')
        for path, text in read_text_files(self.home):
            for needle in needles:
                self.assertNotIn(needle.lower(), text.lower(), f'{path} embeds {needle}')
        for path in self.home.rglob('*'):
            if path.is_symlink():
                self.assertNotIn(PRIVATE_NAME, os.readlink(path).lower(), path)
                self.assertTrue(os.readlink(path).startswith(str(self.home)) or not os.path.isabs(os.readlink(path)),
                                f'{path} points outside the install: {os.readlink(path)}')

    def test_launchers_embed_only_the_resolved_install_root(self):
        for name in ('agent-team', 'claude-team', 'codex-team'):
            text = (self.home / '.local/bin' / name).read_text()
            self.assertNotIn(PRIVATE_NAME, text)
            for m in re.findall(r'/(?:home|Users)/[^\s"\']+', text):
                self.assertTrue(m.startswith(str(self.home)), f'{name} embeds foreign path {m}')


# ---------------------------------------------------------------- idempotency / backups / restore
class IdempotencyBackupRestoreTests(InstallTestCase):
    def test_second_run_changes_nothing_at_all(self):
        self.ok(self.sb.install('--no-system'))
        first = snapshot(self.sb.home)
        second_out = self.ok(self.sb.install('--no-system'))
        self.assertEqual(first, snapshot(self.sb.home), 'second run must be a no-op, including no new backup directories')
        self.assertRegex(second_out.lower(), r'no changes|nothing to|already|up[- ]to[- ]date|unchanged')

    def test_third_run_after_a_second_still_converges(self):
        for _ in range(3):
            self.ok(self.sb.install('--no-system'))
        snap = snapshot(self.sb.home)
        self.ok(self.sb.install('--no-system'))
        self.assertEqual(snap, snapshot(self.sb.home))

    def test_existing_user_config_is_preserved_or_backed_up(self):
        home = self.sb.home
        (home / '.claude').mkdir()
        (home / '.agent-team').mkdir()
        originals = {
            '.bashrc': 'export MINE=1\nalias ll="ls -l"\n',
            '.claude/CLAUDE.md': 'my private rules, do not lose\n',
            '.claude/settings.json': json.dumps({'theme': 'dark', 'custom': {'keep': True}}),
            '.agent-team/team.py': '# user-modified copy\n',
        }
        for rel, text in originals.items():
            (home / rel).write_text(text)
        self.ok(self.sb.install('--no-system'))
        rc = (home / '.bashrc').read_text()
        self.assertIn('export MINE=1', rc)
        self.assertIn('alias ll="ls -l"', rc)
        settings = json.loads((home / '.claude/settings.json').read_text())
        self.assertEqual(settings.get('theme'), 'dark', 'unrelated settings keys must survive')
        self.assertEqual(settings.get('custom'), {'keep': True})
        self.assertNotEqual((home / '.agent-team/team.py').read_text(), '# user-modified copy\n')
        dirs = self.backup_dirs()
        self.assertEqual(len(dirs), 1, f'one timestamped backup per run: {dirs}')
        backed_up = [p.read_text(errors='replace') for p in self.files_in(dirs[0])]
        for rel in ('.bashrc', '.claude/CLAUDE.md', '.claude/settings.json', '.agent-team/team.py'):
            self.assertIn(originals[rel], backed_up, f'original {rel} was not backed up')

    def test_seeded_memory_is_never_overwritten(self):
        home = self.sb.home
        (home / '.agent-team/memory/qa').mkdir(parents=True)
        (home / '.agent-team/memory/preferences.md').write_text('my real preferences\n')
        (home / '.agent-team/memory/qa/MEMORY.md').write_text('hard-won qa notes\n')
        self.ok(self.sb.install('--no-system'))
        self.ok(self.sb.install('--no-system'))
        self.assertEqual((home / '.agent-team/memory/preferences.md').read_text(), 'my real preferences\n')
        self.assertEqual((home / '.agent-team/memory/qa/MEMORY.md').read_text(), 'hard-won qa notes\n')

    def test_restore_returns_changed_files_to_their_backup(self):
        home = self.sb.home
        (home / '.claude').mkdir()
        originals = {'.bashrc': 'export MINE=1\n', '.claude/CLAUDE.md': 'precious\n',
                     '.claude/settings.json': json.dumps({'theme': 'dark'})}
        for rel, text in originals.items():
            (home / rel).write_text(text)
        self.ok(self.sb.install('--no-system'))
        self.assertNotEqual((home / '.claude/CLAUDE.md').read_text(), 'precious\n')
        ts = self.backup_dirs()[0].name
        self.ok(self.sb.run(['--home', str(home), '--restore', ts, '--no-windows']))
        for rel, text in originals.items():
            self.assertEqual((home / rel).read_text(), text, f'{rel} not restored')

    def test_restore_unknown_timestamp_fails_and_changes_nothing(self):
        self.ok(self.sb.install('--no-system'))
        before = snapshot(self.sb.home)
        p = self.sb.run(['--home', str(self.sb.home), '--restore', '19990101T000000Z', '--no-windows'])
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertEqual(before, snapshot(self.sb.home))

    def test_restore_rejects_path_traversal_timestamps(self):
        self.ok(self.sb.install('--no-system'))
        secret = self.sb.base / 'outside'
        secret.mkdir()
        (secret / 'x').write_text('x')
        before = (snapshot(self.sb.home), snapshot(secret), snapshot(self.sb.decoy))
        for bad in ('../../outside', '/etc', '..'):
            p = self.sb.run(['--home', str(self.sb.home), '--restore', bad, '--no-windows'])
            self.assertNotEqual(p.returncode, 0, f'{bad}: ' + output(p))
        self.assertEqual(before, (snapshot(self.sb.home), snapshot(secret), snapshot(self.sb.decoy)))

    def test_install_over_partial_old_install_repairs_it(self):
        self.ok(self.sb.install('--no-system'))
        victim = self.sb.home / '.claude/agents/qa.md'
        victim.unlink()
        shutil.rmtree(self.sb.home / '.agent-team/skills/team-qa-flaky-tests')
        self.ok(self.sb.install('--no-system'))
        self.assertTrue(victim.is_file())
        self.assertTrue((self.sb.home / '.agent-team/skills/team-qa-flaky-tests/SKILL.md').is_file())

    def test_installing_from_a_checkout_does_not_modify_the_checkout(self):
        before = subprocess.run(['git', 'status', '--porcelain', '--ignored'], cwd=REPO, capture_output=True, text=True).stdout
        self.ok(self.sb.install('--no-system'))
        after = subprocess.run(['git', 'status', '--porcelain', '--ignored'], cwd=REPO, capture_output=True, text=True).stdout
        new_lines = set(after.splitlines()) - set(before.splitlines())
        self.assertFalse([l for l in new_lines if '__pycache__' not in l], new_lines)


# ---------------------------------------------------------------- system packages
class LinuxPackageTests(InstallTestCase):
    sandbox_kwargs = {'tools': ('apt-get', 'apt', 'sudo', 'claude')}

    def test_no_system_skips_sudo_and_lists_what_is_missing(self):
        text = self.ok(self.sb.install('--no-system'))
        self.assertEqual(self.sb.calls_matching(r'^(sudo|apt|apt-get|dnf|pacman|brew)\b.*\binstall\b|^sudo'), [])
        for pkg in ('tmux', 'gh'):
            self.assertIn(pkg, text)
        self.assertIn('coderabbit', text)

    def test_yes_installs_missing_packages_in_one_sudo_batch(self):
        self.ok(self.sb.install('--yes'))
        installs = self.sb.calls_matching(r'^(apt|apt-get) .*install')
        sudo_installs = self.sb.calls_matching(r'^sudo (apt|apt-get) .*install')
        self.assertTrue(installs, self.sb.calls())
        self.assertTrue(sudo_installs, 'package installation must go through sudo')
        self.assertLessEqual(len(sudo_installs), 1, 'ask-once: batch all packages into one install call')
        joined = ' '.join(installs)
        self.assertRegex(joined, r'\btmux\b')
        self.assertRegex(joined, r'\bgh\b|github-cli')

    def test_without_yes_and_without_a_terminal_sudo_is_never_invoked(self):
        for stdin in ('', 'n\n', '\n'):
            self.sb.log.write_text('')
            self.ok(self.sb.install(stdin=stdin))
            self.assertEqual(self.sb.calls_matching(r'^sudo|apt|brew|dnf|pacman'), [], f'stdin={stdin!r}')

    def test_nothing_is_installed_for_tools_that_are_already_present(self):
        self.sb.add_tools(['tmux', 'gh'])
        self.ok(self.sb.install('--yes'))
        joined = ' '.join(self.sb.calls_matching(r'^(apt|apt-get) .*install'))
        self.assertNotRegex(joined, r'\btmux\b')
        self.assertNotRegex(joined, r'\bgh\b')

    def test_failed_sudo_is_reported_and_does_not_corrupt_the_rest(self):
        p = self.sb.install('--yes', FAKE_SUDO_FAIL='1')
        out = p.stdout + p.stderr
        self.assertIn('tmux', out)
        self.assertTrue((self.sb.home / '.agent-team/team.py').is_file() or p.returncode != 0,
                        'either continue installing the user-level parts or fail cleanly')

    def test_root_without_sudo_binary_still_works_or_explains(self):
        self.sb.remove_tools(['sudo'])
        p = self.sb.install('--yes')
        out = p.stdout + p.stderr
        self.assertNotIn('command not found', out)


class OtherLinuxPackageManagerTests(InstallTestCase):
    def pm_sandbox(self, pm):
        sb = Sandbox(tools=(pm, 'sudo'))
        self.addCleanup(sb.cleanup)
        return sb

    def test_dnf(self):
        sb = self.pm_sandbox('dnf')
        proc = sb.install('--yes')
        self.assertEqual(proc.returncode, 0, output(proc))
        self.assertTrue(sb.calls_matching(r'^dnf .*install.*\btmux\b'), sb.calls())

    def test_pacman(self):
        sb = self.pm_sandbox('pacman')
        proc = sb.install('--yes')
        self.assertEqual(proc.returncode, 0, output(proc))
        self.assertTrue(sb.calls_matching(r'^pacman .*-S.*\btmux\b'), sb.calls())

    def test_unknown_package_manager_prints_manual_steps_and_installs_nothing(self):
        sb = Sandbox(tools=('sudo',))
        self.addCleanup(sb.cleanup)
        proc = sb.install('--yes')
        out = self.ok(proc)
        self.assertIn('tmux', out)
        self.assertRegex(out.lower(), r'manual|manually|install .* yourself|please install')
        self.assertEqual(sb.calls_matching(r'install'), [])
        self.assertTrue((sb.home / '.agent-team/team.py').is_file(), 'user-level install should still proceed')


# ---------------------------------------------------------------- macOS simulation
class MacOSTests(InstallTestCase):
    sandbox_kwargs = {'tools': ('brew', 'sw_vers', 'claude'), 'uname': 'Darwin', 'uname_r': '23.5.0'}

    def setUp(self):
        super().setUp()
        self.sb.extra_env.update({'SHELL': '/bin/zsh', 'FAKE_BREW_HAVE': 'git python3'})

    def test_uses_homebrew_never_sudo_or_linux_package_managers(self):
        self.ok(self.sb.install('--yes'))
        brews = self.sb.calls_matching(r'^brew .*install')
        self.assertTrue(brews, self.sb.calls())
        self.assertRegex(' '.join(brews), r'\btmux\b')
        self.assertRegex(' '.join(brews), r'\bgh\b')
        self.assertEqual(self.sb.calls_matching(r'^sudo|^apt|^dnf|^pacman'), [])

    def test_no_system_on_mac_runs_no_brew_install(self):
        out = self.ok(self.sb.install('--no-system'))
        self.assertEqual(self.sb.calls_matching(r'^brew .*install'), [])
        self.assertIn('tmux', out)

    def test_zsh_is_the_default_shell_so_zshrc_gets_the_block(self):
        self.ok(self.sb.install('--no-system'))
        self.assertIn('AGENT TEAM', (self.sb.home / '.zshrc').read_text())

    def test_no_windows_sync_on_mac(self):
        self.ok(self.sb.run(['--home', str(self.sb.home)], WSL_DISTRO_NAME=''))
        self.assertFalse(self.sb.win.exists() and any(self.sb.win.iterdir()))
        self.assertEqual(self.sb.calls_matching(r'^(cmd\.exe|powershell\.exe|wslpath)'), [])

    def test_mac_install_is_idempotent_and_dry_run_is_pure(self):
        before = snapshot(self.sb.home)
        self.ok(self.sb.run(['--dry-run', '--home', str(self.sb.home)]))
        self.assertEqual(before, snapshot(self.sb.home))
        self.ok(self.sb.install('--no-system'))
        first = snapshot(self.sb.home)
        self.ok(self.sb.install('--no-system'))
        self.assertEqual(first, snapshot(self.sb.home))

    def test_missing_homebrew_prints_how_to_get_it(self):
        self.sb.remove_tools(['brew'])
        out = self.ok(self.sb.install('--yes'))
        self.assertRegex(out.lower(), r'homebrew|brew\.sh')


# ---------------------------------------------------------------- WSL simulation
class WslTests(InstallTestCase):
    sandbox_kwargs = {'tools': ('tmux', 'gh', 'coderabbit', 'claude', 'codex', 'apt-get', 'sudo', 'cmd.exe', 'wslpath', 'powershell.exe'),
                      'uname_r': '5.15.153.1-microsoft-standard-WSL2'}

    def wsl_env(self, **extra):
        return dict(WSL_DISTRO_NAME='Ubuntu', WSL_INTEROP='/run/WSL/1_interop', **extra)

    def test_explicit_windows_home_receives_the_mirror(self):
        self.ok(self.sb.run(['--home', str(self.sb.home), '--windows-home', str(self.sb.win), '--no-system'], **self.wsl_env()))
        win = self.sb.win
        self.assertEqual(len(list((win / '.claude/agents').glob('*.md'))), ROLES)
        self.assertTrue((win / '.claude/CLAUDE.md').is_file())
        self.assertTrue((win / '.codex/AGENTS.md').is_file())
        for provider in ('claude', 'codex'):
            cmd = win / '.agent-team/bin' / f'{provider}-team.cmd'
            self.assertTrue(cmd.is_file(), cmd)
            self.assertIn('wsl', cmd.read_text().lower())
        self.assertIsNotNone(next(win.rglob('*.ps1'), None), 'PowerShell profile integration must be mirrored')

    def test_windows_mirror_embeds_no_private_or_linux_user_paths(self):
        self.ok(self.sb.run(['--home', str(self.sb.home), '--windows-home', str(self.sb.win), '--no-system'], **self.wsl_env()))
        for path, text in read_text_files(self.sb.win):
            self.assertNotIn(PRIVATE_NAME, text.lower(), path)
            if REAL_HOME not in ('/', ''):
                self.assertNotIn(REAL_HOME, text, path)

    def test_default_windows_home_is_discovered_via_cmd_exe_and_wslpath(self):
        self.ok(self.sb.run(['--no-system'], home_is_target=True, **self.wsl_env()))
        self.assertTrue(self.sb.calls_matching(r'^cmd\.exe .*USERPROFILE'), self.sb.calls())
        self.assertTrue(self.sb.calls_matching(r'^wslpath'), self.sb.calls())
        self.assertTrue((self.sb.win / '.agent-team/bin/claude-team.cmd').is_file())

    def test_env_override_beats_discovery(self):
        other = self.sb.base / 'override-win'
        self.ok(self.sb.run(['--no-system'], home_is_target=True, AGENT_TEAM_WINDOWS_HOME=other, **self.wsl_env()))
        self.assertTrue((other / '.agent-team/bin/claude-team.cmd').is_file())
        self.assertFalse((self.sb.win / '.agent-team').exists())

    def test_no_windows_flag_skips_the_mirror_entirely(self):
        self.ok(self.sb.run(['--no-system', '--no-windows'], home_is_target=True, **self.wsl_env()))
        self.assertEqual(snapshot(self.sb.win), {})
        self.assertEqual(self.sb.calls_matching(r'^(cmd\.exe|wslpath|powershell\.exe)'), [])

    def test_sandboxed_home_without_windows_home_never_writes_to_windows(self):
        self.ok(self.sb.run(['--home', str(self.sb.home), '--no-system'], **self.wsl_env()))
        self.assertEqual(snapshot(self.sb.win), {}, '--home must confine writes unless --windows-home is given')

    def test_dry_run_on_wsl_writes_nothing_to_either_side(self):
        self.ok(self.sb.run(['--dry-run', '--home', str(self.sb.home), '--windows-home', str(self.sb.win)], **self.wsl_env()))
        self.assertEqual(snapshot(self.sb.home), {})
        self.assertEqual(snapshot(self.sb.win), {})

    def test_wsl_install_is_idempotent_on_both_sides(self):
        args = ['--home', str(self.sb.home), '--windows-home', str(self.sb.win), '--no-system']
        self.ok(self.sb.run(args, **self.wsl_env()))
        first = (snapshot(self.sb.home), snapshot(self.sb.win))
        self.ok(self.sb.run(args, **self.wsl_env()))
        self.assertEqual(first, (snapshot(self.sb.home), snapshot(self.sb.win)))

    def test_windows_side_user_files_are_backed_up_not_lost(self):
        (self.sb.win / '.claude').mkdir(parents=True)
        (self.sb.win / '.claude/CLAUDE.md').write_text('windows-side rules\n')
        self.ok(self.sb.run(['--home', str(self.sb.home), '--windows-home', str(self.sb.win), '--no-system'], **self.wsl_env()))
        found = [p.read_text(errors='replace') for b in self.backup_dirs() for p in self.files_in(b)]
        found += [p.read_text(errors='replace') for p in self.files_in(self.sb.win) if 'backup' in str(p).lower()]
        self.assertIn('windows-side rules\n', found)


# ---------------------------------------------------------------- managed rules block and YOLO opt-in
BLOCK_BEGIN = '<!-- BEGIN AGENT TEAM -->'
BLOCK_END = '<!-- END AGENT TEAM -->'
RULE_FILES = ('.claude/CLAUDE.md', '.codex/AGENTS.md')


class ManagedRulesBlockTests(InstallTestCase):
    def test_fresh_install_writes_exactly_one_marked_block_per_file(self):
        self.ok(self.sb.install('--no-system'))
        for rel in RULE_FILES:
            text = (self.sb.home / rel).read_text()
            self.assertEqual(text.count(BLOCK_BEGIN), 1, rel)
            self.assertEqual(text.count(BLOCK_END), 1, rel)
            self.assertLess(text.index(BLOCK_BEGIN), text.index(BLOCK_END), rel)
            self.assertGreater(len(text[text.index(BLOCK_BEGIN):text.index(BLOCK_END)]), 200, rel)

    def test_users_own_rules_survive_above_and_below_the_block(self):
        home = self.sb.home
        (home / '.claude').mkdir()
        (home / '.codex').mkdir()
        for rel in RULE_FILES:
            (home / rel).write_text('# My own rule: be kind\n')
        self.ok(self.sb.install('--no-system'))
        for rel in RULE_FILES:
            text = (home / rel).read_text()
            self.assertIn('# My own rule: be kind', text, f'{rel} lost the user content')
            self.assertEqual(text.count(BLOCK_BEGIN), 1)
        # The user keeps editing around the block; a re-run may only touch the managed part.
        for rel in RULE_FILES:
            path = home / rel
            path.write_text('# Added above\n' + path.read_text() + '\n# Added below\n')
        self.ok(self.sb.install('--no-system'))
        for rel in RULE_FILES:
            text = (home / rel).read_text()
            self.assertIn('# Added above', text)
            self.assertIn('# Added below', text)
            self.assertIn('# My own rule: be kind', text)
            self.assertEqual(text.count(BLOCK_BEGIN), 1, 'block must not be duplicated on re-run')

    def test_hand_edits_inside_the_block_are_replaced_and_backed_up(self):
        self.ok(self.sb.install('--no-system'))
        path = self.sb.home / '.claude/CLAUDE.md'
        path.write_text(path.read_text().replace(BLOCK_BEGIN, BLOCK_BEGIN + '\nTAMPERED LINE', 1))
        self.ok(self.sb.install('--no-system'))
        self.assertNotIn('TAMPERED LINE', path.read_text())
        backups = [p.read_text(errors='replace') for b in self.backup_dirs() for p in self.files_in(b)]
        self.assertTrue(any('TAMPERED LINE' in t for t in backups), 'replaced block content must be recoverable')

    def test_rules_file_with_only_a_begin_marker_is_not_destroyed(self):
        home = self.sb.home
        (home / '.claude').mkdir()
        (home / '.claude/CLAUDE.md').write_text('keep me\n' + BLOCK_BEGIN + '\nhalf-written, no end marker\n')
        self.sb.install('--no-system')
        everything = (home / '.claude/CLAUDE.md').read_text() + ''.join(
            x.read_text(errors='replace') for b in self.backup_dirs() for x in self.files_in(b))
        self.assertIn('keep me', everything, 'user text must survive in the file or its backup')

    def test_second_run_is_a_noop_with_user_text_present(self):
        (self.sb.home / '.claude').mkdir()
        (self.sb.home / '.claude/CLAUDE.md').write_text('# mine\n')
        self.ok(self.sb.install('--no-system'))
        first = snapshot(self.sb.home)
        self.ok(self.sb.install('--no-system'))
        self.assertEqual(first, snapshot(self.sb.home))

    def test_restore_brings_back_the_pre_install_rules_file(self):
        home = self.sb.home
        (home / '.claude').mkdir()
        (home / '.claude/CLAUDE.md').write_text('# mine only\n')
        self.ok(self.sb.install('--no-system'))
        ts = self.backup_dirs()[0].name
        self.ok(self.sb.run(['--home', str(home), '--restore', ts, '--no-windows']))
        self.assertEqual((home / '.claude/CLAUDE.md').read_text(), '# mine only\n')

    def test_doctor_requires_the_marked_block_not_just_a_file(self):
        self.ok(self.sb.install('--no-system', **HEALTHY))
        (self.sb.home / '.codex/AGENTS.md').write_text('# something unrelated\n')
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertIn('AGENTS.md', p.stdout + p.stderr)


class YoloOptInTests(InstallTestCase):
    """Permission-bypass defaults are opt-in via --yolo; a plain install must not weaken safety."""

    def texts(self, root):
        return {str(p.relative_to(root)): t for p, t in read_text_files(root)}

    def test_help_documents_the_yolo_flag(self):
        self.assertIn('--yolo', self.ok(self.sb.run(['--help'])))

    def test_plain_install_enables_no_permission_bypass_anywhere(self):
        self.ok(self.sb.install('--no-system'))
        home = self.sb.home
        settings = json.loads((home / '.claude/settings.json').read_text())
        self.assertNotEqual(settings.get('permissions', {}).get('defaultMode'), 'bypassPermissions')
        self.assertNotIn('skipDangerousModePermissionPrompt', settings)
        self.assertFalse((home / '.agent-team/yolo').exists())
        cfg = home / '.codex/config.toml'
        codex = cfg.read_text() if cfg.exists() else ''
        self.assertNotIn('danger-full-access', codex)
        self.assertNotRegex(codex, r'approval_policy\s*=\s*"never"')
        for rel, text in self.texts(home).items():
            if rel.startswith(('.claude/agents/', '.codex/agents/')):
                self.assertNotIn('bypassPermissions', text, rel)
            if rel.startswith(('.local/bin/', '.agent-team/shell.sh', '.bashrc', '.zshrc')):
                self.assertNotIn('--dangerously', text, f'{rel} must not add permission-skipping flags by default')

    def test_yolo_flag_opts_in_and_is_recorded(self):
        self.ok(self.sb.install('--no-system', '--yolo'))
        home = self.sb.home
        self.assertTrue((home / '.agent-team/yolo').is_file())
        settings = json.loads((home / '.claude/settings.json').read_text())
        self.assertEqual(settings.get('permissions', {}).get('defaultMode'), 'bypassPermissions')

    def test_yolo_install_is_idempotent(self):
        self.ok(self.sb.install('--no-system', '--yolo'))
        first = snapshot(self.sb.home)
        self.ok(self.sb.install('--no-system', '--yolo'))
        self.assertEqual(first, snapshot(self.sb.home))

    def test_dry_run_with_yolo_writes_nothing_but_mentions_it(self):
        out = self.ok(self.sb.run(['--dry-run', '--yolo', '--home', str(self.sb.home)]))
        self.assertEqual(snapshot(self.sb.home), {})
        self.assertIn('yolo', out.lower())

    def test_user_settings_survive_a_yolo_install(self):
        (self.sb.home / '.claude').mkdir()
        (self.sb.home / '.claude/settings.json').write_text(
            json.dumps({'theme': 'dark', 'permissions': {'allow': ['Bash(ls)']}}))
        self.ok(self.sb.install('--no-system', '--yolo'))
        settings = json.loads((self.sb.home / '.claude/settings.json').read_text())
        self.assertEqual(settings['theme'], 'dark')
        self.assertIn('Bash(ls)', settings['permissions']['allow'])

    def test_plain_install_leaves_existing_permission_rules_untouched(self):
        (self.sb.home / '.claude').mkdir()
        (self.sb.home / '.claude/settings.json').write_text(
            json.dumps({'permissions': {'deny': ['Bash(rm *)'], 'defaultMode': 'default'}}))
        self.ok(self.sb.install('--no-system'))
        perms = json.loads((self.sb.home / '.claude/settings.json').read_text())['permissions']
        self.assertEqual(perms.get('deny'), ['Bash(rm *)'])
        self.assertEqual(perms.get('defaultMode'), 'default')


# ---------------------------------------------------------------- tools / auth / plugins
class ToolAndLoginTests(InstallTestCase):
    def test_missing_ai_clis_are_reported_with_install_hint_not_fatal(self):
        sb = Sandbox(tools=('tmux', 'gh', 'coderabbit', 'apt-get', 'sudo'))
        self.addCleanup(sb.cleanup)
        out = self.ok(sb.install('--no-system'))
        self.assertIn('claude', out.lower())
        self.assertIn('codex', out.lower())

    def test_only_one_provider_cli_is_enough(self):
        sb = Sandbox(tools=('tmux', 'gh', 'coderabbit', 'claude', 'apt-get', 'sudo'))
        self.addCleanup(sb.cleanup)
        self.ok(sb.install('--no-system'))
        self.assertEqual(len(list((sb.home / '.claude/agents').glob('*.md'))), ROLES)

    def test_python_too_old_or_missing_stops_before_writing(self):
        sb = Sandbox()
        self.addCleanup(sb.cleanup)
        os.unlink(sb.bin / 'python3')
        proc = sb.install('--no-system')
        self.assertNotEqual(proc.returncode, 0, output(proc))
        self.assertIn('python', (proc.stdout + proc.stderr).lower())
        self.assertEqual(snapshot(sb.home), {}, 'a failed prerequisite check must not leave a half install')

    def test_git_missing_is_reported(self):
        sb = Sandbox()
        self.addCleanup(sb.cleanup)
        os.unlink(sb.bin / 'git')
        proc = sb.install('--no-system')
        self.assertIn('git', (proc.stdout + proc.stderr).lower())

    def test_plugin_installs_only_through_a_present_claude_cli(self):
        sb = Sandbox(tools=('tmux', 'gh', 'coderabbit', 'codex', 'apt-get', 'sudo'))
        self.addCleanup(sb.cleanup)
        self.ok(sb.install('--no-system'))
        self.assertEqual(sb.calls_matching(r'^claude'), [], 'no claude CLI on PATH: nothing to call (doctor reports the plugins)')

    def test_plugin_install_failure_is_not_fatal(self):
        sb = Sandbox()
        self.addCleanup(sb.cleanup)
        failing = sb.base / 'failing-claude'
        failing.write_text('#!/bin/bash\n[ "$1" = plugin ] && exit 1\nexit 0\n')
        failing.chmod(0o755)
        (sb.bin / 'claude').unlink()
        os.symlink(failing, sb.bin / 'claude')
        proc = sb.install('--no-system')
        self.assertEqual(proc.returncode, 0, output(proc))
        self.assertTrue((sb.home / '.agent-team/team.py').is_file())

    def test_authenticated_state_is_read_but_logins_are_never_triggered(self):
        self.ok(self.sb.install('--no-system', FAKE_GH_AUTH='0', FAKE_CODERABBIT_AUTH='0'))
        self.assertEqual(self.sb.calls_matching(r'login|auth (setup|refresh)|logout'), [])


# ---------------------------------------------------------------- doctor
HEALTHY = dict(FAKE_GH_AUTH='0', FAKE_CODERABBIT_AUTH='0', FAKE_CLAUDE_PLUGINS='ecc@ecc ccpm')


class DoctorTests(InstallTestCase):
    def install_healthy(self, sb=None):
        sb = sb or self.sb
        proc = sb.install('--no-system', **HEALTHY)
        self.assertEqual(proc.returncode, 0, output(proc))

    def test_healthy_install_passes_and_reports_every_checked_item(self):
        self.install_healthy()
        p = self.sb.doctor(**HEALTHY)
        out = self.ok(p, 'doctor on a healthy install')
        low = out.lower()
        for item in ('python', 'git', 'tmux', 'gh', 'coderabbit', 'claude', 'codex', 'ecc', 'ccpm', 'roles', 'skills', 'launcher'):
            self.assertIn(item, low, f'doctor should report {item}')
        self.assertRegex(out, r'12')
        self.assertRegex(out, r'120')

    def test_json_output_is_machine_readable_and_matches_exit_code(self):
        self.install_healthy()
        p = self.sb.doctor('--json', **HEALTHY)
        self.assertEqual(p.returncode, 0, output(p))
        data = json.loads(p.stdout)
        flat = json.dumps(data).lower()
        for item in ('python', 'git', 'tmux', 'gh', 'coderabbit', 'claude', 'codex', 'skills'):
            self.assertIn(item, flat)

    def test_json_failure_exit_code_is_nonzero_and_still_valid_json(self):
        self.install_healthy()
        self.sb.remove_tools(['tmux'])
        p = self.sb.doctor('--json', **HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        json.loads(p.stdout)

    def test_missing_tool_fails_with_the_exact_fix_command(self):
        self.install_healthy()
        self.sb.remove_tools(['tmux'])
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        lines = [l for l in (p.stdout + p.stderr).splitlines() if 'tmux' in l.lower()]
        self.assertTrue(lines, output(p))
        self.assertRegex(' '.join(lines), r'(apt(-get)? install|brew install|dnf install|pacman -S).*tmux|tmux.*(apt(-get)? install|brew install|dnf install|pacman -S)')

    def test_fix_command_matches_the_platform_package_manager(self):
        sb = Sandbox(tools=('gh', 'coderabbit', 'claude', 'codex', 'brew', 'sw_vers'), uname='Darwin', uname_r='23.5.0')
        self.addCleanup(sb.cleanup)
        sb.extra_env['SHELL'] = '/bin/zsh'
        self.install_healthy(sb)
        p = sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertIn('brew install', p.stdout + p.stderr)
        self.assertNotIn('apt', p.stdout + p.stderr)

    def test_unauthenticated_gh_and_coderabbit_show_the_login_commands(self):
        self.install_healthy()
        p = self.sb.doctor(FAKE_GH_AUTH='1', FAKE_CODERABBIT_AUTH='1', FAKE_CLAUDE_PLUGINS='ecc@ecc ccpm')
        out = p.stdout + p.stderr
        self.assertIn('gh auth login', out)
        self.assertIn('coderabbit auth login', out)
        self.assertEqual(self.sb.calls_matching(r'auth login'), [], 'doctor must never log in for the user')

    def test_missing_plugins_are_flagged_with_the_install_command(self):
        self.install_healthy()
        p = self.sb.doctor(FAKE_GH_AUTH='0', FAKE_CODERABBIT_AUTH='0', FAKE_CLAUDE_PLUGINS='')
        out = p.stdout + p.stderr
        self.assertRegex(out.lower(), r'ecc')
        self.assertRegex(out.lower(), r'ccpm')
        self.assertRegex(out, r'plugin')

    def test_deleted_role_or_skill_is_detected(self):
        self.install_healthy()
        (self.sb.home / '.claude/agents/qa.md').unlink()
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertRegex((p.stdout + p.stderr).lower(), r'qa|11')
        self.install_healthy()
        link = self.sb.home / '.claude/skills/team-qa-flaky-tests'
        if link.is_symlink():
            link.unlink()
        else:
            shutil.rmtree(link)
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertRegex(p.stdout + p.stderr, r'119|team-qa-flaky-tests|skills')

    def test_dangling_skill_symlink_is_not_counted_as_present(self):
        self.install_healthy()
        shutil.rmtree(self.sb.home / '.agent-team/skills/team-qa-flaky-tests')
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))

    def test_removed_global_rules_are_detected(self):
        self.install_healthy()
        (self.sb.home / '.codex/AGENTS.md').unlink()
        p = self.sb.doctor(**HEALTHY)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertIn('AGENTS.md', p.stdout + p.stderr)

    def test_launcher_not_on_path_is_reported_with_a_fix(self):
        self.install_healthy()
        env = self.sb.env(home_is_target=True, **HEALTHY)
        env['PATH'] = str(self.sb.bin)  # ~/.local/bin deliberately absent
        p = subprocess.run([str(self.sb.home / '.local/bin/agent-team'), 'doctor'], env=env, cwd=self.sb.elsewhere,
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertRegex((p.stdout + p.stderr), r'(?i)\.local/bin|PATH')

    def test_doctor_without_an_install_fails_and_says_to_run_the_installer(self):
        empty = self.sb.base / 'empty-home'
        empty.mkdir()
        env = self.sb.env(**HEALTHY)
        env['HOME'] = str(empty)
        p = subprocess.run(['python3', str(REPO / 'team/team.py'), 'doctor'], env=env, cwd=self.sb.elsewhere,
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertIn('install.sh', p.stdout + p.stderr)
        self.assertEqual(snapshot(empty), {}, 'doctor is read-only')

    def test_doctor_is_read_only_on_a_healthy_install(self):
        self.install_healthy()
        before = snapshot(self.sb.home)
        self.sb.doctor(**HEALTHY)
        self.sb.doctor('--json', **HEALTHY)
        self.assertEqual(before, snapshot(self.sb.home))
        self.assertEqual(self.sb.calls_matching(r'install|login'), [])

    def test_doctor_checks_the_windows_mirror_on_wsl_only(self):
        sb = Sandbox(tools=('tmux', 'gh', 'coderabbit', 'claude', 'codex', 'cmd.exe', 'wslpath', 'powershell.exe'),
                     uname_r='5.15.153.1-microsoft-standard-WSL2')
        self.addCleanup(sb.cleanup)
        wsl = dict(WSL_DISTRO_NAME='Ubuntu', WSL_INTEROP='/run/WSL/1_interop', AGENT_TEAM_WINDOWS_HOME=sb.win, **HEALTHY)
        proc = sb.run(['--home', str(sb.home), '--windows-home', str(sb.win), '--no-system'], **wsl)
        self.assertEqual(proc.returncode, 0, output(proc))
        p = sb.doctor(**wsl)
        self.assertEqual(p.returncode, 0, output(p))
        self.assertRegex((p.stdout + p.stderr).lower(), r'windows')
        (sb.win / '.agent-team/bin/claude-team.cmd').unlink()
        p = sb.doctor(**wsl)
        self.assertNotEqual(p.returncode, 0, output(p))
        self.assertRegex((p.stdout + p.stderr).lower(), r'windows|claude-team\.cmd')

    def test_non_wsl_doctor_does_not_mention_windows_failures(self):
        self.install_healthy()
        p = self.sb.doctor(**HEALTHY)
        self.assertEqual(p.returncode, 0, output(p))
        self.assertNotRegex((p.stdout + p.stderr).lower(), r'windows.*(missing|fail)')


# ---------------------------------------------------------------- public repository hygiene
class PublicDataScanTests(unittest.TestCase):
    """The repository will be public: no personal names, paths, e-mails, tokens or machine details."""

    ALLOWED_EMAIL_DOMAINS = re.compile(r'@(example\.(com|org|net)|[\w.-]*\.invalid|localhost|anthropic\.com)$', re.I)
    EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b')
    UNIX_USER = re.compile(r'(?:/home|/Users)/([A-Za-z_][\w.-]*)')
    WIN_USER = re.compile(r'[A-Za-z]:[\\/]+Users[\\/]+([A-Za-z_][\w.-]*)')
    SECRETS = [
        re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'), re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}'),
        re.compile(r'sk-ant-[A-Za-z0-9_-]{10,}'), re.compile(r'\bsk-[A-Za-z0-9]{32,}'),
        re.compile(r'AKIA[0-9A-Z]{16}'), re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'),
        re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----'),
        re.compile(r'(?i)\b(?:api[_-]?key|secret|passw(?:or)?d|token)\b\s*[:=]\s*["\'][A-Za-z0-9+/_=-]{16,}["\']'),
    ]

    @classmethod
    def setUpClass(cls):
        listing = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=REPO, capture_output=True)
        cls.files = [REPO / n.decode() for n in listing.stdout.split(b'\0') if n]
        cls.files = [p for p in cls.files if p.is_file()]

    def texts(self):
        for p in self.files:
            try:
                yield p, p.read_text(encoding='utf-8-sig')
            except (UnicodeDecodeError, OSError):
                continue

    def hits(self, finder):
        found = []
        for p, text in self.texts():
            for lineno, line in enumerate(text.splitlines(), 1):
                for hit in finder(line):
                    found.append(f'{p.relative_to(REPO)}:{lineno}: {hit}')
        return found

    def test_scan_actually_covers_the_repository(self):
        rels = {str(p.relative_to(REPO)) for p in self.files}
        self.assertIn('team/team.py', rels)
        self.assertGreater(len(rels), 100)

    def test_no_personal_username_in_content_or_file_names(self):
        found = self.hits(lambda l: [PRIVATE_NAME] if PRIVATE_NAME in l.lower() else [])
        found += [f'path: {p.relative_to(REPO)}' for p in self.files if PRIVATE_NAME in str(p.relative_to(REPO)).lower()]
        self.assertEqual(found, [], f'{len(found)} personal-name hits')

    def test_no_literal_home_directories(self):
        def finder(line):
            out = []
            for rx in (self.UNIX_USER, self.WIN_USER):
                for m in rx.finditer(line):
                    if m.group(1).lower() not in PLACEHOLDER_USERS:
                        out.append(m.group(0))
            return out
        found = self.hits(finder)
        self.assertEqual(found, [], f'{len(found)} hard-coded user paths')

    def test_no_email_addresses_except_documentation_placeholders(self):
        def finder(line):
            return [m.group(0) for m in self.EMAIL.finditer(line) if not self.ALLOWED_EMAIL_DOMAINS.search(m.group(0))]
        found = self.hits(finder)
        self.assertEqual(found, [], f'{len(found)} e-mail addresses')

    def test_no_tokens_or_keys(self):
        found = self.hits(lambda l: [m.group(0)[:12] + '…' for rx in self.SECRETS for m in rx.finditer(l)])
        self.assertEqual(found, [])

    def test_no_state_files_or_credentials_are_tracked(self):
        bad = re.compile(r'(^|/)(\.env(\..*)?|id_rsa|id_ed25519|credentials(\.json)?|\.netrc|auth\.json|settings\.local\.json|\.claude\.json)$')
        offenders = [str(p.relative_to(REPO)) for p in self.files if bad.search(str(p.relative_to(REPO))) and p.name != '.env.example']
        self.assertEqual(offenders, [])
        for p in self.files:
            rel = str(p.relative_to(REPO))
            self.assertFalse(rel.startswith(('memory/', 'backups/', 'profile-backups/', '.worktrees/')), rel)
            self.assertNotIn('__pycache__', rel)


if __name__ == '__main__':
    unittest.main()
