import importlib.util
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'team'
spec = importlib.util.spec_from_file_location('personal_team', SOURCE / 'team.py')
team = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team)
buildspec = importlib.util.spec_from_file_location('personal_build', SOURCE / 'build_setup.py')
build = importlib.util.module_from_spec(buildspec)
buildspec.loader.exec_module(build)


class LocalGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai-setup-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.root.mkdir()
        self.oldcwd = Path.cwd()
        self.addCleanup(os.chdir, self.oldcwd)
        os.chdir(self.root)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Local Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'app.txt').write_text('baseline\n')
        self.git('add', 'app.txt')
        self.git('commit', '-m', 'docs(setup): baseline')
        self.remote = self.base / 'remote.git'
        subprocess.run(['git', 'clone', '--bare', str(self.root), str(self.remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('switch', '-c', 'feat/test')

    def git(self, *args):
        return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()

    def approve(self, authority):
        report = self.base / (authority + '.json')
        report.write_text(json.dumps({'authority':authority,'sha':self.git('rev-parse','HEAD'),'verdict':'pass','checks':[{'name':'local fixture','status':'pass','evidence':'isolated behavior verified'}]}))
        args = type('Args', (), {'authority': authority, 'report': str(report)})()
        team.gate_record(args)
        return report

    def test_requires_both_reviewers(self):
        with self.assertRaisesRegex(ValueError, 'validator'): team.gate_check()
        self.approve('validator')
        with self.assertRaisesRegex(ValueError, 'chief'): team.gate_check()

    def test_new_commit_invalidates_approval(self):
        self.approve('validator'); self.approve('chief')
        (self.root / 'app.txt').write_text('new behavior\n')
        self.git('add', 'app.txt'); self.git('commit', '-m', 'feat(test): new behavior')
        with self.assertRaisesRegex(ValueError, 'Missing'): team.gate_check()

    def test_modified_evidence_invalidates_approval(self):
        report = self.approve('validator'); self.approve('chief')
        report.write_text(report.read_text() + 'Altered after review\n')
        with self.assertRaisesRegex(ValueError, 'changed'): team.gate_check()

    def test_fail_verdict_rejected(self):
        report=self.base/'failed.json'
        report.write_text(json.dumps({'authority':'validator','sha':self.git('rev-parse','HEAD'),'verdict':'fail','checks':[]}))
        args=type('Args',(),{'authority':'validator','report':str(report)})()
        with self.assertRaisesRegex(ValueError,'pass verdict'):team.gate_record(args)

    def test_missing_check_evidence_rejected(self):
        report=self.base/'empty-check.json'
        report.write_text(json.dumps({'authority':'validator','sha':self.git('rev-parse','HEAD'),'verdict':'pass','checks':[{'name':'test','status':'pass'}]}))
        args=type('Args',(),{'authority':'validator','report':str(report)})()
        with self.assertRaisesRegex(ValueError,'name/evidence'):team.gate_record(args)

    def test_legacy_fail_approval_is_rejected_on_check(self):
        sha=self.git('rev-parse','HEAD')
        report=self.base/'legacy.md';report.write_text('FAIL '+sha)
        path=team.gate_directory()/sha/'validator.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'authority':'validator','sha':sha,'branch':'feat/test','report':str(report),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest()}))
        with self.assertRaisesRegex(ValueError,'structured JSON'):team.gate_check()

    def test_distinct_pushurl_rejected(self):
        self.approve('validator');self.approve('chief')
        other=self.base/'other.git'
        subprocess.run(['git','clone','--bare',str(self.root),str(other)],check=True,capture_output=True)
        self.git('config','remote.origin.pushurl',str(other))
        args=type('Args',(),{'action':'push','remote':'origin'})()
        with self.assertRaisesRegex(ValueError,'fetch/push'):team.gate(args)

    def test_remote_name_indirection_rejected(self):
        self.approve('validator');self.approve('chief')
        self.git('remote','add','alias',str(self.remote))
        self.git('remote','set-url','origin','alias')
        args=type('Args',(),{'action':'push','remote':'origin'})()
        with self.assertRaisesRegex(ValueError,'another configured remote'):team.gate(args)

    def test_url_rewrite_rejected(self):
        self.approve('validator');self.approve('chief')
        self.git('config','url.file:///unused/.insteadOf','fake:')
        args=type('Args',(),{'action':'push','remote':'origin'})()
        with self.assertRaisesRegex(ValueError,'URL rewrites'):team.gate(args)

    def test_dirty_tree_blocks_gate(self):
        self.approve('validator'); self.approve('chief')
        (self.root / 'app.txt').write_text('unreviewed edit\n')
        with self.assertRaisesRegex(ValueError, 'outstanding'): team.gate_check()

    def test_primary_branch_blocked(self):
        self.git('switch', 'main')
        with self.assertRaisesRegex(ValueError, 'main/master'): team.gate_check()

    def test_remote_default_branch_blocked(self):
        self.approve('validator'); self.approve('chief')
        self.git('push', 'origin', 'HEAD:refs/heads/feat/test')
        subprocess.run(['git','--git-dir',str(self.remote),'symbolic-ref','HEAD','refs/heads/feat/test'],check=True)
        args = type('Args', (), {'action': 'push', 'remote': 'origin'})()
        with self.assertRaisesRegex(ValueError, 'remote default'): team.gate(args)

    def test_approved_object_pushed_to_topic(self):
        self.approve('validator'); self.approve('chief')
        sha = self.git('rev-parse', 'HEAD')
        args = type('Args', (), {'action': 'push', 'remote': 'origin'})()
        team.gate(args)
        remote_sha = subprocess.run(['git','--git-dir',str(self.remote),'rev-parse','refs/heads/feat/test'],check=True,capture_output=True,text=True).stdout.strip()
        self.assertEqual(sha, remote_sha)

    def test_worktree_isolates_writer(self):
        args = type('Args', (), {'role':'backend','task':'reporting','kind':'feat','base':'HEAD'})()
        team.worktree(args)
        writer = self.base / 'project-worktrees' / 'reporting-backend'
        self.assertTrue((writer / 'app.txt').exists())
        (writer / 'app.txt').write_text('worker change\n')
        self.assertEqual((self.root / 'app.txt').read_text(), 'baseline\n')
        self.assertEqual(team.git('branch','--show-current',cwd=writer),'feat/reporting-backend')
        with self.assertRaisesRegex(ValueError, 'already exists'): team.worktree(args)


BOOTSTRAP = 'You are {{PROVIDER}} Chief on {{CHIEF_MODEL}}; validator {{VALIDATOR_MODEL}}; workers {{WORKER_MODEL}} at {{EFFORT}}. Initialize a pane team. {{OTHER}}'


def fixture_root(tmp):
    """Temp team ROOT with real models.json/roles and fixture bootstrap prompts."""
    root = Path(tmp) / 'team'
    root.mkdir()
    (root / 'models.json').write_text((SOURCE / 'models.json').read_text())
    (root / 'roles').mkdir()
    for path in (SOURCE / 'roles').glob('*.md'):
        (root / 'roles' / path.name).write_text(path.read_text())
    for provider in ('claude', 'codex'):
        (root / f'bootstrap-{provider}.txt').write_text(BOOTSTRAP)
    return root


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ai-setup-launch-')
        self.addCleanup(self.tmp.cleanup)
        self.root = fixture_root(self.tmp.name)

    def test_chief_command_and_literal_prompt(self):
        with patch.dict(os.environ,{'AGENT_TEAM_YOLO':'1'}), patch.object(team,'ROOT',self.root), patch.object(team,'executable',return_value='/vendor/codex'):
            cmd=team.command('codex','chief',['app with spaces; $(touch nope)'])
        self.assertEqual(cmd[0],'/vendor/codex')
        self.assertIn('gpt-6.1-sol',cmd)
        self.assertIn('--dangerously-bypass-approvals-and-sandbox',cmd)
        self.assertIn('Initialize a pane team',cmd[-1])
        self.assertIn('$(touch nope)',cmd[-1])
        self.assertFalse(Path('nope').exists())

    def test_bypass_flags_are_opt_in_and_switchable_off(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-yolo-') as tmp:
            home=Path(tmp)
            env={k:v for k,v in os.environ.items() if k not in ('AGENT_TEAM_YOLO','AGENT_TEAM_NO_BYPASS')}
            with patch.dict(os.environ,env,clear=True),patch.object(Path,'home',return_value=home),patch.object(team,'ROOT',self.root),patch.object(team,'executable',return_value='/vendor/claude'):
                self.assertNotIn('--dangerously-skip-permissions',team.command('claude','backend',[],prompt='p'))
                (home/'.agent-team').mkdir();(home/'.agent-team/yolo').write_text('on\n')
                self.assertIn('--dangerously-skip-permissions',team.command('claude','backend',[],prompt='p'))
                with patch.dict(os.environ,{'AGENT_TEAM_NO_BYPASS':'1'}):
                    self.assertNotIn('--dangerously-skip-permissions',team.command('claude','backend',[],prompt='p'))

    def test_worker_uses_lower_model(self):
        with patch.object(team,'ROOT',self.root), patch.object(team,'executable',return_value='/vendor/codex'):
            cmd=team.command('codex','backend',[])
        self.assertIn('gpt-6-luna',cmd)
        self.assertNotIn('gpt-6.1-sol',cmd)

    def test_claude_senior_model(self):
        with patch.object(team,'ROOT',self.root), patch.object(team,'executable',return_value='/vendor/claude'):
            cmd=team.command('claude','validator',[])
        self.assertIn('claude-opus-5-5',cmd)
        self.assertIn('--agent',cmd)
        self.assertIn('--effort',cmd)

    def test_native_wsl_vendor_selected_with_no_nvm_path(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-runtime-') as tmp:
            home=Path(tmp);bindir=home/'.nvm/versions/node/v24.0.0/bin';bindir.mkdir(parents=True)
            for name in ['node','codex']:
                path=bindir/name;path.write_text('#!/bin/sh\n');path.chmod(0o755)
            with patch.object(Path,'home',return_value=home),patch.dict(os.environ,{'PATH':'/usr/bin:/mnt/c/npm'}):
                path=team.executable('codex')
                self.assertEqual(path,str(bindir/'codex'))
                self.assertIn(str(bindir),os.environ['PATH'])

    def test_bad_worktree_name_rejected(self):
        for value in ['../outside','test;touch-nope','Bad-Name','-branch','two words']:
            with self.assertRaises(ValueError):team.validate_name(value)


FAKE_TMUX = """#!{python}
import json, os, sys
d = os.environ['FAKE_TMUX_DIR']
args = sys.argv[1:]
with open(d + '/log.jsonl', 'a') as f:
    f.write(json.dumps(args) + '\\n')
rules = json.load(open(d + '/rules.json'))
cpath = d + '/counts.json'
counts = json.load(open(cpath)) if os.path.exists(cpath) else {{}}
for rule in rules:
    i = rule['id']
    m = rule['match']
    if args and args[0] == m[0] and all(x in args for x in m[1:]):
        outs = rule.get('outputs') or [{{}}]
        n = counts.get(str(i), 0)
        counts[str(i)] = n + 1
        json.dump(counts, open(cpath, 'w'))
        o = outs[min(n, len(outs) - 1)]
        sys.stdout.write(o.get('stdout', ''))
        sys.stderr.write(o.get('stderr', ''))
        sys.exit(o.get('rc', 0))
sys.exit(0)
"""

DIALOG_NO = "Do you trust the files in this folder?\n  1. Yes, I trust this folder\n❯ 2. No, exit\n"
DIALOG_YES = "Do you trust the files in this folder?\n❯ 1. Yes, I trust this folder\n  2. No, exit\n"
READY = "? for shortcuts\n"
IDLE_CLAUDE = "─────\n❯\xa0\n─────\n  ⏵⏵ bypass permissions on\n"


class PaneTeamBase(unittest.TestCase):
    """Runs team.* against a fake tmux on PATH with a temp HOME/ROOT/state."""
    provider = 'claude'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ai-setup-panes-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.root = fixture_root(self.base)
        self.fake = self.base / 'fake'
        self.fake.mkdir()
        tmux = self.fake / 'tmux'
        tmux.write_text(FAKE_TMUX.format(python=sys.executable))
        tmux.chmod(0o755)
        self.state = self.base / 'state' / 'sess'
        self.workdir = self.base / 'work'
        self.workdir.mkdir()
        self.rules = []
        env = {'PATH': f'{self.fake}{os.pathsep}/usr/bin{os.pathsep}/bin', 'FAKE_TMUX_DIR': str(self.fake),
               'TMUX': '/tmp/fake,1,0', 'TMUX_PANE': '%1', 'AGENT_TEAM_SESSION': 'sess', 'AGENT_TEAM_STATE': str(self.state),
               'AGENT_TEAM_CHIEF_PANE': '%1', 'AGENT_TEAM_ROLE': 'chief', 'AGENT_TEAM_PROVIDER': self.provider}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for patcher in (patch.object(team, 'ROOT', self.root), patch.object(Path, 'home', return_value=self.home),
                        patch.object(team, 'executable', return_value='/vendor/' + self.provider),
                        patch.object(team, '_sleep', lambda s: setattr(self, 'clock', self.clock + s)),
                        patch.object(team, '_clock', lambda: self.clock)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.clock = 0.0
        self.rule('show-options', stdout=self.provider + '\n')
        self.rule('display-message', '#{window_id}', stdout='@1\n')
        self.rule('display-message', '#{session_name}', stdout='sess\n')
        self.rule('list-panes', '-a', stdout='%1\n')
        self.rule('list-panes', '-t', stdout='%1\n')
        self.rule('split-window', stdout='%2\n')
        self.rule('capture-pane', stdout=READY)

    def rule(self, *match, stdout='', stderr='', rc=0, outputs=None):
        """Earlier rules win, so call more specific rules before the defaults in setUp."""
        self.rules.append({'id': self.next_id(), 'match': list(match), 'outputs': outputs or [{'stdout': stdout, 'stderr': stderr, 'rc': rc}]})
        self.flush()

    def next_id(self):
        self.rule_ids = getattr(self, 'rule_ids', 0) + 1
        return self.rule_ids

    def priority(self, *match, **kw):
        outputs = kw.pop('outputs', None) or [{'stdout': kw.get('stdout', ''), 'stderr': kw.get('stderr', ''), 'rc': kw.get('rc', 0)}]
        self.rules.insert(0, {'id': self.next_id(), 'match': list(match), 'outputs': outputs})
        self.flush()

    def flush(self):
        (self.fake / 'rules.json').write_text(json.dumps(self.rules))

    def calls(self):
        path = self.fake / 'log.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def verbs(self):
        return [c[0] for c in self.calls()]

    def spawn(self, role='backend', task=None, provider=None, directory=None, prompt=()):
        args = type('Args', (), {'role': role, 'task': task, 'directory': str(directory or self.workdir), 'provider': provider, 'prompt': list(prompt)})()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            team.spawn(args)
        return json.loads(out.getvalue())

    def registry(self):
        return json.loads((self.state / 'panes.json').read_text())


class SpawnTests(PaneTeamBase):
    def test_spawn_splits_then_titles_then_tiles_and_prints_json(self):
        result = self.spawn('backend', 'api')
        verbs = self.verbs()
        self.assertLess(verbs.index('split-window'), verbs.index('select-pane'))
        tiled = [i for i, c in enumerate(self.calls()) if c[0] == 'select-layout' and 'tiled' in c]
        self.assertTrue(tiled and verbs.index('select-pane') < tiled[0])
        split = next(c for c in self.calls() if c[0] == 'split-window')
        self.assertIn('-d', split)
        self.assertEqual(split[split.index('-t') + 1], '@1')
        self.assertEqual(split[split.index('-c') + 1], str(self.workdir))
        title = next(c for c in self.calls() if c[0] == 'select-pane')
        self.assertEqual(title[title.index('-T') + 1], 'backend:api')
        self.assertIn(['set-option', '-w', '-t', '@1', 'pane-border-status', 'top'], self.calls())
        self.assertEqual((result['pane'], result['window'], result['role'], result['task'], result['provider']), ('%2', '@1', 'backend', 'api', 'claude'))
        self.assertEqual(result['model'], 'claude-sonnet-5-5')
        self.assertFalse(result['awaiting_trust'])

    def test_pane_title_is_protected_from_agent_rewrites_before_it_is_set(self):
        self.spawn('data', 'probe')
        calls = self.calls()
        off = ['set-option', '-p', '-t', '%2', 'allow-set-title', 'off']
        self.assertIn(off, calls)
        verbs = self.verbs()
        self.assertLess(verbs.index('split-window'), calls.index(off))
        self.assertLess(calls.index(off), verbs.index('select-pane'))

    def test_pane_command_has_env_cwd_and_worker_prompt_without_shell_expansion(self):
        self.spawn('backend', 'api', prompt=['do $(touch nope); x'])
        shell = next(c for c in self.calls() if c[0] == 'split-window')[-1]
        for expected in ('AGENT_TEAM_PROVIDER=claude', 'AGENT_TEAM_SESSION=sess', 'AGENT_TEAM_ROLE=backend', f'AGENT_TEAM_STATE={self.state}', 'AGENT_TEAM_CHIEF_PANE=%1', '--agent backend', '--model claude-sonnet-5-5', '--effort high'):
            self.assertIn(expected, shell)
        words = __import__('shlex').split(shell)
        prompt = words[-1]
        self.assertIn('use only claude agents', prompt)
        self.assertIn(f'assigned directory is {self.workdir}', prompt)
        self.assertIn('Verify `pwd` equals your assigned directory before any edit', prompt)
        self.assertIn('Chief pane: %1', prompt)
        self.assertIn('agent-team send chief', prompt)
        self.assertIn('agent-team inbox', prompt)
        self.assertIn('do $(touch nope); x', prompt)

    def test_worker_prompt_carries_single_contact_no_loops_one_increment_rules(self):
        self.spawn('backend', 'api')
        prompt = __import__('shlex').split(next(c for c in self.calls() if c[0] == 'split-window')[-1])[-1]
        self.assertIn('Chief is the only agent that talks to the user', prompt)
        self.assertIn('send questions and blockers to Chief with agent-team send chief', prompt)
        self.assertIn('do not start autonomous loops', prompt)
        self.assertIn('stop after your assigned increment and report', prompt)

    def test_worker_prompt_requires_startup_acknowledgement_to_chief(self):
        self.spawn('validator')
        prompt = __import__('shlex').split(next(c for c in self.calls() if c[0] == 'split-window')[-1])[-1]
        self.assertIn('On startup, before any other work, acknowledge Chief', prompt)
        self.assertIn('agent-team send chief --from validator "ACK validator: model claude-opus-5-5, effort high, pwd $(pwd)"', prompt)

    def test_validator_uses_senior_model(self):
        self.assertEqual(self.spawn('validator')['model'], 'claude-opus-5-5')

    def test_outside_tmux_is_an_error_and_touches_nothing(self):
        with patch.dict(os.environ):
            os.environ.pop('TMUX')
            with self.assertRaisesRegex(ValueError, r'\$TMUX is unset'):
                self.spawn('backend')
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.state / 'panes.json').exists())

    def test_no_recorded_provider_is_refused(self):
        self.priority('show-options', stdout='')
        with self.assertRaisesRegex(ValueError, 'No team provider recorded'):
            self.spawn('backend')
        self.assertNotIn('split-window', self.verbs())

    def test_cross_provider_refused_before_any_pane(self):
        with self.assertRaisesRegex(ValueError, 'provider-exclusive'):
            self.spawn('backend', provider='codex')
        self.assertNotIn('split-window', self.verbs())

    def test_matching_provider_flag_accepted(self):
        self.assertEqual(self.spawn('backend', provider='claude')['provider'], 'claude')

    def test_chief_and_unknown_roles_refused(self):
        with self.assertRaisesRegex(ValueError, 'cannot be spawned'):
            self.spawn('chief')
        with self.assertRaisesRegex(ValueError, 'Unknown role'):
            self.spawn('wizard')
        with self.assertRaises(ValueError):
            self.spawn('backend', task='Bad Task')
        self.assertNotIn('split-window', self.verbs())

    def test_duplicate_live_role_task_refused_but_dead_pane_replaced(self):
        self.spawn('backend', 'api')
        self.priority('list-panes', '-a', stdout='%1\n%2\n')
        with self.assertRaisesRegex(ValueError, 'already has a live pane'):
            self.spawn('backend', 'api')
        self.spawn('backend', 'other')  # different task is fine
        # %2 dies; a re-spawn is allowed and replaces the stale registry row.
        self.priority('list-panes', '-a', stdout='%1\n')
        self.priority('split-window', stdout='%9\n')
        self.spawn('backend', 'api')
        rows = [(e['role'], e['task'], e['pane']) for e in self.registry()]
        self.assertIn(('backend', 'api', '%9'), rows)
        self.assertNotIn(('backend', 'api', '%2'), rows)

    def test_overflow_opens_new_numbered_window_when_chief_window_full(self):
        self.priority('list-panes', '-t', '@1', stdout='%1\n%2\n%3\n%4\n%5\n%6\n')
        self.rule('list-windows', stdout='@1 chief\n')
        self.rule('new-window', stdout='%7 @2\n')
        result = self.spawn('qa', 'sweep')
        self.assertNotIn('split-window', self.verbs())
        new = next(c for c in self.calls() if c[0] == 'new-window')
        self.assertEqual((new[new.index('-n') + 1], new[new.index('-c') + 1]), ('team-1', str(self.workdir)))
        self.assertEqual((result['pane'], result['window']), ('%7', '@2'))
        self.assertIn(['select-layout', '-t', '@2', 'tiled'], self.calls())
        self.assertEqual(self.registry()[0]['window'], '@2')

    def test_overflow_reuses_existing_team_window_with_room_and_honors_max_env(self):
        self.priority('list-panes', '-t', '@1', stdout='%1\n%2\n')
        self.priority('list-panes', '-t', '@2', stdout='%7\n')
        self.rule('list-windows', stdout='@1 chief\n@2 team-1\n')
        self.priority('split-window', '@2', stdout='%8\n')
        with patch.dict(os.environ, {'AGENT_TEAM_MAX_PANES': '2'}):
            result = self.spawn('qa')
        self.assertEqual((result['pane'], result['window']), ('%8', '@2'))
        self.assertNotIn('new-window', self.verbs())

    def test_no_space_error_falls_back_to_new_window(self):
        self.priority('split-window', rc=1, stderr='create pane failed: no space for new pane\n')
        self.rule('list-windows', stdout='@1 chief\n')
        self.rule('new-window', stdout='%5 @3\n')
        result = self.spawn('qa')
        self.assertEqual((result['pane'], result['window']), ('%5', '@3'))

    def test_other_split_failure_is_reported(self):
        self.priority('split-window', rc=1, stderr='boom\n')
        with self.assertRaisesRegex(ValueError, 'boom'):
            self.spawn('qa')
        self.assertNotIn('new-window', self.verbs())
        self.assertFalse((self.state / 'panes.json').exists())

    def test_retile_hooks_installed(self):
        self.spawn('backend')
        self.assertIn(['set-hook', '-w', '-t', '@1', 'pane-exited', 'select-layout tiled'], self.calls())
        self.assertIn(['set-hook', '-t', 'sess', 'after-kill-pane', 'select-layout tiled'], self.calls())

    def test_registry_written_atomically_with_contract_fields(self):
        self.spawn('backend', 'api')
        self.spawn('qa')
        rows = self.registry()
        self.assertEqual([r['role'] for r in rows], ['backend', 'qa'])
        self.assertEqual(set(rows[0]), {'role', 'task', 'pane', 'window', 'cwd', 'provider', 'model', 'started_at'})
        self.assertEqual((rows[0]['task'], rows[0]['cwd'], rows[0]['provider']), ('api', str(self.workdir), 'claude'))
        self.assertEqual(list(self.state.glob('*.tmp')), [])

    def test_panes_reports_live_and_dead(self):
        self.spawn('backend')
        self.priority('list-panes', '-a', stdout='%1\n%2\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            team.panes(None)
        self.assertEqual(json.loads(out.getvalue())[0]['status'], 'live')
        self.priority('list-panes', '-a', stdout='%1\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            team.panes(None)
        self.assertEqual(json.loads(out.getvalue())[0]['status'], 'dead')


class TrustTests(PaneTeamBase):
    def make_worktree(self, trusted):
        main = self.base / 'main-checkout'
        main.mkdir()
        for args in (['init', '-b', 'main'], ['config', 'user.name', 't'], ['config', 'user.email', 't@example.invalid'], ['commit', '--allow-empty', '-m', 'init'], ['worktree', 'add', '-b', 'feat/x', str(self.base / 'wt')]):
            subprocess.run(['git', *args], cwd=main, check=True, capture_output=True)
        self.config = self.home / '.claude.json'
        self.config.write_text(json.dumps({'projects': {str(main): {'hasTrustDialogAccepted': trusted}}}))
        self.config_before = (self.config.read_bytes(), self.config.stat().st_mtime_ns)
        return self.base / 'wt'

    def sent_keys(self):
        return [c[3:] for c in self.calls() if c[0] == 'send-keys']

    def test_trusted_worktree_prompt_is_accepted_after_verified_selection(self):
        wt = self.make_worktree(True)
        self.priority('capture-pane', outputs=[{'stdout': 'booting\n'}, {'stdout': DIALOG_NO}, {'stdout': DIALOG_NO}, {'stdout': DIALOG_YES}])
        result = self.spawn('backend', directory=wt)
        self.assertFalse(result['awaiting_trust'])
        self.assertEqual(self.sent_keys(), [['Up'], ['Enter']])
        self.assertEqual((self.config.read_bytes(), self.config.stat().st_mtime_ns), self.config_before)

    def test_already_selected_yes_gets_enter_only(self):
        wt = self.make_worktree(True)
        self.priority('capture-pane', stdout=DIALOG_YES)
        self.spawn('backend', directory=wt)
        self.assertEqual(self.sent_keys(), [['Enter']])

    def test_untrusted_main_checkout_reports_awaiting_trust_and_sends_nothing(self):
        wt = self.make_worktree(False)
        self.priority('capture-pane', stdout=DIALOG_NO)
        self.assertTrue(self.spawn('backend', directory=wt)['awaiting_trust'])
        self.assertEqual(self.sent_keys(), [])
        self.assertEqual((self.config.read_bytes(), self.config.stat().st_mtime_ns), self.config_before)

    def test_non_worktree_directory_is_never_auto_accepted(self):
        self.config = self.home / '.claude.json'
        self.config.write_text(json.dumps({'projects': {str(self.workdir): {'hasTrustDialogAccepted': True}}}))
        self.priority('capture-pane', stdout=DIALOG_NO)
        self.assertTrue(self.spawn('backend')['awaiting_trust'])
        self.assertEqual(self.sent_keys(), [])

    def test_unverifiable_selection_never_presses_enter(self):
        wt = self.make_worktree(True)
        self.priority('capture-pane', stdout=DIALOG_NO)  # selection never moves
        self.assertTrue(self.spawn('backend', directory=wt)['awaiting_trust'])
        self.assertNotIn(['Enter'], self.sent_keys())

    def test_prompt_wait_is_bounded_and_ends_early_when_ui_ready(self):
        self.priority('capture-pane', stdout='starting...\n')
        self.assertFalse(self.spawn('backend')['awaiting_trust'])
        self.assertGreaterEqual(self.clock, team.TRUST_WAIT)
        self.assertLess(self.clock, team.TRUST_WAIT + 1)
        self.clock = 0.0
        self.priority('capture-pane', stdout=READY)
        self.spawn('qa')
        self.assertEqual(self.clock, 0.0)


class MailboxTests(PaneTeamBase):
    def setUp(self):
        super().setUp()
        self.priority('list-panes', '-a', stdout='%1\n%2\n')
        self.spawn('backend', 'api')
        self.rule('capture-pane', stdout=IDLE_CLAUDE)
        self.priority('capture-pane', stdout=IDLE_CLAUDE)
        retry = patch.object(team, 'start_retry')
        self.retry = retry.start()
        self.addCleanup(retry.stop)

    def send(self, target, *message, sender='qa'):
        args = type('Args', (), {'target': target, 'sender': sender, 'message': list(message)})()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            team.send(args)
        return Path(out.getvalue().strip())

    def test_send_writes_mailbox_then_literal_notification_then_enter(self):
        before = len(self.calls())
        path = self.send('backend', 'please', 'review $(x)')
        self.assertEqual(path.parent, self.state / 'mailbox' / 'backend')
        self.assertTrue(path.name.endswith('-from-qa.md'))
        self.assertEqual(path.read_text(), 'please review $(x)\n')
        keys = [c for c in self.calls()[before:] if c[0] == 'send-keys']
        self.assertEqual(keys[0], ['send-keys', '-t', '%2', '-l', f'[from qa] read {path}'])
        self.assertEqual(keys[1], ['send-keys', '-t', '%2', 'Enter'])

    def test_chief_pane_gets_typed_notice_only_when_input_is_empty(self):
        before = len(self.calls())
        path = self.send('chief', 'done')
        new = self.calls()[before:]
        keys = [c for c in new if c[0] == 'send-keys']
        self.assertEqual([k[1:] for k in keys], [['-t', '%1', '-l', f'[from qa] read {path}'], ['-t', '%1', 'Enter']])
        self.assertEqual([c for c in new if c[0] == 'display-message' and '-d' in c], [])
        self.retry.assert_not_called()

    def test_chief_pane_with_user_typing_is_never_typed_into(self):
        self.priority('capture-pane', '%1', stdout='──\n❯\xa0half typed to the user\n──\n')
        before = len(self.calls())
        path = self.send('chief', 'done')
        new = self.calls()[before:]
        self.assertNotIn('send-keys', [c[0] for c in new])
        self.assertIn(['display-message', '-t', '%1', '-d', '8000', f'[agent-team] new message for chief: {path}'], new)
        self.assertTrue(path.exists())
        self.retry.assert_called_once_with('%1', f'[from qa] read {path}')

    def test_input_is_rechecked_immediately_before_typing(self):
        # Empty at the first look, user starts typing before the keys go out.
        self.priority('capture-pane', '%2', outputs=[{'stdout': '❯\xa0\n'}, {'stdout': '❯\xa0h\n'}])
        before = len(self.calls())
        path = self.send('backend', 'x')
        new = self.calls()[before:]
        self.assertNotIn('send-keys', [c[0] for c in new])
        self.assertIn('display-message', [c[0] for c in new])
        self.retry.assert_called_once_with('%2', f'[from qa] read {path}')

    def test_send_by_pane_id(self):
        self.assertEqual(self.send('%2', 'hi').parent.name, 'backend')

    def test_non_empty_input_is_not_typed_into_notice_shown_and_retry_started(self):
        for typed in ('❯\xa0half typed message', '❯ \x1b[0mhalf typed', '│ ❯\xa0ls -la │', '❯\xa0\x1b[7mx\x1b[27m'):
            self.priority('capture-pane', stdout='────\n' + typed + '\n────\n')
            before = len(self.calls())
            path = self.send('backend', 'review')
            new = self.calls()[before:]
            self.assertNotIn('send-keys', [c[0] for c in new], typed)
            self.assertIn(['display-message', '-t', '%2', '-d', '8000', f'[agent-team] new message for backend: {path}'], new)
            self.assertTrue(path.exists())
            self.retry.assert_called_with('%2', f'[from qa] read {path}')

    def test_pane_in_copy_mode_is_busy_never_typed_into(self):
        self.priority('display-message', '#{pane_in_mode}', stdout='1\n')
        before = len(self.calls())
        path = self.send('backend', 'x')
        new = self.calls()[before:]
        self.assertNotIn('send-keys', [c[0] for c in new])
        self.assertIn(['display-message', '-t', '%2', '-d', '8000', f'[agent-team] new message for backend: {path}'], new)
        self.retry.assert_called_once_with('%2', f'[from qa] read {path}')

    def test_send_keys_failure_falls_back_to_notice_and_retry_without_aborting(self):
        self.priority('send-keys', rc=1, stderr='no current client\n')
        before = len(self.calls())
        path = self.send('backend', 'x')
        new = self.calls()[before:]
        self.assertTrue(path.exists())
        self.assertNotIn(['send-keys', '-t', '%2', 'Enter'], new)
        self.assertIn(['display-message', '-t', '%2', '-d', '8000', f'[agent-team] new message for backend: {path}'], new)
        self.retry.assert_called_once_with('%2', f'[from qa] read {path}')

    def test_enter_failure_clears_the_partial_line_we_typed(self):
        self.priority('send-keys', 'Enter', rc=1)
        path = self.send('backend', 'x')
        self.assertIn(['send-keys', '-t', '%2', 'C-u'], self.calls())
        self.retry.assert_called_once()

    def test_undeterminable_input_is_treated_as_not_empty(self):
        self.priority('capture-pane', stdout='no prompt marker here\n')
        before = len(self.calls())
        self.send('backend', 'x')
        self.assertNotIn('send-keys', [c[0] for c in self.calls()[before:]])
        self.assertIn('display-message', [c[0] for c in self.calls()[before:]])

    def test_empty_and_placeholder_input_lines_allow_typing(self):
        for screen in (IDLE_CLAUDE, '❯\xa0\n', '❯\xa0\x1b[2mjust a dim placeholder\x1b[0m\n', '› \n', '│ ❯\xa0  │\n',
                       '❯ [from chief] read /old/history\n──\n❯\xa0\n──\n'):
            self.priority('capture-pane', stdout=screen)
            before = len(self.calls())
            path = self.send('backend', 'x')
            keys = [c for c in self.calls()[before:] if c[0] == 'send-keys']
            self.assertEqual(len(keys), 2, screen)
            self.assertEqual(keys[0][-2:], ['-l', f'[from qa] read {path}'])
            self.assertEqual(keys[1][-1], 'Enter')
        self.retry.assert_not_called()

    def test_background_retry_waits_until_input_empties_then_types_once(self):
        self.priority('capture-pane', outputs=[{'stdout': '❯\xa0typing\n'}, {'stdout': '❯\xa0typing more\n'}, {'stdout': '❯\xa0\n'}])
        before = len(self.calls())
        self.assertTrue(team.deliver_when_idle('%2', '[from qa] read /x'))
        keys = [c for c in self.calls()[before:] if c[0] == 'send-keys']
        self.assertEqual([k[3:] for k in keys], [['-l', '[from qa] read /x'], ['Enter']])
        self.assertEqual(self.clock, 4.0)

    def test_background_retry_gives_up_silently_after_timeout_without_typing(self):
        self.priority('capture-pane', stdout='❯\xa0still typing\n')
        before = len(self.calls())
        self.assertFalse(team.deliver_when_idle('%2', 'line', timeout=10, interval=2))
        self.assertNotIn('send-keys', [c[0] for c in self.calls()[before:]])
        self.assertGreaterEqual(self.clock, 10)

    def test_background_retry_stops_when_pane_is_gone(self):
        self.priority('capture-pane', rc=1, stderr="can't find pane\n")
        self.priority('display-message', '#{pane_id}', rc=1)
        self.assertFalse(team.deliver_when_idle('%2', 'line'))
        self.assertLess(self.clock, 1)

    def test_send_defaults_sender_to_env_role_and_reads_stdin(self):
        with patch.dict(os.environ, {'AGENT_TEAM_ROLE': 'platform'}), patch.object(sys, 'stdin', io.StringIO('multi\nline\n')):
            path = self.send('backend', '-', sender=None)
        self.assertTrue(path.name.endswith('-from-platform.md'))
        self.assertEqual(path.read_text(), 'multi\nline\n')

    def test_same_timestamp_never_overwrites(self):
        class Frozen(datetime_cls):
            @classmethod
            def now(cls, tz=None):
                return datetime_cls(2026, 1, 1, tzinfo=tz)
        with patch.object(team.datetime, 'datetime', Frozen):
            first, second = self.send('backend', 'a'), self.send('backend', 'b')
        self.assertNotEqual(first, second)
        self.assertEqual((first.read_text(), second.read_text()), ('a\n', 'b\n'))

    def test_send_rejects_bad_targets_and_senders_without_writing(self):
        for target, sender in (('nobody', 'qa'), ('%99', 'qa'), ('security', 'qa'), ('backend', '../evil')):
            with self.assertRaises(ValueError, msg=(target, sender)):
                self.send(target, 'x', sender=sender)
        self.assertEqual(list((self.state / 'mailbox').glob('*/*.md')), [])

    def test_inbox_prints_in_order_and_moves_to_read(self):
        first = self.send('backend', 'one')
        second = self.send('backend', 'two', sender='qa')
        out = io.StringIO()
        with patch.dict(os.environ, {'AGENT_TEAM_ROLE': 'backend'}), contextlib.redirect_stdout(out):
            team.inbox(type('Args', (), {'role': None})())
        text = out.getvalue()
        self.assertLess(text.index('one'), text.index('two'))
        self.assertFalse(first.exists() or second.exists())
        self.assertTrue((first.parent / 'read' / first.name).exists())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            team.inbox(type('Args', (), {'role': 'backend'})())
        self.assertIn('No unread', out.getvalue())


datetime_cls = __import__('datetime').datetime


class LaunchTests(PaneTeamBase):
    def setUp(self):
        super().setUp()
        patcher = patch.object(os, 'chdir')
        patcher.start()
        self.addCleanup(patcher.stop)

    def args(self, provider='claude', role='chief', **kw):
        values = {'provider': provider, 'role': role, 'directory': str(self.workdir), 'no_tmux': False, 'dry_run': False, 'prompt': []}
        values.update(kw)
        return type('Args', (), values)()

    def test_inside_tmux_records_provider_exports_env_and_execs_rendered_bootstrap(self):
        self.priority('show-options', stdout='')
        with patch.object(os, 'execv', side_effect=SystemExit) as execv, patch.dict(os.environ):
            with self.assertRaises(SystemExit):
                team.launch(self.args())
            env = dict(os.environ)
        self.assertIn(['set-option', '-t', 'sess', '@agent_team_provider', 'claude'], self.calls())
        self.assertEqual([env[k] for k in ('AGENT_TEAM_PROVIDER', 'AGENT_TEAM_SESSION', 'AGENT_TEAM_ROLE', 'AGENT_TEAM_CHIEF_PANE')], ['claude', 'sess', 'chief', '%1'])
        self.assertEqual(env['AGENT_TEAM_STATE'], str(self.state))
        prompt = execv.call_args[0][1][-1]
        self.assertIn('You are claude Chief on claude-opus-5-5; validator claude-opus-5-5; workers claude-sonnet-5-5 at high.', prompt)
        self.assertIn('{{OTHER}}', prompt)  # only the five contract tokens are templated
        self.assertTrue((self.state / 'mailbox' / 'chief').is_dir())

    def test_inside_tmux_protects_chief_pane_title(self):
        with patch.object(os, 'execv', side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                team.launch(self.args())
        self.assertIn(['set-option', '-p', '-t', '%1', 'allow-set-title', 'off'], self.calls())

    def test_inherited_state_and_chief_pane_from_another_session_are_ignored(self):
        with patch.dict(os.environ, {'AGENT_TEAM_SESSION': 'other', 'AGENT_TEAM_STATE': '/stale/state', 'AGENT_TEAM_CHIEF_PANE': '%99'}):
            with patch.object(os, 'execv', side_effect=SystemExit):
                with self.assertRaises(SystemExit):
                    team.launch(self.args(role='validator'))
            env = dict(os.environ)
        self.assertEqual((env['AGENT_TEAM_SESSION'], env['AGENT_TEAM_CHIEF_PANE']), ('sess', '%1'))
        self.assertEqual(env['AGENT_TEAM_STATE'], str(self.home / '.agent-team/state/sess'))
        self.assertTrue((self.home / '.agent-team/state/sess/mailbox/validator').is_dir())
        self.assertFalse(Path('/stale/state').exists())

    def test_inherited_values_from_the_same_session_are_reused(self):
        with patch.object(os, 'execv', side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                team.launch(self.args(role='validator'))
            self.assertEqual((os.environ['AGENT_TEAM_STATE'], os.environ['AGENT_TEAM_CHIEF_PANE']), (str(self.state), '%1'))

    def test_inside_tmux_matching_recorded_provider_is_not_rewritten(self):
        with patch.object(os, 'execv', side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                team.launch(self.args())
        self.assertNotIn(['set-option', '-t', 'sess', '@agent_team_provider', 'claude'], self.calls())

    def test_cross_provider_launch_into_existing_team_refused(self):
        with patch.object(os, 'execv') as execv, patch.object(team, 'executable', return_value='/vendor/codex'):
            with self.assertRaisesRegex(ValueError, 'provider-exclusive'):
                team.launch(self.args('codex'))
        execv.assert_not_called()

    def test_new_session_records_provider_and_wraps_env(self):
        with patch.dict(os.environ):
            os.environ.pop('TMUX')
            with patch.object(os, 'execvp') as execvp:
                team.launch(self.args())
        new = next(c for c in self.calls() if c[0] == 'new-session')
        name = new[new.index('-s') + 1]
        self.assertTrue(name.startswith('claude-team-work-'))
        shell = new[-1]
        self.assertIn(f'AGENT_TEAM_SESSION={name}', shell)
        self.assertIn('AGENT_TEAM_CHIEF_PANE="$TMUX_PANE"', shell)
        self.assertIn(f'AGENT_TEAM_STATE={self.home}/.agent-team/state/{name}', shell)
        self.assertIn(['set-option', '-t', name, '@agent_team_provider', 'claude'], self.calls())
        self.assertLess(self.verbs().index('new-session'), self.verbs().index('set-option'))
        self.assertIn(['set-option', '-p', '-t', name, 'allow-set-title', 'off'], self.calls())
        execvp.assert_called_once_with('tmux', ['tmux', 'attach-session', '-t', name])

    def test_dry_run_touches_neither_tmux_nor_state(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            team.launch(self.args(dry_run=True))
        self.assertEqual(json.loads(out.getvalue())['env']['AGENT_TEAM_PROVIDER'], 'claude')
        self.assertEqual(self.calls(), [])

    def test_missing_bootstrap_is_a_clear_error(self):
        (self.root / 'bootstrap-claude.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing Chief bootstrap prompt.*bootstrap-claude.txt'):
            team.launch(self.args(dry_run=True))


class BootstrapRenderTests(unittest.TestCase):
    def test_tokens_rendered_exactly_per_provider(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-render-') as tmp:
            root = fixture_root(tmp)
            with patch.object(team, 'ROOT', root):
                claude, codex = team.render_bootstrap('claude'), team.render_bootstrap('codex')
        self.assertIn('claude Chief on claude-opus-5-5', claude)
        self.assertIn('codex Chief on gpt-6.1-sol; validator gpt-6.1-sol; workers gpt-6-luna at high', codex)
        self.assertNotIn('{{PROVIDER}}', claude + codex)

    def test_real_bootstrap_files_have_no_cross_provider_names(self):
        banned = {'claude': r'\b(codex|gpt|luna|sol)\b', 'codex': r'\b(claude|opus|sonnet|anthropic)\b'}
        checked = 0
        for provider, pattern in banned.items():
            if not (SOURCE / f'bootstrap-{provider}.txt').is_file():
                continue
            checked += 1
            with patch.object(team, 'ROOT', SOURCE):
                text = team.render_bootstrap(provider)
            self.assertNotRegex(text, __import__('re').compile(pattern, __import__('re').I), provider)
            self.assertNotRegex(text, r'\{\{(PROVIDER|CHIEF_MODEL|VALIDATOR_MODEL|WORKER_MODEL|EFFORT)\}\}')
        if not checked:
            self.skipTest('team/bootstrap-claude.txt and team/bootstrap-codex.txt are not present yet (architect owns them)')


class SyncTests(unittest.TestCase):
    def test_malformed_agent_rejected_before_any_sync_writes(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sync-') as tmp:
            base=Path(tmp);linux=base/'linux';windows=base/'windows';source=linux/'.agent-team'
            source.mkdir(parents=True);(source/'UNIVERSAL.md').write_text('new rules')
            native=windows/'.claude/agents/backend.md';native.parent.mkdir(parents=True);native.write_text('Missing frontmatter')
            rules=windows/'.claude/CLAUDE.md';rules.write_text('existing rules')
            with patch.object(team,'ROOT',source),patch.object(team,'WINDOWS',windows),patch.object(Path,'home',return_value=linux):
                with self.assertRaisesRegex(ValueError,'frontmatter'):team.sync(None)
                self.assertEqual(rules.read_text(),'existing rules')
                self.assertFalse((windows/'.agent-team').exists())

    def test_sync_copies_both_provider_bootstrap_prompts(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sync-') as tmp:
            base=Path(tmp);linux=base/'linux';windows=base/'windows';source=linux/'.agent-team'
            source.mkdir(parents=True);(source/'UNIVERSAL.md').write_text('rules')
            (source/'skills').mkdir();(source/'roles').mkdir()
            for role in team.ROLES:(source/f'roles/{role}.md').write_text(f'# {role}\n')
            for provider in ('claude','codex'):(source/f'bootstrap-{provider}.txt').write_text(provider+' prompt')
            (source/'bootstrap.txt').write_text('legacy')
            with patch.object(team,'ROOT',source),patch.object(team,'WINDOWS',windows),patch.object(Path,'home',return_value=linux),contextlib.redirect_stdout(io.StringIO()):
                team.sync(None)
            self.assertEqual((windows/'.agent-team/bootstrap-claude.txt').read_text(),'claude prompt')
            self.assertEqual((windows/'.agent-team/bootstrap-codex.txt').read_text(),'codex prompt')
            self.assertFalse((windows/'.agent-team/bootstrap.txt').exists())

    def test_sync_preserves_replaced_windows_files_in_backup(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sync-') as tmp:
            base=Path(tmp);linux=base/'linux';windows=base/'windows';source=linux/'.agent-team'
            source.mkdir(parents=True)
            (source/'UNIVERSAL.md').write_text('updated shared rules\n')
            (source/'skills').mkdir()
            (source/'roles').mkdir()
            for role in team.ROLES:(source/f'roles/{role}.md').write_text(f'# Updated {role}\n')
            native=windows/'.codex/agents/backend.toml';native.parent.mkdir(parents=True)
            native.write_text('name = "backend"\ndeveloper_instructions = "LOCALLY_EDITED_SENTINEL"\n')
            with patch.object(team,'ROOT',source),patch.object(team,'WINDOWS',windows),patch.object(Path,'home',return_value=linux):
                team.sync(None)
                self.assertNotIn('LOCALLY_EDITED_SENTINEL',native.read_text())
                backups=list((source/'backups').rglob('backend.toml'))
                self.assertEqual(len(backups),1)
                self.assertIn('LOCALLY_EDITED_SENTINEL',backups[0].read_text())
                self.assertEqual((source/'backups').stat().st_mode & 0o777,0o700)
                team.sync(None)
                self.assertEqual(len(list((source/'backups').rglob('backend.toml'))),1)


class LauncherInstallTests(unittest.TestCase):
    def test_installer_does_not_export_experimental_native_agent_teams(self):
        self.assertNotIn('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS', (SOURCE / 'install_launchers.py').read_text())


class InstallerTests(unittest.TestCase):
    def test_reinstall_preserves_learned_skills_roles_and_rules(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-install-') as tmp:
            base=Path(tmp);linux=base/'linux';windows=base/'windows';source=linux/'.agent-team'
            ccpm=linux/'ccpm/skill/ccpm';ccpm.mkdir(parents=True);(ccpm/'SKILL.md').write_text('fixture CCPM')
            with patch.dict(os.environ,{'AGENT_TEAM_PROVIDERS':'claude,codex'}),patch.object(build,'ROOT',source),patch.object(build,'LINUX',linux),patch.object(build,'WINDOWS',windows),patch.object(build,'BACKUP',source/'backups/test'),contextlib.redirect_stdout(io.StringIO()):
                build.apply()
                skill=source/'skills/team-chief-project-plan/SKILL.md';role=source/'roles/chief.md';rules=source/'UNIVERSAL.md'
                for path in [skill,role,rules]:path.write_text(path.read_text()+'\nLEARNED_USER_PREFERENCE\n')
                original={p:p.read_text() for p in [skill,role,rules]}
                build.apply()
                for path,text in original.items():self.assertEqual(path.read_text(),text)
                self.assertIn('LEARNED_USER_PREFERENCE',(windows/'.agents/skills/team-chief-project-plan/SKILL.md').read_text())
                self.assertIn('LEARNED_USER_PREFERENCE',(windows/'.claude/agents/chief.md').read_text())
                self.assertIn('LEARNED_USER_PREFERENCE',(windows/'.codex/AGENTS.md').read_text())


REPO = SOURCE.parent


def run_py(script, *args, home, **env):
    """Run one of the installer scripts black-box in a throwaway HOME (never the real one)."""
    full = {**os.environ, 'HOME': str(home), 'AGENT_TEAM_WINDOWS_HOME': 'none', 'AGENT_TEAM_PROVIDERS': 'claude,codex',
            'AGENT_TEAM_CCPM_REPO': str(home / 'no-such-ccpm'), 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin', **env}
    return subprocess.run([sys.executable, str(script), *args], env=full, capture_output=True, text=True, cwd=str(home))


def tree(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() and not p.is_symlink() else str(p.is_symlink()))
            for p in sorted(Path(root).rglob('*')) if 'backups' not in p.parts}


class PortabilityTests(unittest.TestCase):
    def test_owned_files_embed_no_personal_data(self):
        user = 'egood' + 'man'
        files = [*SOURCE.glob('*.py'), *SOURCE.glob('*.ps1'), SOURCE / 'cli-shim', REPO / 'install.sh', REPO / 'install.ps1', Path(__file__)]
        pattern = __import__('re').compile(user + r'|/home/[a-z][a-z0-9_-]+/|/Users/[a-z][a-z0-9_-]+/|Users\\\\[a-z][a-z0-9_-]+\\\\', __import__('re').I)
        for path in files:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertIsNone(pattern.search(line), f'{path.name}:{number}: {line.strip()[:80]}')

    def test_old_split_windows_installers_are_consolidated(self):
        self.assertTrue((REPO / 'install.ps1').is_file())
        self.assertEqual(sorted(p.name for p in SOURCE.glob('install-*.ps1')), [])

    def test_python_sources_parse_as_python_39(self):
        for path in [*SOURCE.glob('*.py'), SOURCE / 'cli-shim']:
            __import__('ast').parse(path.read_text(), feature_version=(3, 9))

    def test_crlf_files_compare_by_bytes_and_are_not_rewritten(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-crlf-') as tmp:
            build.reset()
            with patch.object(build, 'BACKUP', Path(tmp) / 'backups/x'):
                path = Path(tmp) / 'a.cmd'
                self.assertTrue(build.write_bytes(path, b'@echo off\r\n'))
                self.assertFalse(build.write_bytes(path, b'@echo off\r\n'))
                self.assertFalse((Path(tmp) / 'backups').exists())
            build.reset()


class InstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ai-setup-flow-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.home.mkdir()

    def install(self, *extra, **env):
        return run_py(SOURCE / 'build_setup.py', '--package-from', str(SOURCE), *extra, home=self.home, **env)

    def test_dry_run_prints_changes_and_writes_nothing(self):
        result = self.install('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('would create', result.stdout)
        self.assertEqual(list(self.home.rglob('*')), [])

    def test_second_install_changes_nothing_and_adds_no_backup(self):
        self.assertEqual(self.install().returncode, 0)
        before = tree(self.home)
        backups = sorted(p.name for p in (self.home / '.agent-team/backups').iterdir())
        again = self.install()
        self.assertIn('No changes needed', again.stdout)
        self.assertEqual(before, tree(self.home))
        self.assertEqual(backups, sorted(p.name for p in (self.home / '.agent-team/backups').iterdir()))

    def test_existing_settings_are_merged_backed_up_and_restorable(self):
        settings = self.home / '.claude/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text('{"theme": "dark"}\n')
        first = self.install(AGENT_TEAM_BACKUP_STAMP='20260101T000000Z')
        self.assertEqual(first.returncode, 0, first.stderr)
        merged = json.loads(settings.read_text())
        self.assertEqual(merged['theme'], 'dark')
        self.assertNotIn('permissions', merged, 'bypass defaults are opt-in')
        saved = list((self.home / '.agent-team/backups/20260101T000000Z').rglob('settings.json'))
        self.assertEqual([p.read_text() for p in saved], ['{"theme": "dark"}\n'])
        restored = run_py(SOURCE / 'build_setup.py', '--restore', '20260101T000000Z', home=self.home)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(settings.read_text(), '{"theme": "dark"}\n')
        self.assertFalse((self.home / '.claude/agents/chief.md').exists(), 'files the install created are removed again')

    def test_yolo_is_opt_in_and_sticky_and_existing_bypass_is_kept(self):
        self.install()
        self.assertFalse((self.home / '.agent-team/yolo').exists())
        self.assertNotIn('bypassPermissions', (self.home / '.claude/settings.json').read_text())
        self.assertNotIn('bypassPermissions', (self.home / '.claude/agents/backend.md').read_text())
        self.assertNotIn('danger-full-access', (self.home / '.codex/config.toml').read_text())
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home)
        self.assertFalse((self.home / '.local/bin/codex').exists(), 'no flag-injecting shim without --yolo')
        self.assertNotIn('claude()', (self.home / '.agent-team/shell.sh').read_text())
        self.assertTrue(self.install('--yolo').returncode == 0)
        self.assertTrue((self.home / '.agent-team/yolo').is_file())
        self.assertEqual(json.loads((self.home / '.claude/settings.json').read_text())['permissions']['defaultMode'], 'bypassPermissions')
        self.assertIn('bypassPermissions', (self.home / '.claude/agents/backend.md').read_text())
        self.assertIn('danger-full-access', (self.home / '.codex/config.toml').read_text())
        # a later plain run keeps what is already there
        self.assertEqual(self.install().returncode, 0)
        self.assertIn('bypassPermissions', (self.home / '.claude/settings.json').read_text())
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home)
        self.assertIn('claude()', (self.home / '.agent-team/shell.sh').read_text())
        self.assertTrue((self.home / '.local/bin/codex').is_symlink())

    def test_existing_bypass_is_never_inferred_into_yolo(self):
        settings = self.home / '.claude/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text('{"permissions": {"defaultMode": "bypassPermissions"}}\n')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / '.agent-team/yolo').exists(), 'the marker is written only by --yolo')
        self.assertNotIn('danger-full-access', (self.home / '.codex/config.toml').read_text(), 'Claude bypass must not enable Codex bypass')
        self.assertNotIn('approval_policy', (self.home / '.codex/config.toml').read_text())
        self.assertIn('--no-yolo', result.stdout)   # tells the user how to clear what is left

    def test_plain_rerun_after_marker_deletion_stays_off(self):
        self.install('--yolo')
        (self.home / '.agent-team/yolo').unlink()
        self.assertEqual(self.install().returncode, 0)
        self.assertFalse((self.home / '.agent-team/yolo').exists())
        self.assertNotIn('bypassPermissions', (self.home / '.claude/agents/backend.md').read_text())
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home)
        self.assertNotIn('claude()', (self.home / '.agent-team/shell.sh').read_text())

    def test_no_yolo_round_trip_removes_what_yolo_added_and_keeps_the_rest(self):
        settings = self.home / '.claude/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text('{"theme": "dark"}\n')
        codex = self.home / '.codex/config.toml'
        codex.parent.mkdir(parents=True)
        codex.write_text('personality = "terse"\n')
        self.assertEqual(self.install('--yolo').returncode, 0)
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home)
        self.assertIn('bypassPermissions', settings.read_text())
        self.assertIn('danger-full-access', codex.read_text())
        self.assertTrue((self.home / '.local/bin/codex').is_symlink())
        off = run_py(self.home / '.agent-team/build_setup.py', '--no-yolo', home=self.home, AGENT_TEAM_BACKUP_STAMP='20260103T000000Z')
        self.assertEqual(off.returncode, 0, off.stderr)
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, AGENT_TEAM_NO_YOLO='1')
        self.assertFalse((self.home / '.agent-team/yolo').exists())
        merged = json.loads(settings.read_text())
        self.assertEqual(merged['theme'], 'dark')
        self.assertNotIn('permissions', merged)
        self.assertNotIn('skipDangerousModePermissionPrompt', merged)
        text = codex.read_text()
        self.assertIn('personality = "terse"', text)
        for gone in ('approval_policy', 'danger-full-access'):
            self.assertNotIn(gone, text)
        self.assertNotIn('bypassPermissions', (self.home / '.claude/agents/backend.md').read_text())
        self.assertFalse((self.home / '.local/bin/codex').exists())
        self.assertNotIn('claude()', (self.home / '.agent-team/shell.sh').read_text())
        self.assertTrue(list((self.home / '.agent-team/backups/20260103T000000Z').rglob('settings.json')), 'removed keys are backed up')
        self.assertEqual(self.install().returncode, 0)   # and stays off
        self.assertNotIn('bypassPermissions', settings.read_text())

    def test_yolo_flags_conflict(self):
        self.assertNotEqual(self.install('--yolo', '--no-yolo').returncode, 0)

    def test_dry_run_discloses_the_global_claude_settings_it_will_set(self):
        out = self.install('--dry-run').stdout
        self.assertIn('global Claude model', out)

    def test_ccpm_is_fetched_at_the_pinned_commit_without_vcs_metadata(self):
        repo = Path(self.tmp.name) / 'ccpm-src'
        (repo / 'skill/ccpm').mkdir(parents=True)
        (repo / 'skill/ccpm/SKILL.md').write_text('ccpm')
        git = lambda *a: subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *a], check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-q'); git('add', '.'); git('commit', '-qm', 'one')
        pinned = git('rev-parse', 'HEAD')
        (repo / 'skill/ccpm/SKILL.md').write_text('moved on'); git('commit', '-qam', 'two')
        ok = self.install(AGENT_TEAM_CCPM_REPO=str(repo), AGENT_TEAM_CCPM_REF=pinned)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        vendor = self.home / '.agent-team/vendor/ccpm'
        self.assertEqual((vendor / 'skill/ccpm/SKILL.md').read_text(), 'ccpm')
        self.assertFalse((vendor / '.git').exists())
        self.assertTrue((self.home / '.claude/skills/ccpm').is_symlink())

    def test_ccpm_with_unknown_pin_is_skipped_with_a_warning(self):
        repo = Path(self.tmp.name) / 'ccpm-src'
        (repo / 'skill/ccpm').mkdir(parents=True)
        (repo / 'skill/ccpm/SKILL.md').write_text('ccpm')
        subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True)
        bad = self.install(AGENT_TEAM_CCPM_REPO=str(repo))   # default pin does not exist in this repo
        self.assertEqual(bad.returncode, 0, bad.stderr)
        self.assertIn('WARN: CCPM fetch', bad.stdout)
        self.assertFalse((self.home / '.agent-team/vendor/ccpm').exists())

    def test_restore_names_are_strictly_timestamps(self):
        self.install()
        for bad in ('.', '..', '', '../x', 'x', 'T1', 'restore-20260101T000000123456Z'):
            result = run_py(SOURCE / 'build_setup.py', '--restore', bad, home=self.home)
            self.assertNotEqual(result.returncode, 0, repr(bad))
            self.assertNotIn('Traceback', result.stderr)

    def test_windows_launchers_and_marker_have_one_source_shared_with_install_ps1(self):
        import re as _re
        sys.path.insert(0, str(SOURCE))
        try:
            import install_launchers as launchers
        finally:
            sys.path.pop(0)
        ps1 = (REPO / 'install.ps1').read_text()
        match = _re.search(r'\$cmd = "(.*?)"\r?\n', ps1)
        self.assertIsNotNone(match)
        for provider in ('claude', 'codex'):
            text = match.group(1).replace('`r`n', '\r\n').replace('`"', '"').replace('$provider', provider)
            self.assertEqual(text.encode(), launchers.cmd_launcher(provider))
        marker = launchers.B.YOLO_MARKER_TEXT
        self.assertIn(marker.rstrip('\n') + '`n', ps1)

    def test_wsl_rerun_with_install_ps1_present_is_a_noop(self):
        win = Path(self.tmp.name) / 'win'
        env = dict(AGENT_TEAM_WINDOWS_HOME=str(win))
        self.assertEqual(self.install('--yolo', **env).returncode, 0)
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, **env)
        before = tree(win)
        again = run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, **env)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(before, tree(win))
        self.assertEqual((win / '.agent-team/yolo').read_text(), (self.home / '.agent-team/yolo').read_text())

    def test_rules_go_into_a_managed_block_and_user_text_survives(self):
        rules = self.home / '.claude/CLAUDE.md'
        rules.parent.mkdir(parents=True)
        rules.write_text('# My own notes\nKeep answers short.\n')
        self.assertEqual(self.install(AGENT_TEAM_BACKUP_STAMP='20260102T000000Z').returncode, 0)
        text = rules.read_text()
        self.assertTrue(text.startswith('# My own notes\nKeep answers short.'))
        self.assertEqual(text.count('<!-- BEGIN AGENT TEAM -->'), 1)
        self.assertIn('Universal engineering rules', text)
        self.assertNotIn('tags: [claude-code', text, 'front matter is not embedded mid-file')
        saved = list((self.home / '.agent-team/backups/20260102T000000Z').rglob('CLAUDE.md'))
        self.assertEqual([p.read_text() for p in saved], ['# My own notes\nKeep answers short.\n'])
        rules.write_text(text.replace('Keep answers short.', 'Keep answers very short.'))
        before = rules.read_text()
        self.assertIn('No changes needed', self.install().stdout)
        self.assertEqual(rules.read_text(), before)
        # an edited block is refreshed, text around it is kept
        rules.write_text(text.replace('Read existing relevant files', 'TAMPERED'))
        self.install()
        self.assertNotIn('TAMPERED', rules.read_text())
        self.assertTrue(rules.read_text().startswith('# My own notes'))

    def test_unmarked_copy_of_older_rules_is_replaced_by_the_block(self):
        rules = self.home / '.codex/AGENTS.md'
        rules.parent.mkdir(parents=True)
        rules.write_text('---\nscope: global\n---\n\n# Universal engineering rules\nold text\n')
        self.install()
        text = rules.read_text()
        self.assertEqual(text.count('# Universal engineering rules'), 1)
        self.assertTrue(text.startswith('<!-- BEGIN AGENT TEAM -->'))

    def test_restore_rejects_unknown_backup_and_path_traversal(self):
        self.assertNotEqual(run_py(SOURCE / 'build_setup.py', '--restore', 'nope', home=self.home).returncode, 0)
        self.assertNotEqual(run_py(SOURCE / 'build_setup.py', '--restore', '../x', home=self.home).returncode, 0)

    def test_locally_edited_content_survives_reinstall_and_is_reported(self):
        self.install()
        skill = self.home / '.agent-team/skills/team-qa-flaky-tests/SKILL.md'
        skill.write_text(skill.read_text() + '\nLEARNED\n')
        again = self.install()
        self.assertIn('LEARNED', skill.read_text())
        self.assertIn('kept (locally modified', again.stdout)

    def test_code_is_refreshed_even_when_modified(self):
        self.install()
        script = self.home / '.agent-team/team.py'
        script.write_text('# tampered\n')
        self.install()
        self.assertEqual(script.read_bytes(), (SOURCE / 'team.py').read_bytes())
        self.assertTrue(os.access(script, os.X_OK))

    def test_only_installed_providers_are_configured(self):
        self.assertEqual(self.install(AGENT_TEAM_PROVIDERS='claude').returncode, 0)
        self.assertTrue((self.home / '.claude/agents/chief.md').is_file())
        self.assertFalse((self.home / '.codex').exists())

    def test_launchers_use_the_resolved_root_and_shell_block_is_added_once(self):
        self.install()
        for _ in range(2):
            result = run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, SHELL='/bin/zsh')
            self.assertEqual(result.returncode, 0, result.stderr)
        launcher = (self.home / '.local/bin/claude-team').read_text()
        self.assertIn(str(self.home / '.agent-team/team.py'), launcher)
        self.assertTrue(os.access(self.home / '.local/bin/claude-team', os.X_OK))
        rc = (self.home / '.zshrc').read_text()
        self.assertEqual(rc.count('BEGIN PERSONAL AGENT TEAM'), 1)
        self.assertNotIn(str(self.home), rc, 'the rc block must stay relative to $HOME')

    def test_launchers_dry_run_writes_nothing(self):
        self.install()
        before = tree(self.home)
        result = run_py(SOURCE / 'install_launchers.py', '--dry-run', home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, tree(self.home))

    def test_windows_mirror_only_when_a_windows_home_is_given(self):
        win = Path(self.tmp.name) / 'win'
        self.assertEqual(self.install().returncode, 0)
        self.assertFalse(win.exists())
        result = run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, AGENT_TEAM_WINDOWS_HOME=str(win))
        self.assertEqual(result.returncode, 0, result.stderr)
        cmd = win / '.agent-team/bin/claude-team.cmd'
        self.assertIn(b'\r\n', cmd.read_bytes())
        self.assertEqual(json.loads((win / '.agent-team/wsl-target.json').read_text())['home'], str(self.home))
        before = tree(win)
        run_py(self.home / '.agent-team/install_launchers.py', '--no-plugins', home=self.home, AGENT_TEAM_WINDOWS_HOME=str(win))
        self.assertEqual(before, tree(win))


class InstallShTests(unittest.TestCase):
    def run_install(self, home, *extra):
        env={**os.environ,'AGENT_TEAM_PROVIDERS':'claude,codex','AGENT_TEAM_SKIP_PLUGINS':'1','AGENT_TEAM_CCPM_REPO':str(home/'no-such-ccpm'),'AGENT_TEAM_WSL':'0'}
        env.pop('AGENT_TEAM_WINDOWS_HOME',None)
        return subprocess.run([str(REPO/'install.sh'),'--home',str(home),'--no-system','--no-windows',*extra],env=env,capture_output=True,text=True,cwd=str(home.parent))

    def test_noop_rerun_prints_one_summary_and_no_phantom_backup(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sh-') as tmp:
            home=Path(tmp)/'home'
            first=self.run_install(home)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertIn('Done. Backups of anything changed',first.stdout)
            self.assertNotIn('No changes needed',first.stdout)
            again=self.run_install(home)
            self.assertEqual(again.returncode,0,again.stderr)
            self.assertEqual(again.stdout.count('No changes needed'),1,again.stdout)
            self.assertNotIn('Backups of anything changed',again.stdout)
            self.assertNotIn('--restore',again.stdout)
            self.assertEqual(len(list((home/'.agent-team/backups').iterdir())),1,'a no-op run creates no backup directory')

    def test_empty_and_malformed_option_values_are_usage_errors(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sh-') as tmp:
            home = Path(tmp) / 'home'
            for args in (['--home', ''], ['--home='], ['--windows-home', ''], ['--restore', ''], ['--restore='], ['--restore', '.'],
                         ['--restore', '..'], ['--restore', '../x'], ['--restore', 'T1'], ['--yolo', '--no-yolo']):
                result = subprocess.run([str(REPO / 'install.sh'), '--dry-run', *args], capture_output=True, text=True, cwd=tmp,
                                        env={**os.environ, 'HOME': str(home)})
                self.assertEqual(result.returncode, 2, f'{args}: {result.stdout}{result.stderr}')
            self.assertFalse(home.exists())

    def test_install_records_that_the_windows_mirror_was_skipped(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-sh-') as tmp:
            home=Path(tmp)/'home'
            self.assertEqual(self.run_install(home).returncode,0)
            self.assertEqual((home/'.agent-team/windows-target').read_text().strip(),'none')


class DoctorTests(unittest.TestCase):
    def doctor(self, home, *args, **env):
        return run_py(SOURCE / 'team.py', 'doctor', *args, home=home, **env)

    def test_empty_home_fails_with_json_and_points_to_the_installer_without_writing(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-doctor-') as tmp:
            home = Path(tmp)
            result = self.doctor(home, '--json')
            self.assertEqual(result.returncode, 1)
            data = json.loads(result.stdout)
            self.assertFalse(data['ok'])
            self.assertIn('install.sh', result.stdout)
            self.assertEqual(list(home.rglob('*')), [])

    def test_table_lists_every_check_and_fix_section(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-doctor-') as tmp:
            result = self.doctor(Path(tmp))
            for word in ('python', 'git', 'tmux', 'roles', 'skills', 'rules', 'launchers', 'Fix:', 'Result: FAIL'):
                self.assertIn(word, result.stdout)

    def test_windows_row_follows_the_installs_recorded_choice_even_on_wsl(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-doctor-') as tmp:
            home=Path(tmp)/'home';win=Path(tmp)/'win';home.mkdir()
            self.assertEqual(run_py(SOURCE/'build_setup.py','--package-from',str(SOURCE),home=home).returncode,0)
            def row(**env):
                data=json.loads(self.doctor(home,'--json',AGENT_TEAM_WSL='1',**env).stdout)
                return next(r for r in data['checks'] if r['name']=='windows mirror')
            self.assertEqual(row()['status'],'n/a')                           # recorded 'none' -> skipped on purpose
            self.assertEqual(row(AGENT_TEAM_WINDOWS_HOME=str(win))['status'],'n/a')
            (home/'.agent-team/windows-target').write_text(str(win)+'\n')    # installed with a mirror, which is now incomplete
            missing=row()
            self.assertEqual(missing['status'],'fail')
            self.assertIn('claude-team.cmd',missing['detail'])
            (home/'.agent-team/windows-target').unlink()                      # legacy install without a record: old behaviour
            self.assertEqual(row()['status'],'warn')

    def test_signed_out_coderabbit_is_a_warning_even_with_exit_zero(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-doctor-') as tmp:
            home = Path(tmp) / 'home'
            home.mkdir()
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            fake = bin_dir / 'coderabbit'
            fake.write_text('#!/bin/sh\ncase "$1 $2" in "auth status") echo "Status : signed out"; exit 0;; esac\necho coderabbit 1.0\n')
            fake.chmod(0o755)
            data = json.loads(self.doctor(home, '--json', PATH=f'{bin_dir}:/usr/bin:/bin').stdout)
            row = next(r for r in data['checks'] if r['name'] == 'coderabbit')
            self.assertEqual(row['status'], 'warn')
            self.assertEqual(row['fix'], 'coderabbit auth login')
            fake.write_text('#!/bin/sh\ncase "$1 $2" in "auth status") echo "Status : signed in"; exit 0;; esac\n')
            data = json.loads(self.doctor(home, '--json', PATH=f'{bin_dir}:/usr/bin:/bin').stdout)
            self.assertEqual(next(r for r in data['checks'] if r['name'] == 'coderabbit')['status'], 'ok')

    def test_installed_package_counts_are_exact(self):
        with tempfile.TemporaryDirectory(prefix='ai-setup-doctor-') as tmp:
            home = Path(tmp)
            self.assertEqual(run_py(SOURCE / 'build_setup.py', '--package-from', str(SOURCE), home=home).returncode, 0)
            rows = {r['name']: r for r in json.loads(self.doctor(home, '--json').stdout)['checks']}
            self.assertEqual(rows['roles (claude)']['status'], 'ok')
            self.assertIn('120/120', rows['skills (claude)']['detail'])
            (home / '.claude/agents/qa.md').unlink()
            rows = {r['name']: r for r in json.loads(self.doctor(home, '--json').stdout)['checks']}
            self.assertEqual(rows['roles (claude)']['status'], 'fail')
            self.assertIn('qa', rows['roles (claude)']['detail'])


if __name__=='__main__':unittest.main()
