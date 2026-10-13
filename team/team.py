#!/usr/bin/env python3
"""Personal launchers, isolated worktrees and explicit local push gates."""
import argparse, contextlib, datetime, fcntl, hashlib, json, os, platform, re, shlex, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROVIDERS = ('claude','codex')
PROVIDER_OPTION = '@agent_team_provider'
MAX_PANES = 6
TRUST_WAIT = 15.0
_clock = time.monotonic
_sleep = time.sleep
ROLES = ('chief','validator','architect','product','backend','frontend','engine','data','qa','security','platform','integrator')

def is_wsl():
    flag=os.environ.get('AGENT_TEAM_WSL')
    if flag in ('0','1'):return flag=='1'
    if os.environ.get('WSL_DISTRO_NAME'):return True
    try:return 'microsoft' in Path('/proc/version').read_text().lower()
    except OSError:return False

def windows_home():
    """Windows profile as a Linux path (WSL only) or None. AGENT_TEAM_WINDOWS_HOME overrides ("none" disables)."""
    value=os.environ.get('AGENT_TEAM_WINDOWS_HOME')
    if value is not None:return None if value.strip().lower() in ('','none') else Path(value)
    if not is_wsl():return None
    try:
        out=subprocess.run(['cmd.exe','/c','echo %USERPROFILE%'],capture_output=True,text=True,timeout=15,cwd='/mnt/c' if Path('/mnt/c').is_dir() else None).stdout
        lines=[x.strip() for x in out.replace('\r','\n').split('\n') if x.strip()]
        path=subprocess.run(['wslpath','-u',lines[-1]],capture_output=True,text=True,timeout=15).stdout.strip()
        return Path(path) if path.startswith('/') and Path(path).parent.is_dir() else None
    except (OSError,IndexError,subprocess.SubprocessError):return None

WINDOWS = windows_home()

def yolo_enabled():
    """YOLO defaults (agents skip permission prompts) are opt-in: install.sh --yolo writes ~/.agent-team/yolo.
    AGENT_TEAM_NO_BYPASS=1 switches them off for one command."""
    if os.environ.get('AGENT_TEAM_NO_BYPASS'):return False
    return os.environ.get('AGENT_TEAM_YOLO')=='1' or (Path.home()/'.agent-team/yolo').is_file()

RULES_BEGIN='<!-- BEGIN AGENT TEAM -->'
RULES_END='<!-- END AGENT TEAM -->'

def managed_rules(existing, rules):
    """Return EXISTING with the shared RULES as a marked block: replace the block, replace a file that is just an
    older copy of the rules, or append to the user's own text. Mirrored in build_setup.managed_rules."""
    body=re.sub(r'\A---\r?\n.*?\r?\n---\r?\n','',rules.lstrip('\ufeff'),count=1,flags=re.S).strip('\n')
    block=f'{RULES_BEGIN}\n{body}\n{RULES_END}\n'
    if existing is None or not existing.strip():return block
    if RULES_BEGIN in existing and RULES_END in existing:
        head,rest=existing.split(RULES_BEGIN,1)
        return head+block+rest.split(RULES_END,1)[1].lstrip('\n')
    if '# Universal engineering rules' in existing:return block   # an unmarked copy written by an earlier install (backed up)
    return existing.rstrip('\n')+'\n\n'+block

def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, **kwargs)

def git(*args, cwd=None):
    return run(['git',*args],cwd=cwd,capture_output=True).stdout.strip()

def repo():
    return Path(git('rev-parse','--show-toplevel')).resolve()

def validate_name(value):
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*',value):
        raise ValueError('Use a lowercase kebab-case name beginning with a letter.')
    return value

def executable(provider):
    # Skip a managed shim while keeping vendor upgrades at their normal path.
    candidates=[]
    if provider=='codex':
        node_root=Path.home()/'.nvm/versions/node'
        if node_root.exists():
            def version(p):
                return tuple(int(x) for x in re.findall(r'\d+',p.name))
            candidates.extend(str(p/'bin') for p in sorted(node_root.iterdir(),key=version,reverse=True))
    elif provider=='claude':candidates.append(str(Path.home()/'.local/bin'))
    candidates.extend(os.environ.get('PATH','').split(os.pathsep))
    for item in candidates:
        # Windows npm launchers cannot supply a native WSL team runtime.
        if item.startswith('/mnt/'):continue
        path=Path(item)/provider
        if path.is_file() and os.access(path,os.X_OK):
            if path.resolve() == (ROOT/'cli-shim').resolve():continue
            if provider=='codex' and (path.parent/'node').is_file():
                os.environ['PATH']=str(path.parent)+os.pathsep+os.environ.get('PATH','')
            return str(path)
    raise ValueError(f'{provider} is not installed on PATH.')

def models():
    return json.loads((ROOT/'models.json').read_text())

def render_bootstrap(provider):
    """Render team/bootstrap-<provider>.txt, replacing exactly the five contract tokens."""
    path=ROOT/f'bootstrap-{provider}.txt'
    if not path.is_file():
        raise ValueError(f'Missing Chief bootstrap prompt: {path}. Expected team/bootstrap-{provider}.txt; run the installer/sync from a checkout that has it.')
    m=models()[provider]
    values={'PROVIDER':provider,'CHIEF_MODEL':m['chief'],'VALIDATOR_MODEL':m['validator'],'WORKER_MODEL':m['worker'],'EFFORT':models()['effort']}
    return re.sub(r'\{\{(PROVIDER|CHIEF_MODEL|VALIDATOR_MODEL|WORKER_MODEL|EFFORT)\}\}',lambda match: values[match.group(1)],path.read_text())

def command(provider, role, extra, prompt=None):
    m=models()
    tier=role if role in ['chief','validator'] else 'worker'
    if prompt is None:
        prompt=render_bootstrap(provider) if role=='chief' else f'Act as {role}. Read ~/.agent-team/roles/{role}.md, universal rules and preferences. Follow Chief assignments; verify your worktree and do not start unapproved implementation.'
    if extra:prompt+='\n\nUser request:\n'+' '.join(extra)
    yolo=yolo_enabled()
    if provider=='claude':
        return [executable(provider),*(['--dangerously-skip-permissions'] if yolo else []),'--agent',role,'--model',m[provider][tier],'--effort','high',prompt]
    instructions=(ROOT/f'roles/{role}.md').read_text()
    return [executable(provider),*(['--dangerously-bypass-approvals-and-sandbox'] if yolo else []),'-m',m[provider][tier],'-c','model_reasoning_effort="high"','-c','developer_instructions='+json.dumps(instructions),prompt]

# ---- tmux plumbing -------------------------------------------------------

def require_tmux():
    if not shutil.which('tmux'):raise ValueError('tmux is missing. Install it or use --no-tmux.')

def tmux(*args, check=True):
    result=subprocess.run(['tmux',*args],capture_output=True,text=True)
    if check and result.returncode!=0:
        raise ValueError(f'tmux {args[0]} failed: '+(result.stderr.strip() or f'exit {result.returncode}'))
    return result

def tmux_out(*args):
    return tmux(*args).stdout.strip()

def state_root():
    return Path.home()/'.agent-team/state'

def inherited_session(session):
    """Inherited AGENT_TEAM_* values are only valid inside the session that exported them."""
    return os.environ.get('AGENT_TEAM_SESSION')==session

def session_state(session):
    if inherited_session(session) and os.environ.get('AGENT_TEAM_STATE'):return Path(os.environ['AGENT_TEAM_STATE'])
    return state_root()/session

def team_state():
    value=os.environ.get('AGENT_TEAM_STATE')
    if not value:raise ValueError('Not inside an agent-team session: AGENT_TEAM_STATE is unset. Start with claude-team or codex-team.')
    return Path(value)

def team_env(provider, session, role, state, chief_pane, task=None):
    env={'AGENT_TEAM_PROVIDER':provider,'AGENT_TEAM_SESSION':session,'AGENT_TEAM_ROLE':role,'AGENT_TEAM_STATE':str(state)}
    if chief_pane:env['AGENT_TEAM_CHIEF_PANE']=chief_pane
    if task:env['AGENT_TEAM_TASK']=task
    return env

def pane_shell_command(env, argv, chief_from_pane=False):
    """Shell string for tmux: exec the agent under an explicit env, argv quoted literally."""
    assignments=[f'{k}={v}' for k,v in env.items()]
    if os.environ.get('PATH'):assignments.append('PATH='+os.environ['PATH'])
    text='exec env '
    if chief_from_pane:text+='AGENT_TEAM_CHIEF_PANE="$TMUX_PANE" '
    return text+shlex.join([*assignments,*argv])

def record_provider(session, provider):
    current=tmux_out('show-options','-qv','-t',session,PROVIDER_OPTION)
    if current and current!=provider:
        raise ValueError(f'Session {session} is a {current} team; a {provider} agent cannot join it (provider-exclusive teams).')
    if not current:tmux('set-option','-t',session,PROVIDER_OPTION,provider)

def launch(args):
    cwd=Path(args.directory).expanduser().resolve()
    if not cwd.is_dir():raise ValueError(f'Not a directory: {cwd}')
    cmd=command(args.provider,args.role,args.prompt)
    base_env={'AGENT_TEAM_PROVIDER':args.provider,'AGENT_TEAM_ROLE':args.role}
    if args.dry_run:
        print(json.dumps({'provider':args.provider,'role':args.role,'cwd':str(cwd),'argv':cmd,'tmux':not args.no_tmux,'env':base_env},indent=2));return
    if args.no_tmux:
        os.environ.update(base_env);os.chdir(cwd);os.execv(cmd[0],cmd)
    require_tmux()
    # Inside an existing tmux pane this pane becomes the Chief (or the launched
    # role) and its session is recorded as a provider-exclusive team.
    if os.environ.get('TMUX'):
        pane=os.environ.get('TMUX_PANE','')
        session=tmux_out('display-message','-p',*(['-t',pane] if pane else []),'#{session_name}')
        record_provider(session,args.provider)
        tmux('set-option','-p','-t',pane or session,'allow-set-title','off')
        state=session_state(session)
        (state/'mailbox'/args.role).mkdir(parents=True,exist_ok=True)
        chief=pane if args.role=='chief' or not inherited_session(session) else (os.environ.get('AGENT_TEAM_CHIEF_PANE') or pane)
        os.environ.update(team_env(args.provider,session,args.role,state,chief))
        os.chdir(cwd);os.execv(cmd[0],cmd)
    prefix=f'{args.provider}-team-{cwd.name}'
    name=re.sub(r'[^a-zA-Z0-9_-]','-',prefix)[:50]+'-'+str(os.getpid())
    state=state_root()/name
    (state/'mailbox'/args.role).mkdir(parents=True,exist_ok=True)
    env=team_env(args.provider,name,args.role,state,None)
    run(['tmux','new-session','-d','-s',name,'-c',str(cwd),pane_shell_command(env,cmd,chief_from_pane=True)])
    tmux('set-option','-t',name,PROVIDER_OPTION,args.provider)
    tmux('set-option','-p','-t',name,'allow-set-title','off')
    os.execvp('tmux',['tmux','attach-session','-t',name])

# ---- pane registry -------------------------------------------------------

@contextlib.contextmanager
def registry_lock(state):
    state.mkdir(parents=True,exist_ok=True)
    with open(state/'panes.lock','a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)

def load_registry(state):
    path=state/'panes.json'
    if not path.exists():return []
    data=json.loads(path.read_text())
    if not isinstance(data,list):raise ValueError(f'Corrupt pane registry: {path}')
    return data

def save_registry(state, entries):
    path=state/'panes.json'
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(entries,indent=2)+'\n');temp.replace(path)

def live_pane_ids():
    result=tmux('list-panes','-a','-F','#{pane_id}',check=False)
    return set(result.stdout.split()) if result.returncode==0 else set()

# ---- spawn ---------------------------------------------------------------

def worker_prompt(provider, role, task, cwd, session, chief_pane, state, model, effort):
    return (f'Act as {role}. Task: {task or "as assigned by Chief"}. You are a pane teammate in tmux team session {session}; '
        f'the team provider is {provider} - use only {provider} agents and never launch another provider.\n'
        f'Your assigned directory is {cwd}. Verify `pwd` equals your assigned directory before any edit.\n'
        f'Read ~/.agent-team/roles/{role}.md, universal rules and preferences. Follow Chief assignments; do not start unapproved implementation.\n'
        f'Chief pane: {chief_pane}. Team state: {state}.\n'
        f'On startup, before any other work, acknowledge Chief by running: '
        f'agent-team send chief --from {role} "ACK {role}: model {model}, effort {effort}, pwd $(pwd)".\n'
        f'Messaging: report to Chief with `agent-team send chief --from {role} "<message>"` (long text: pipe to `agent-team send chief --from {role} -`). '
        f'When a line like "[from <role>] read <file>" appears, read that file; list unread mail with `agent-team inbox`. '
        f'Chief is the only agent that talks to the user; send questions and blockers to Chief with agent-team send chief; '
        f'do not start autonomous loops; stop after your assigned increment and report. '
        f'Report branch, exact SHA, changed paths and test results when done or blocked.')

def claude_trusts(directory):
    """Read-only: is DIR a linked worktree whose main checkout accepted the trust dialog?"""
    try:
        directory=Path(directory)
        gitdir=(directory/git('rev-parse','--git-dir',cwd=directory)).resolve()
        common=(directory/git('rev-parse','--git-common-dir',cwd=directory)).resolve()
        if gitdir==common or common.name!='.git':return False
        config=Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home())/'.claude.json'
        projects=json.loads(config.read_text()).get('projects',{})
        return projects.get(str(common.parent),{}).get('hasTrustDialogAccepted') is True
    except (OSError,ValueError,AttributeError,subprocess.CalledProcessError):
        return False

TRUST_RE=re.compile(r'trust this folder|trust the files in this folder',re.I)
READY_RE=re.compile(r'bypass permissions|\? for shortcuts|esc to interrupt|shift\+tab',re.I)
OPTION_RE=re.compile(r'^\s*(?P<mark>[❯›>])?\s*(?P<num>\d+)\.\s+(?P<text>.*)$')

def trust_choice(screen):
    """Return (index of selected option, index of the 'Yes, I trust' option) or None."""
    options=[m for m in map(OPTION_RE.match,screen.splitlines()) if m]
    selected=[i for i,m in enumerate(options) if m.group('mark')]
    yes=[i for i,m in enumerate(options) if re.search(r'yes,?\s+i trust',m.group('text'),re.I)]
    if len(selected)!=1 or len(yes)!=1:return None
    return selected[0],yes[0]

def accept_trust(pane):
    """Move the selection to 'Yes, I trust this folder', verify it by capture, then Enter."""
    for _ in range(4):
        screen=tmux('capture-pane','-p','-t',pane,check=False).stdout
        choice=trust_choice(screen)
        if not choice:return False
        selected,yes=choice
        if selected==yes:
            tmux('send-keys','-t',pane,'Enter');return True
        tmux('send-keys','-t',pane,'Down' if yes>selected else 'Up');_sleep(0.2)
    return False

def settle_trust(pane, directory, provider):
    """Return awaiting_trust: True only when a trust prompt is left for the user."""
    if provider!='claude':return False
    deadline=_clock()+float(os.environ.get('AGENT_TEAM_TRUST_WAIT',TRUST_WAIT))
    while True:
        result=tmux('capture-pane','-p','-t',pane,check=False)
        if result.returncode!=0:return False
        if TRUST_RE.search(result.stdout):
            return not (claude_trusts(directory) and accept_trust(pane))
        if READY_RE.search(result.stdout) or _clock()>=deadline:return False
        _sleep(0.5)

def window_panes(window):
    return tmux_out('list-panes','-t',window,'-F','#{pane_id}').split()

def split_in(window, cwd, shell):
    """Split WINDOW; return pane id, or None when tmux reports no space."""
    result=tmux('split-window','-d','-t',window,'-c',str(cwd),'-P','-F','#{pane_id}',shell,check=False)
    if result.returncode==0:return result.stdout.strip()
    if 'no space for new pane' in result.stderr:return None
    raise ValueError('tmux split-window failed: '+(result.stderr.strip() or f'exit {result.returncode}'))

def place_pane(session, chief_window, cwd, shell, limit):
    if len(window_panes(chief_window))<limit:
        pane=split_in(chief_window,cwd,shell)
        if pane:return pane,chief_window
    # Overflow: fill an existing team-<n> window first, else open the next one.
    numbered=[]
    for line in tmux_out('list-windows','-t',session,'-F','#{window_id} #{window_name}').splitlines():
        window_id,_,name=line.partition(' ')
        match=re.fullmatch(r'team-(\d+)',name)
        if match:numbered.append((int(match.group(1)),window_id))
    for _,window in sorted(numbered):
        if len(window_panes(window))<limit:
            pane=split_in(window,cwd,shell)
            if pane:return pane,window
    number=max([n for n,_ in numbered],default=0)+1
    out=tmux_out('new-window','-d','-t',f'{session}:','-n',f'team-{number}','-c',str(cwd),'-P','-F','#{pane_id} #{window_id}',shell)
    pane,window=out.split()
    return pane,window

def install_retile_hooks(session, window):
    # pane-exited is window-scoped in tmux; after-kill-pane is session-scoped.
    tmux('set-hook','-w','-t',window,'pane-exited','select-layout tiled')
    tmux('set-hook','-t',session,'after-kill-pane','select-layout tiled')

def spawn(args):
    if not os.environ.get('TMUX'):raise ValueError('spawn must run inside the team tmux session ($TMUX is unset).')
    require_tmux()
    role=args.role
    if role=='chief':raise ValueError('chief is the orchestrator pane and cannot be spawned.')
    if role not in ROLES:raise ValueError(f'Unknown role: {role}')
    task=validate_name(args.task) if args.task else None
    cwd=Path(args.directory).expanduser().resolve()
    if not cwd.is_dir():raise ValueError(f'Not a directory: {cwd}')
    chief_pane=os.environ.get('AGENT_TEAM_CHIEF_PANE') or os.environ.get('TMUX_PANE')
    if not chief_pane:raise ValueError('Cannot find the Chief pane: set AGENT_TEAM_CHIEF_PANE or run inside tmux.')
    session=os.environ.get('AGENT_TEAM_SESSION') or tmux_out('display-message','-p','-t',chief_pane,'#{session_name}')
    provider=tmux_out('show-options','-qv','-t',session,PROVIDER_OPTION)
    if not provider:raise ValueError(f'No team provider recorded on session {session}; start the team with claude-team or codex-team.')
    if args.provider and args.provider!=provider:
        raise ValueError(f'Refusing {args.provider} agent: this is a {provider} team (provider-exclusive).')
    state=session_state(session)
    chief_window=tmux_out('display-message','-p','-t',chief_pane,'#{window_id}')
    limit=int(os.environ.get('AGENT_TEAM_MAX_PANES',MAX_PANES))
    tier='validator' if role=='validator' else 'worker'
    model=models()[provider][tier]
    prompt=worker_prompt(provider,role,task,cwd,session,chief_pane,state,model,models()['effort'])
    cmd=command(provider,role,args.prompt,prompt=prompt)
    env=team_env(provider,session,role,state,chief_pane,task)
    with registry_lock(state):
        entries=load_registry(state)
        live=live_pane_ids()
        for entry in entries:
            if entry.get('role')==role and entry.get('task')==task and entry.get('pane') in live:
                raise ValueError(f'{role}{":"+task if task else ""} already has a live pane ({entry["pane"]}); refusing to duplicate.')
        pane,window=place_pane(session,chief_window,cwd,pane_shell_command(env,cmd),limit)
        title=f'{role}:{task}' if task else role
        # Claude Code rewrites titles via OSC; keep role/task titles stable.
        tmux('set-option','-p','-t',pane,'allow-set-title','off')
        tmux('select-pane','-t',pane,'-T',title)
        tmux('set-option','-w','-t',window,'pane-border-status','top')
        tmux('select-layout','-t',window,'tiled')
        install_retile_hooks(session,window)
        entry={'role':role,'task':task,'pane':pane,'window':window,'cwd':str(cwd),'provider':provider,'model':model,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        entries=[e for e in entries if not (e.get('role')==role and e.get('task')==task)]
        entries.append(entry)
        save_registry(state,entries)
    awaiting=settle_trust(pane,cwd,provider)
    print(json.dumps({**{k:entry[k] for k in ('role','task','pane','window','cwd','provider','model')},'awaiting_trust':awaiting},indent=2))

# ---- mailbox -------------------------------------------------------------

def resolve_target(target, state):
    """Return (role, pane id) for a role name or %pane id."""
    chief=os.environ.get('AGENT_TEAM_CHIEF_PANE')
    entries=load_registry(state)
    if target.startswith('%'):
        if target==chief:return 'chief',target
        for entry in entries:
            if entry.get('pane')==target:return entry['role'],target
        raise ValueError(f'Pane {target} is not registered in this team.')
    if target not in ROLES:raise ValueError(f'Unknown role: {target}')
    if target=='chief':
        if not chief:raise ValueError('AGENT_TEAM_CHIEF_PANE is unset; cannot find the Chief pane.')
        return 'chief',chief
    live=live_pane_ids()
    matches=[e for e in entries if e.get('role')==target and e.get('pane') in live]
    if not matches:raise ValueError(f'No live registered pane for role {target}.')
    return target,max(matches,key=lambda e:e.get('started_at',''))['pane']

def send(args):
    state=team_state()
    sender=args.sender or os.environ.get('AGENT_TEAM_ROLE')
    if not sender:raise ValueError('Cannot tell who is sending: pass --from ROLE or set AGENT_TEAM_ROLE.')
    validate_name(sender)
    text=sys.stdin.read() if args.message==['-'] else ' '.join(args.message)
    if not text.strip():raise ValueError('Empty message.')
    require_tmux()
    role,pane=resolve_target(args.target,state)
    box=state/'mailbox'/role
    box.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path=box/f'{stamp}-from-{sender}.md'
    counter=1
    while path.exists():
        path=box/f'{stamp}-{counter}-from-{sender}.md';counter+=1
    path.write_text(text if text.endswith('\n') else text+'\n')
    notify(role,pane,sender,path)
    print(path)

SGR_RE=re.compile(r'\x1b\[([0-9;]*)m')
ANSI_RE=re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
PROMPT_RE=re.compile(r'^(?:\x1b\[[0-9;]*m|[\s│])*[❯›](?P<rest>.*)$')

def input_is_empty(pane):
    """True/False for the pane's input line; None when it cannot be determined.

    Looks at the LAST prompt line (Claude "❯", Codex "›"). Text rendered dim
    (SGR 2) is the idle placeholder suggestion, not typed input.
    """
    mode=tmux('display-message','-p','-t',pane,'#{pane_in_mode}',check=False)
    if mode.returncode!=0:return None
    # Copy/view mode swallows keystrokes as commands: treat as busy.
    if mode.stdout.strip()=='1':return False
    result=tmux('capture-pane','-p','-e','-t',pane,check=False)
    if result.returncode!=0:return None
    rest=None
    for line in result.stdout.splitlines():
        match=PROMPT_RE.match(line)
        if match:rest=match.group('rest')
    if rest is None:return None
    dim=False;typed=''
    position=0
    for sgr in SGR_RE.finditer(rest):
        if not dim:typed+=rest[position:sgr.start()]
        position=sgr.end()
        for code in (sgr.group(1) or '0').split(';'):
            if code in ('0',''):dim=False
            elif code=='2':dim=True
            elif code=='22':dim=False
    if not dim:typed+=rest[position:]
    typed=ANSI_RE.sub('',typed).replace('│',' ')
    return typed.strip(' \t\xa0')==''

def type_if_idle(pane, line):
    """Type LINE + Enter only if the input is empty, re-checked immediately before typing.

    Returns True when typed, False when busy or tmux refused the keys, None when the input cannot be read."""
    state=input_is_empty(pane)
    if not state:return state
    if not input_is_empty(pane):return False
    if tmux('send-keys','-t',pane,'-l',line,check=False).returncode!=0:return False
    if tmux('send-keys','-t',pane,'Enter',check=False).returncode!=0:
        tmux('send-keys','-t',pane,'C-u',check=False)  # input was verified empty: remove our partial line
        return False
    return True

def deliver_when_idle(pane, line, timeout=60.0, interval=2.0):
    """Retry type_if_idle until TIMEOUT; give up silently if the pane is gone or stays busy."""
    deadline=_clock()+timeout
    while True:
        typed=type_if_idle(pane,line)
        if typed:return True
        if typed is None and tmux('display-message','-p','-t',pane,'#{pane_id}',check=False).returncode!=0:return False
        if _clock()>=deadline:return False
        _sleep(interval)

def start_retry(pane, line):
    subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'_deliver','--pane',pane,'--line',line],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def notify(role, pane, sender, path):
    """Never type into a pane the user may be typing in (Chief pane included)."""
    line=f'[from {sender}] read {path}'
    if type_if_idle(pane,line):return
    tmux('display-message','-t',pane,'-d','8000',f'[agent-team] new message for {role}: {path}')
    start_retry(pane,line)

def deliver(args):
    deliver_when_idle(args.pane,args.line)

def inbox(args):
    state=team_state()
    role=args.role or os.environ.get('AGENT_TEAM_ROLE')
    if not role:raise ValueError('Pass --role ROLE or set AGENT_TEAM_ROLE.')
    if role not in ROLES:raise ValueError(f'Unknown role: {role}')
    box=state/'mailbox'/role
    messages=sorted(p for p in box.glob('*.md') if p.is_file()) if box.is_dir() else []
    if not messages:print('No unread messages.');return
    done=box/'read';done.mkdir(exist_ok=True)
    for message in messages:
        print(f'=== {message.name} ===');print(message.read_text().rstrip('\n'))
        message.replace(done/message.name)

def panes(args):
    state=team_state()
    live=live_pane_ids()
    print(json.dumps([{**e,'status':'live' if e.get('pane') in live else 'dead'} for e in load_registry(state)],indent=2))

def worktree(args):
    root=repo()
    task=validate_name(args.task)
    role=validate_name(args.role)
    if role not in ROLES:raise ValueError('Unknown personal role.')
    branch=f'{args.kind}/{task}-{role}'
    parent=root.parent/(root.name+'-worktrees')
    path=parent/f'{task}-{role}'
    if path.exists():raise ValueError(f'Worktree path already exists: {path}')
    # Resolve base before mutation: never create a broken tree or branch.
    git('rev-parse','--verify',args.base+'^{commit}',cwd=root)
    parent.mkdir(parents=True,exist_ok=True)
    run(['git','worktree','add','-b',branch,str(path),args.base],cwd=root)
    print(json.dumps({'role':role,'branch':branch,'worktree':str(path)},indent=2))

def gate_directory():
    path=Path(git('rev-parse','--git-common-dir'))
    if not path.is_absolute():path=Path.cwd()/path
    return path.resolve()/'agent-team-gates'

def clean_head():
    root=repo()
    if git('status','--porcelain',cwd=root):raise ValueError('Commit or isolate outstanding changes before recording/pushing a verified HEAD.')
    return root,git('rev-parse','HEAD',cwd=root),git('branch','--show-current',cwd=root)

def validate_review(data,authority,sha):
    try:review=json.loads(data)
    except (ValueError,UnicodeDecodeError):raise ValueError('Review report must be structured JSON with a pass verdict.') from None
    if not isinstance(review,dict) or review.get('sha')!=sha:raise ValueError('The report must contain the exact current commit SHA.')
    if review.get('authority')!=authority:raise ValueError('Report authority does not match the recording role.')
    if review.get('verdict')!='pass':raise ValueError('Only an explicit pass verdict can approve a commit.')
    checks=review.get('checks')
    if not isinstance(checks,list) or not checks:raise ValueError('The report needs concrete passing checks.')
    if any(not isinstance(c,dict) or c.get('status')!='pass' or not c.get('name') or not c.get('evidence') for c in checks):
        raise ValueError('All reported checks must pass and include name/evidence.')

def gate_record(args):
    root,sha,branch=clean_head()
    report=Path(args.report).resolve()
    data=report.read_bytes()
    validate_review(data,args.authority,sha)
    evidence={'authority':args.authority,'sha':sha,'branch':branch,'report':str(report),'report_sha256':hashlib.sha256(data).hexdigest(),'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    dest=gate_directory()/sha/(args.authority+'.json')
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(evidence,indent=2)+'\n');temp.replace(dest)
    print(json.dumps(evidence,indent=2))

def gate_check():
    root,sha,branch=clean_head()
    if not branch or branch in ['main','master']:raise ValueError('Detached HEAD and main/master pushes are prohibited.')
    if not re.fullmatch(r'(feat|fix|refactor|test|docs|chore|epic)/[a-zA-Z0-9._/-]+',branch):raise ValueError('Use a topic branch: feat/, fix/, refactor/, test/, docs/, chore/ or epic/.')
    records=[]
    for role in ['validator','chief']:
        path=gate_directory()/sha/(role+'.json')
        if not path.exists():raise ValueError(f'Missing {role} approval for {sha}.')
        record=json.loads(path.read_text())
        if record.get('sha')!=sha or record.get('branch')!=branch:raise ValueError(f'Stale {role} approval.')
        data=Path(record['report']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=record['report_sha256']:raise ValueError(f'{role} report changed after approval.')
        validate_review(data,role,sha)
        records.append(record)
    return root,sha,branch,records

def gate(args):
    if args.action=='record':gate_record(args);return
    root,sha,branch,records=gate_check()
    if args.action=='status':print(json.dumps({'sha':sha,'branch':branch,'approved':True,'reviews':records},indent=2));return
    remote=args.remote
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',remote):raise ValueError('Invalid remote name.')
    # Reject the remote default branch as well as local main/master. Query
    # before a push and fail closed if the default cannot be established.
    fetch_urls=git('remote','get-url','--all',remote,cwd=root).splitlines()
    push_urls=git('remote','get-url','--push','--all',remote,cwd=root).splitlines()
    if len(push_urls)!=1 or len(fetch_urls)!=1 or push_urls!=fetch_urls:
        raise ValueError('Multiple or different fetch/push destinations are unsupported; configure one explicit matching URL.')
    rewrites=subprocess.run(['git','config','--get-regexp',r'^url\..*\.(insteadof|pushinsteadof)$'],cwd=root,capture_output=True,text=True)
    if rewrites.returncode==0:raise ValueError('Git URL rewrites are unsupported by this gate; configure an explicit destination.')
    if rewrites.returncode!=1:raise ValueError('Cannot inspect Git URL rewrite configuration.')
    destination=push_urls[0]
    if destination.startswith('-'):raise ValueError('Invalid remote destination.')
    if destination in git('remote',cwd=root).splitlines():
        raise ValueError('A remote URL that names another configured remote is unsupported.')
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://',destination) and not re.match(r'^[^/@:]+@[^/:]+:',destination):
        local_path=(root/Path(destination).expanduser()).resolve()
        if not local_path.exists():raise ValueError('Local remote destination does not exist.')
        destination=str(local_path)
    refs=git('ls-remote','--symref',destination,'HEAD',cwd=root)
    match=re.search(r'^ref: refs/heads/(\S+)\s+HEAD$',refs,re.M)
    if not match:raise ValueError('Cannot establish remote default branch; no push performed.')
    if branch==match.group(1):raise ValueError('Pushing the remote default branch is prohibited.')
    # Catch local state changes during the remote lookup. Use the approved
    # object ID, not mutable HEAD, for the actual push.
    check=gate_check()
    if check[1:3]!=(sha,branch):raise ValueError('HEAD/branch changed while checking remote.')
    run(['git','push',destination,f'{sha}:refs/heads/{branch}'],cwd=root)
    print(f'Pushed approved commit {sha} to {remote}/{branch}.')

def sync(args):
    windows=WINDOWS
    if windows is None:
        print('No Windows profile configured (not WSL, or AGENT_TEAM_WINDOWS_HOME is none); nothing to synchronize.');return
    target=windows/'.agent-team'
    homes=[Path.home(),windows]
    frontmatter={}
    # Validate all managed role inputs before the first write, so a malformed
    # user-edited agent cannot leave synchronization partially applied.
    for home in homes:
        for role in ROLES:
            path=home/f'.claude/agents/{role}.md'
            if path.exists():
                match=re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)',path.read_text(),re.S)
                if not match:raise ValueError(f'Missing or malformed frontmatter: {path}')
                frontmatter[path]=match.group(1)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    # One install run shares one backup directory (AGENT_TEAM_BACKUP_STAMP) so --restore undoes all of it.
    backup_root=ROOT/'backups'/(os.environ.get('AGENT_TEAM_BACKUP_STAMP') or 'sync-'+stamp)
    created=[]
    def copy_file(src,dest):
        save_bytes(dest,src.read_bytes())
    def save_bytes(dest,data):
        if dest.exists():
            if dest.read_bytes()==data:return
            backup=backup_root/str(dest).lstrip('/')
            backup.parent.mkdir(parents=True,exist_ok=True)
            (ROOT/'backups').chmod(0o700)
            shutil.copy2(dest,backup)
        else:created.append(dest)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    def copy_tree(src,dest):
        for item in src.rglob('*'):
            if item.is_file():copy_file(item,dest/item.relative_to(src))
    # Copy owned content only; exclude backups, caches and personal installer.
    for name in ['UNIVERSAL.md','ROSTER.md','README.md','models.json','bootstrap-claude.txt','bootstrap-codex.txt','roles','skills','memory']:
        src=ROOT/name
        if src.is_dir():copy_tree(src,target/name)
        elif src.exists():
            copy_file(src,target/name)
    rules=(ROOT/'UNIVERSAL.md').read_text()
    for rules_file in (windows/'.claude/CLAUDE.md',windows/'.codex/AGENTS.md'):
        current=rules_file.read_text(encoding='utf-8-sig') if rules_file.is_file() else None
        save_bytes(rules_file,managed_rules(current,rules).encode())
    for home in homes:
        for role in ROLES:
            body=(ROOT/f'roles/{role}.md').read_text()
            claude=home/f'.claude/agents/{role}.md'
            if claude.exists():
                save_bytes(claude,('---\n'+frontmatter[claude]+'\n---\n\n'+body).encode())
            codex=home/f'.codex/agents/{role}.toml'
            if codex.exists():
                text=codex.read_text()
                text=re.sub(r'^developer_instructions = .*$',lambda _: 'developer_instructions = '+json.dumps(body),text,flags=re.M)
                save_bytes(codex,text.encode())
        for provider in [p for p in PROVIDERS if (Path.home()/f'.{p}').is_dir()]:
            base=home/('.claude/skills' if provider=='claude' else '.agents/skills')
            base.mkdir(parents=True,exist_ok=True)
            for src in (ROOT/'skills').iterdir():
                dest=base/src.name
                if home==Path.home():
                    if not dest.exists():dest.symlink_to(src,target_is_directory=True)
                else:copy_tree(src,dest)
    if created:
        backup_root.mkdir(parents=True,exist_ok=True)
        with open(backup_root/'CREATED.txt','a') as handle:handle.writelines(str(path)+'\n' for path in created)
    print('Synchronized shared rules, roles, skills and memory to Windows. WSL is the source of truth.')

# ---- doctor --------------------------------------------------------------

EXPECTED_ROLES = 12
EXPECTED_SKILLS = 120
RULES_MARKER = '# Universal engineering rules'
LOGIN_FIX = {'claude': 'run `claude`, then /login', 'codex': 'codex login', 'gh': 'gh auth login', 'coderabbit': 'coderabbit auth login'}
CLI_FIX = {'claude': 'curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh && bash /tmp/claude-install.sh', 'codex': 'npm install -g @openai/codex',
           'coderabbit': 'curl -fsSL https://cli.coderabbit.ai/install.sh -o /tmp/coderabbit-install.sh && sh /tmp/coderabbit-install.sh'}
PACKAGES = {'brew': {'python3': 'python', 'git': 'git', 'tmux': 'tmux', 'gh': 'gh'},
            'apt-get': {'python3': 'python3', 'git': 'git', 'tmux': 'tmux', 'gh': 'gh'},
            'dnf': {'python3': 'python3', 'git': 'git', 'tmux': 'tmux', 'gh': 'gh'},
            'pacman': {'python3': 'python', 'git': 'git', 'tmux': 'tmux', 'gh': 'github-cli'}}
INSTALL = {'brew': 'brew install {}', 'apt-get': 'sudo apt-get install -y {}', 'dnf': 'sudo dnf install -y {}', 'pacman': 'sudo pacman -S --needed {}'}

def uname(flag):
    # Ask the PATH's uname (not the interpreter) so the platform seen here matches install.sh.
    try:return subprocess.run(['uname',flag],capture_output=True,text=True,timeout=5).stdout.strip()
    except (OSError,subprocess.SubprocessError):return platform.system() if flag=='-s' else platform.release()

def wsl_detected():
    flag=os.environ.get('AGENT_TEAM_WSL')
    if flag in ('0','1'):return flag=='1'
    return bool(os.environ.get('WSL_DISTRO_NAME')) or 'microsoft' in uname('-r').lower()

def package_manager():
    if uname('-s')=='Darwin':return 'brew'
    return next((pm for pm in ('apt-get','dnf','pacman') if shutil.which(pm)),None)

def install_hint(tool):
    pm=package_manager()
    if pm is None:return f'install {tool} with your system package manager'
    return INSTALL[pm].format(PACKAGES[pm][tool])

def cli_output(argv,timeout=20):
    """(exit code, stdout+stderr) of a read-only probe; (None, '') when it cannot run."""
    try:
        result=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
        return result.returncode,result.stdout+result.stderr
    except (OSError,subprocess.SubprocessError):return None,''

def plugin_enabled(text,name):
    """True when `<cli> plugin list` output shows NAME and at least one entry of it is not disabled."""
    lines=text.splitlines();found=False
    for i,line in enumerate(lines):
        if name not in line:continue
        entry=[line]
        for follow in lines[i+1:i+6]:
            if '@' in follow:break
            entry.append(follow)
        if not re.search(r'disabled',' '.join(entry)):found=True
    return found

def doctor_checks():
    """Read-only environment report: a list of {name, status(ok|warn|fail|n/a), detail, fix}."""
    home=Path.home();root=home/'.agent-team';rows=[]
    def add(name,status,detail,fix=None):rows.append({'name':name,'status':status,'detail':detail,'fix':fix})
    installer='run ./install.sh from your AI-Setup checkout'
    system={'Darwin':'macOS','Linux':'Linux'}.get(uname('-s'),uname('-s') or 'unknown')
    if system=='Linux' and wsl_detected():system='Linux (WSL)'
    pm=package_manager()
    add('os',  'ok',f'{system}, package manager: {pm or "none detected"}')
    version='.'.join(map(str,sys.version_info[:3]))
    if sys.version_info>=(3,9):add('python','ok',f'{version} (3.9+ required)')
    else:add('python','fail',f'{version}; 3.9+ required',install_hint('python3'))
    for tool in ('git','tmux'):
        path=shutil.which(tool)
        add(tool,'ok' if path else 'fail',path or 'not found',None if path else install_hint(tool))
    if shutil.which('gh'):
        code,_=cli_output(['gh','auth','status'])
        add('gh','ok' if code==0 else 'warn',shutil.which('gh')+('' if code==0 else ' (not logged in)'),None if code==0 else LOGIN_FIX['gh'])
    else:add('gh','fail','not found',install_hint('gh'))
    if shutil.which('coderabbit'):
        code,out=cli_output(['coderabbit','auth','status'])
        # `coderabbit auth status` exits 0 even when signed out, so read the text too.
        logged=code==0 and not re.search(r'signed out|logged out|not (?:logged|signed) in|unauthenticated',out,re.I)
        add('coderabbit','ok' if logged else 'warn',shutil.which('coderabbit')+('' if logged else ' (not logged in)'),None if logged else LOGIN_FIX['coderabbit'])
    else:add('coderabbit','fail','not found',CLI_FIX['coderabbit'])
    present=[]
    for provider in PROVIDERS:
        try:exe=executable(provider)
        except ValueError:exe=None
        if not exe:
            add(provider,'warn','not found (optional if the other provider is installed)',CLI_FIX[provider]);continue
        present.append(provider)
        code,out=cli_output([exe,'--version']);first=(out.strip().splitlines() or ['version unknown'])[0]
        add(provider,'ok',f'{first} ({exe})')
        if provider=='claude':logged=cli_output([exe,'auth','status'])[0]==0
        else:logged=(home/'.codex/auth.json').is_file() or bool(os.environ.get('OPENAI_API_KEY'))   # file check: no process that could prompt
        add(f'{provider} login','ok' if logged else 'warn','logged in' if logged else 'not logged in',None if logged else LOGIN_FIX[provider])
    if not present:
        for row in rows:
            if row['name'] in PROVIDERS:row['status']='fail'
    # Plugins: ECC through the CLI's plugin system; CCPM is a skill (or a plugin).
    ecc={}
    for provider in present:
        exe=executable(provider)
        code,out=cli_output([exe,'plugin','list'])
        ecc[provider]=plugin_enabled(out,'ecc@ecc')
        ecc[provider+':ccpm']='ccpm' in out.lower()
    anywhere=any(ecc.get(p) for p in present)
    for provider in present:
        fix={'claude':'claude plugin marketplace add affaan-m/ECC && claude plugin install ecc@ecc --scope user',
             'codex':'codex plugin marketplace add affaan-m/ECC && codex plugin add ecc@ecc'}[provider]
        add(f'ecc ({provider})','ok' if ecc[provider] else ('warn' if anywhere else 'fail'),'ECC plugin installed' if ecc[provider] else 'ECC plugin not installed',None if ecc[provider] else fix)
    ccpm_skill=any((home/d/'ccpm/SKILL.md').is_file() for d in ('.claude/skills','.agents/skills'))
    ccpm_plugin=any(ecc.get(p+':ccpm') for p in present)
    add('ccpm','ok' if ccpm_skill or ccpm_plugin else 'fail','CCPM skill available' if ccpm_skill else ('CCPM plugin available' if ccpm_plugin else 'CCPM skill not installed'),
        None if ccpm_skill or ccpm_plugin else f'{installer} (fetches CCPM from github.com/automazeio/ccpm); plugin: claude plugin install ccpm')
    # Installed package.
    needed=['team.py','build_setup.py','install_launchers.py','cli-shim','models.json','UNIVERSAL.md','ROSTER.md','bootstrap-claude.txt','bootstrap-codex.txt']
    missing=[n for n in needed if not (root/n).is_file()]
    add('~/.agent-team','fail' if missing else 'ok',('missing: '+', '.join(missing)) if missing else f'{len(needed)} package files present',installer if missing else None)
    roles_root=len([r for r in ROLES if (root/f'roles/{r}.md').is_file()])
    add('roles (shared)','ok' if roles_root==EXPECTED_ROLES else 'fail',f'{roles_root}/{EXPECTED_ROLES} in ~/.agent-team/roles',None if roles_root==EXPECTED_ROLES else installer)
    skills_root=sorted(d.name for d in (root/'skills').glob('team-*') if (d/'SKILL.md').is_file()) if (root/'skills').is_dir() else []
    add('skills (shared)','ok' if len(skills_root)==EXPECTED_SKILLS else 'fail',f'{len(skills_root)}/{EXPECTED_SKILLS} in ~/.agent-team/skills',None if len(skills_root)==EXPECTED_SKILLS else installer)
    for provider in (present or list(PROVIDERS)):
        agents=home/('.claude/agents' if provider=='claude' else '.codex/agents');ext='md' if provider=='claude' else 'toml'
        gone=[r for r in ROLES if not (agents/f'{r}.{ext}').is_file()]
        add(f'roles ({provider})','ok' if not gone else 'fail',f'{len(ROLES)-len(gone)}/{EXPECTED_ROLES} in {agents}'+('' if not gone else '; missing '+', '.join(gone)),None if not gone else installer)
        skills=home/('.claude/skills' if provider=='claude' else '.agents/skills')
        linked=sorted(d.name for d in skills.glob('team-*') if (d/'SKILL.md').is_file()) if skills.is_dir() else []
        gone=sorted(set(skills_root)-set(linked)) if skills_root else []
        add(f'skills ({provider})','ok' if len(linked)==EXPECTED_SKILLS else 'fail',f'{len(linked)}/{EXPECTED_SKILLS} in {skills}'+('' if len(gone)>5 or not gone else '; missing '+', '.join(gone)),None if len(linked)==EXPECTED_SKILLS else installer)
        rules=home/('.claude/CLAUDE.md' if provider=='claude' else '.codex/AGENTS.md')
        ok=rules.is_file() and RULES_BEGIN in rules.read_text(errors='replace')
        add(f'rules ({provider})','ok' if ok else 'fail',f'{rules}'+('' if ok else ' is missing or has no AGENT TEAM rules block'),None if ok else installer)
    # Launchers.
    binpath=home/'.local/bin'
    absent=[n for n in ('agent-team','claude-team','codex-team') if not os.access(binpath/n,os.X_OK)]
    if absent:add('launchers','fail','missing in ~/.local/bin: '+', '.join(absent),installer)
    else:
        on_path=str(binpath) in os.environ.get('PATH','').split(os.pathsep)
        add('launchers','ok' if on_path else 'fail',f'{binpath} '+('is on PATH' if on_path else 'is NOT on PATH'),None if on_path else 'open a new terminal (install.sh added the PATH line to your shell rc) or run: export PATH="$HOME/.local/bin:$PATH"')
    marked=[f for f in ('.bashrc','.zshrc','.bash_profile') if (home/f).is_file() and 'BEGIN PERSONAL AGENT TEAM' in (home/f).read_text(errors='replace')]
    add('shell rc','ok' if marked else 'warn',('managed block in '+', '.join(marked)) if marked else 'no managed block in .bashrc/.zshrc/.bash_profile',None if marked else installer)
    # Windows mirror: WSL only.
    try:recorded=(root/'windows-target').read_text().strip()
    except OSError:recorded=None
    configured=os.environ.get('AGENT_TEAM_WINDOWS_HOME')
    if recorded=='none':add('windows mirror','n/a','skipped when installed (--no-windows, --home or not WSL)')
    elif recorded is None and not wsl_detected() and configured in (None,'','none'):add('windows mirror','n/a','not WSL: no Windows side to check')
    else:
        win=Path(recorded) if recorded else windows_home()
        if win is None:add('windows mirror','warn','Windows profile not detected (cmd.exe/wslpath unavailable)','set AGENT_TEAM_WINDOWS_HOME=/mnt/c/Users/<you> and re-run ./install.sh')
        else:
            wanted=['.agent-team/bin/claude-team.cmd','.agent-team/bin/codex-team.cmd','.agent-team/windows-team.ps1','.agent-team/windows-profile.ps1','.agent-team/wsl-target.json']
            if 'claude' in (present or PROVIDERS):wanted.append('.claude/CLAUDE.md')
            if 'codex' in (present or PROVIDERS):wanted.append('.codex/AGENTS.md')
            gone=[w for w in wanted if not (win/w).is_file()]
            add('windows mirror','fail' if gone else 'ok',('missing: '+', '.join(Path(g).name for g in gone)) if gone else f'{len(wanted)} files present in {win}',installer if gone else None)
    return rows

def doctor(args):
    rows=doctor_checks()
    failed=[r for r in rows if r['status']=='fail'];warned=[r for r in rows if r['status']=='warn']
    ok=not failed and not (args.strict and warned)
    if args.json:
        print(json.dumps({'ok':ok,'failed':len(failed),'warnings':len(warned),'checks':rows},indent=2))
    else:
        width=max(len(r['name']) for r in rows)
        print(f'{"STATUS":<7} {"CHECK":<{width}}  DETAIL')
        for r in rows:print(f'{r["status"]:<7} {r["name"]:<{width}}  {r["detail"]}')
        fixes=[r for r in rows if r['fix']]
        if fixes:
            print('\nFix:')
            for r in fixes:print(f'  {r["name"]}: {r["fix"]}')
        print(f'\nResult: {"PASS" if ok else "FAIL"} ({len(failed)} failed, {len(warned)} warnings)')
    raise SystemExit(0 if ok else 1)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='op',required=True)
    l=sub.add_parser('launch');l.add_argument('provider',choices=['claude','codex']);l.add_argument('--role',choices=ROLES,default='chief');l.add_argument('-C','--directory',default=os.getcwd());l.add_argument('--no-tmux',action='store_true');l.add_argument('--dry-run',action='store_true');l.add_argument('prompt',nargs='*');l.set_defaults(func=launch)
    w=sub.add_parser('worktree');w.add_argument('role');w.add_argument('task');w.add_argument('--kind',choices=['feat','fix','refactor','test','docs','chore'],default='feat');w.add_argument('--base',default='HEAD');w.set_defaults(func=worktree)
    g=sub.add_parser('gate');gs=g.add_subparsers(dest='action',required=True)
    r=gs.add_parser('record');r.add_argument('authority',choices=['validator','chief']);r.add_argument('--report',required=True)
    gs.add_parser('status');ps=gs.add_parser('push');ps.add_argument('--remote',default='origin');g.set_defaults(func=gate)
    s=sub.add_parser('sync');s.set_defaults(func=sync)
    sp=sub.add_parser('spawn',help='open a teammate pane in the current team session');sp.add_argument('role');sp.add_argument('--task');sp.add_argument('-C','--directory',default=os.getcwd());sp.add_argument('--provider',choices=PROVIDERS);sp.add_argument('prompt',nargs='*');sp.set_defaults(func=spawn)
    sd=sub.add_parser('send',help='write a mailbox message and notify the target pane');sd.add_argument('target');sd.add_argument('--from',dest='sender');sd.add_argument('message',nargs='+');sd.set_defaults(func=send)
    ib=sub.add_parser('inbox',help='print unread mailbox messages and mark them read');ib.add_argument('--role');ib.set_defaults(func=inbox)
    dv=sub.add_parser('_deliver',help=argparse.SUPPRESS);dv.add_argument('--pane',required=True);dv.add_argument('--line',required=True);dv.set_defaults(func=deliver)
    dc=sub.add_parser('doctor',help='check this machine and the install; exit 1 on any failure');dc.add_argument('--json',action='store_true');dc.add_argument('--strict',action='store_true',help='treat warnings as failures');dc.set_defaults(func=doctor)
    sub.add_parser('panes',help='show registered team panes with live/dead status').set_defaults(func=panes)
    a=p.parse_args()
    try:a.func(a)
    except (ValueError,OSError,subprocess.CalledProcessError,json.JSONDecodeError) as e:
        print(f'agent-team: {e}',file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
