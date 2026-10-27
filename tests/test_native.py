"""Tests for the native Windows installer (install-native.ps1) and its data files.

The manifest and copy-consistency tests run everywhere. The installer tests run only on Windows
with PowerShell; they use a fake `claude` command and local git repositories, so they need no
network, no real Claude Code and no real home directory.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / 'install-native.ps1'
MANIFEST = REPO / 'native' / 'plugins.json'
POWERSHELL = shutil.which('powershell') or shutil.which('pwsh')
ON_WINDOWS = sys.platform == 'win32' and POWERSHELL is not None
SKILLS = len(list((REPO / 'team' / 'skills').iterdir()))
BEGIN = '<!-- BEGIN AGENT TEAM -->'

FAKE_CLAUDE = '@echo off\r\necho %*>>"%FAKE_CLAUDE_LOG%"\r\nif "%1"=="plugin" if "%2"=="list" echo []\r\nexit /b 0\r\n'


def plugin_id(plugin):
    return f'{plugin["name"]}@{plugin["marketplace"]}'


def load_build_setup():
    spec = importlib.util.spec_from_file_location('build_setup_under_test', REPO / 'team' / 'build_setup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

    def test_marketplaces_have_a_source_or_are_built_in(self):
        for m in self.manifest['marketplaces']:
            self.assertTrue(m.get('builtIn') or re.fullmatch(r'[\w.-]+/[\w.-]+', m.get('source', '')), m)

    def test_every_plugin_points_at_a_declared_marketplace_and_is_unique(self):
        names = {m['name'] for m in self.manifest['marketplaces']}
        ids = [plugin_id(p) for p in self.manifest['plugins']]
        self.assertEqual(len(ids), len(set(ids)), 'duplicate plugin ids')
        for p in self.manifest['plugins']:
            pid = plugin_id(p)
            self.assertTrue(p['name'] and p['marketplace'] in names, pid)
            self.assertNotIn('@', p['name'] + p['marketplace'], pid)
            self.assertIn(p['tier'], ('core', 'optional'), pid)
            self.assertIsInstance(p['login'], bool, pid)
            self.assertTrue(p['tested'], pid)

    def test_both_tiers_exist_and_synced_plugins_are_not_installable_ids(self):
        tiers = {p['tier'] for p in self.manifest['plugins']}
        self.assertEqual(tiers, {'core', 'optional'})
        self.assertTrue(self.manifest['synced'])
        installable = {p['name'] for p in self.manifest['plugins']}
        for name in self.manifest['synced']:
            self.assertNotIn('@', name)
            self.assertNotIn(name, installable, f'{name} is listed as both installable and account-synced')

    def test_extras_are_pinned_to_full_commit_hashes(self):
        for key in ('ccpm', 'designSystems'):
            extra = self.manifest['extras'][key]
            self.assertRegex(extra['sha'], r'^[0-9a-f]{40}$', key)
            self.assertTrue(extra['repo'].startswith('https://'), key)

    def test_no_credentials_in_manifest(self):
        text = MANIFEST.read_text(encoding='utf-8')
        self.assertNotRegex(text, r'(?i)(token|secret|password|api[_-]?key)\s*"?\s*[:=]\s*"[A-Za-z0-9+/_=-]{12,}"')


class CopyConsistencyTests(unittest.TestCase):
    """Repository rule: seeded copies and shipped files must stay identical."""

    def test_embedded_rules_equal_team_universal(self):
        rules = load_build_setup().RULES
        shipped = (REPO / 'team' / 'UNIVERSAL.md').read_text(encoding='utf-8')
        self.assertEqual(rules.strip('\n'), shipped.strip('\n'))

    def test_native_preferences_template_equals_seeded_default(self):
        template = (REPO / 'native' / 'preferences.template.md').read_text(encoding='utf-8')
        self.assertEqual(template, load_build_setup().PREFERENCES)

    def test_universal_rules_lead_with_brainstorm_and_point_to_team_mode(self):
        text = (REPO / 'team' / 'UNIVERSAL.md').read_text(encoding='utf-8')
        self.assertLess(text.index('## Brainstorm first'), text.index('## Scope of these rules'))
        self.assertIn('TEAM_MODE.md', text)
        self.assertTrue((REPO / 'team' / 'TEAM_MODE.md').is_file())

    def test_installer_is_ascii_only(self):
        # Windows PowerShell 5.1 misreads non-ASCII text in a BOM-less file.
        data = INSTALLER.read_bytes()
        self.assertEqual([b for b in data if b > 127], [])


@unittest.skipUnless(ON_WINDOWS, 'needs Windows PowerShell')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ais-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / 'home'
        self.home.mkdir()
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        (self.bin / 'claude.cmd').write_bytes(FAKE_CLAUDE.encode())
        self.log = self.tmp / 'claude-calls.log'
        self.manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

    def run_installer(self, *args, path=None, manifest=None):
        env = dict(os.environ)
        env['PATH'] = path if path is not None else f'{self.bin}{os.pathsep}{os.environ["PATH"]}'
        env['FAKE_CLAUDE_LOG'] = str(self.log)
        cmd = [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(INSTALLER), '-TargetHome', str(self.home)]
        if manifest:
            cmd += ['-ManifestPath', str(manifest)]
        return subprocess.run(cmd + list(args), env=env, capture_output=True, text=True, timeout=300)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def rules_text(self):
        return (self.home / '.claude' / 'CLAUDE.md').read_text(encoding='utf-8')

    def test_dry_run_writes_nothing_and_installs_nothing(self):
        r = self.run_installer('-DryRun', '-SkipExtras')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(self.home.rglob('*')), [])
        self.assertIn('would', r.stdout)
        self.assertEqual([c for c in self.calls() if 'install' in c or 'marketplace add' in c], [])

    def test_core_install_places_rules_skills_memory_and_plugins(self):
        r = self.run_installer('-SkipExtras')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rules_text().count(BEGIN), 1)
        self.assertIn('Brainstorm first', self.rules_text())
        skills = self.home / '.claude' / 'skills'
        self.assertEqual(len(list(skills.glob('team-*/SKILL.md'))), SKILLS)
        self.assertTrue((skills / 'design-match' / 'SKILL.md').is_file())
        self.assertTrue((self.home / '.agent-team' / 'memory' / 'preferences.md').is_file())
        self.assertTrue((self.home / '.agent-team' / 'TEAM_MODE.md').is_file())
        calls = self.calls()
        for m in self.manifest['marketplaces']:
            if not m.get('builtIn'):
                self.assertIn(f'plugin marketplace add {m["source"]}', calls)
        for p in self.manifest['plugins']:
            line = f'plugin install {plugin_id(p)} --scope user'
            (self.assertIn if p['tier'] == 'core' else self.assertNotIn)(line, calls, plugin_id(p))

    def test_all_flag_also_installs_optional_tier(self):
        self.run_installer('-SkipExtras', '-All')
        calls = self.calls()
        for p in self.manifest['plugins']:
            self.assertIn(f'plugin install {plugin_id(p)} --scope user', calls, plugin_id(p))

    def test_users_own_rules_survive_and_restore_brings_back_the_original(self):
        claude = self.home / '.claude'
        claude.mkdir()
        original = b'my private rules, do not lose\n'
        (claude / 'CLAUDE.md').write_bytes(original)
        r = self.run_installer('-SkipExtras', '-SkipPlugins')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('my private rules, do not lose', self.rules_text())
        self.assertEqual(self.rules_text().count(BEGIN), 1)
        again = self.run_installer('-SkipExtras', '-SkipPlugins')
        self.assertIn('already current', again.stdout)
        self.assertEqual(self.rules_text().count(BEGIN), 1)
        stamps = sorted(p.name for p in (self.home / '.agent-team' / 'backups').iterdir())
        self.assertEqual(len(stamps), 1, 'a no-op second run must not create another backup')
        restored = self.run_installer('-Restore', stamps[0])
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assertEqual((claude / 'CLAUDE.md').read_bytes(), original)
        self.assertEqual(list((self.home / '.claude' / 'skills').glob('team-*')) if (self.home / '.claude' / 'skills').exists() else [], [])

    def test_uninstall_removes_block_and_skills_but_keeps_memory(self):
        claude = self.home / '.claude'
        claude.mkdir()
        (claude / 'CLAUDE.md').write_text('keep me\n', encoding='utf-8')
        self.run_installer('-SkipExtras', '-SkipPlugins')
        r = self.run_installer('-Uninstall')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(BEGIN, self.rules_text())
        self.assertIn('keep me', self.rules_text())
        self.assertEqual(list((claude / 'skills').glob('team-*')), [])
        self.assertTrue((self.home / '.agent-team' / 'memory' / 'preferences.md').is_file())

    def test_existing_preferences_are_never_overwritten(self):
        prefs = self.home / '.agent-team' / 'memory' / 'preferences.md'
        prefs.parent.mkdir(parents=True)
        prefs.write_text('my own preferences\n', encoding='utf-8')
        self.run_installer('-SkipExtras', '-SkipPlugins')
        self.assertEqual(prefs.read_text(encoding='utf-8'), 'my own preferences\n')

    def test_missing_claude_is_reported_but_files_still_install(self):
        system = os.environ.get('SystemRoot', r'C:\Windows')
        r = self.run_installer('-SkipExtras', path=f'{system}\\System32;{system}')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('claude CLI not found', r.stdout)
        self.assertEqual(len(list((self.home / '.claude' / 'skills').glob('team-*/SKILL.md'))), SKILLS)

    def test_extras_are_fetched_from_the_pinned_commit(self):
        source = self.tmp / 'upstream'
        (source / 'design-systems' / 'acme').mkdir(parents=True)
        (source / 'design-systems' / 'acme' / 'DESIGN.md').write_text('# Design System Inspired by Acme\n\n> Category: Test\n> Bold and plain.\n', encoding='utf-8')
        (source / 'skill' / 'ccpm').mkdir(parents=True)
        (source / 'skill' / 'ccpm' / 'SKILL.md').write_text('---\nname: ccpm\n---\n', encoding='utf-8')
        (source / 'LICENSE').write_text('Apache License\n', encoding='utf-8')
        git = ['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com']
        subprocess.run(git + ['init', '-q'], cwd=source, check=True)
        subprocess.run(git + ['add', '-A'], cwd=source, check=True)
        subprocess.run(git + ['commit', '-q', '-m', 'fixture'], cwd=source, check=True)
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=source, capture_output=True, text=True, check=True).stdout.strip()
        manifest = dict(self.manifest)
        manifest['extras'] = {
            'ccpm': {'repo': str(source), 'sha': sha, 'path': 'skill/ccpm', 'target': 'ccpm'},
            'designSystems': {'repo': str(source), 'sha': sha, 'path': 'design-systems', 'license': 'Apache-2.0'},
        }
        path = self.tmp / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        r = self.run_installer('-SkipPlugins', manifest=path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        skills = self.home / '.claude' / 'skills'
        self.assertTrue((skills / 'ccpm' / 'SKILL.md').is_file())
        design = self.home / '.claude' / 'design-systems'
        self.assertTrue((design / 'acme' / 'DESIGN.md').is_file())
        index = (design / 'INDEX.md').read_text(encoding='utf-8')
        self.assertIn('| acme | Test | Bold and plain. |', index)
        self.assertIn(sha, index)
        self.assertTrue(list(design.glob('LICENSE-upstream-*.txt')))
        again = self.run_installer('-SkipPlugins', manifest=path)
        self.assertIn('already at the pinned commit', again.stdout)

    def test_unknown_commit_is_reported_not_silently_ignored(self):
        source = self.tmp / 'upstream2'
        source.mkdir()
        git = ['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com']
        subprocess.run(git + ['init', '-q'], cwd=source, check=True)
        (source / 'f.txt').write_text('x', encoding='utf-8')
        subprocess.run(git + ['add', '-A'], cwd=source, check=True)
        subprocess.run(git + ['commit', '-q', '-m', 'fixture'], cwd=source, check=True)
        manifest = dict(self.manifest)
        bad = {'repo': str(source), 'sha': '0' * 40, 'path': 'design-systems', 'license': 'Apache-2.0', 'target': 'ccpm'}
        manifest['extras'] = {'ccpm': dict(bad, path='skill/ccpm'), 'designSystems': bad}
        path = self.tmp / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        r = self.run_installer('-SkipPlugins', manifest=path)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('PROBLEM', r.stdout)


if __name__ == '__main__':
    unittest.main()
