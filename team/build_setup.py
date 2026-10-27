#!/usr/bin/env python3
"""Generate the shared team package and apply backed-up user config.

Usage: build_setup.py [--dry-run] [--package-from TEAM_DIR] [--restore TIMESTAMP]

Everything is relative to the install home ($HOME; install.sh --home DIR exports
HOME=DIR). Environment:
  AGENT_TEAM_WINDOWS_HOME  Windows profile dir as seen from WSL, or "none" to disable
                           the mirror (default: auto-detected on WSL, none elsewhere)
  AGENT_TEAM_WSL           "1"/"0" forces/denies WSL detection
  AGENT_TEAM_PROVIDERS     comma list (claude,codex) overriding installed-CLI detection
  AGENT_TEAM_CCPM_REPO     git URL/path used when CCPM must be fetched
  AGENT_TEAM_BACKUP_STAMP  backup directory name shared by one install run
Every changed file is copied to <home>/.agent-team/backups/<stamp>/ first.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, datetime
try: import tomllib
except ImportError: tomllib = None   # Python < 3.11: skip optional TOML validation

def is_wsl():
    flag = os.environ.get('AGENT_TEAM_WSL')
    if flag in ('0', '1'): return flag == '1'
    if os.environ.get('WSL_DISTRO_NAME'): return True
    try: return 'microsoft' in Path('/proc/version').read_text().lower()
    except OSError: return False

def windows_home():
    """Windows profile as a Linux path (WSL only), or None. Mirrors team.windows_home."""
    value = os.environ.get('AGENT_TEAM_WINDOWS_HOME')
    if value is not None:
        return None if value.strip().lower() in ('', 'none') else Path(value)
    if not is_wsl(): return None
    try:
        out = subprocess.run(['cmd.exe', '/c', 'echo %USERPROFILE%'], capture_output=True, text=True, timeout=15,
                             cwd='/mnt/c' if Path('/mnt/c').is_dir() else None).stdout
        lines = [x.strip() for x in out.replace('\r', '\n').split('\n') if x.strip()]
        path = subprocess.run(['wslpath', '-u', lines[-1]], capture_output=True, text=True, timeout=15).stdout.strip()
        return Path(path) if path.startswith('/') and Path(path).parent.is_dir() else None
    except (OSError, IndexError, subprocess.SubprocessError):
        return None

LINUX = Path.home()
ROOT = LINUX / '.agent-team'
WINDOWS = windows_home()
STAMP = os.environ.get('AGENT_TEAM_BACKUP_STAMP') or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = ROOT / 'backups' / STAMP

DRY = False       # --dry-run: plan and print, write nothing
PLANNED = {}      # dry-run overlay: path -> bytes that would have been written
CHANGES = []      # (kind, path) for every applied or planned change
CREATED = []      # files this run created (a restore removes them again)
KEPT = []         # package files left alone because the user edited them
WARNINGS = []
NOTES = []        # one-line notices printed after the change list
YOLO_MARKER_TEXT = 'Written by install.sh --yolo (or install.ps1 -Yolo). While this file exists, agents run with permission prompts skipped (Claude bypassPermissions, Codex danger-full-access). Turn it off with ./install.sh --no-yolo.\n'
CCPM_REF = '7d7e4623bc6d4c0c9ba66ca6bfecd7e5261dc697'   # pinned CCPM commit; override with AGENT_TEAM_CCPM_REF

def reset():
    global DRY
    DRY = False
    for item in (PLANNED, CHANGES, CREATED, KEPT, WARNINGS, NOTES): item.clear()

def warn(message):
    WARNINGS.append(message); print('WARN: ' + message)

def note(kind, path):
    CHANGES.append((kind, str(path)))

def slurp(path):
    """Read text as the install would see it, including dry-run planned writes."""
    path = Path(path)
    return (PLANNED[path] if path in PLANNED else path.read_bytes()).decode('utf-8-sig')

def present(path):
    return Path(path) in PLANNED or os.path.lexists(path)

def backup(path):
    dest = BACKUP / str(path).lstrip('/')
    if dest.exists() or not Path(path).is_file(): return
    dest.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'backups').chmod(0o700)
    shutil.copy2(path, dest)

def write_bytes(path, data, executable=False):
    path = Path(path)
    if path in PLANNED: current = PLANNED[path]
    else:
        try: current = path.read_bytes() if path.is_file() else None
        except OSError: current = None
    if current is not None and current.lstrip(b'\xef\xbb\xbf') == data.lstrip(b'\xef\xbb\xbf'):
        if executable and not DRY and not os.access(path, os.X_OK): path.chmod(0o755)
        return False
    note('update' if current is not None else 'create', path)
    if DRY:
        PLANNED[path] = data
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    if current is not None: backup(path)
    else: CREATED.append(path)
    path.write_bytes(data)
    if executable: path.chmod(0o755)
    return True

def write(path, text, executable=False):
    return write_bytes(path, text.encode('utf-8'), executable)

def remove(path):
    """Delete a file or link we manage, keeping a backup of regular files."""
    path = Path(path)
    if not present(path): return
    note('remove', path)
    if DRY:
        PLANNED.pop(path, None); return
    if path.is_file() and not path.is_symlink(): backup(path)
    path.unlink()

def seed(path,text):
    """Initial templates never replace authored learning/configuration."""
    if not present(path):write(path,text)

def link(dest, target):
    """Create a symlink unless something (even a dangling link) already sits there."""
    dest = Path(dest)
    if present(dest): return
    note('link', dest)
    if DRY:
        PLANNED[dest] = b''; return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(target, target_is_directory=Path(target).is_dir())
    CREATED.append(dest)

def copy_tree(src, dest):
    for item in sorted(Path(src).rglob('*')):
        if item.is_file() and item.name != '.DS_Store': write_bytes(Path(dest) / item.relative_to(src), item.read_bytes())

def finish():
    """Persist the created-file journal that --restore uses to undo a fresh install."""
    if DRY or not CREATED: return
    journal = BACKUP / 'CREATED.txt'
    journal.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'backups').chmod(0o700)
    seen = set(journal.read_text().splitlines()) if journal.exists() else set()
    with open(journal, 'a') as handle:
        for path in CREATED:
            if str(path) not in seen: handle.write(str(path) + '\n')
    CREATED.clear()

def group(path):
    path = str(path)
    for marker in ('/skills/', '/.claude/skills/', '/.agents/skills/'):
        if marker in path: return path.split(marker)[0] + marker + '*'
    return path

def report(prefix=''):
    """Print every change (skill files grouped) and a one-line summary."""
    counts = {}
    for kind, path in CHANGES: counts.setdefault((kind, group(path)), []).append(path)
    verb = 'would ' if DRY else ''
    for (kind, path), items in sorted(counts.items()):
        print(f'  {verb}{kind}: {path}' + (f'  ({len(items)} files)' if len(items) > 1 else ''))
    for rel in KEPT: print(f'  kept (locally modified, not overwritten): {rel}')
    for line in NOTES: print('  note: ' + line)
    log = os.environ.get('AGENT_TEAM_CHANGE_LOG')   # install.sh sums these and prints one overall summary
    if log:
        with open(log, 'a') as handle: handle.write(f'{len(CHANGES)}\n')
    if not CHANGES:
        if not log: print(prefix + 'No changes needed.')
    else:
        print(prefix + f'{len(CHANGES)} change(s) {"planned" if DRY else "applied"}.' + ('' if DRY else f' Backup: {BACKUP}'))

def installed_providers():
    """Providers to configure: AGENT_TEAM_PROVIDERS, else CLIs/config dirs found, else both."""
    forced = os.environ.get('AGENT_TEAM_PROVIDERS')
    if forced: return [p for p in forced.replace(',', ' ').split() if p in ('claude', 'codex')]
    found = [p for p in ('claude', 'codex') if shutil.which(p) or (LINUX / f'.{p}').is_dir()]
    return found or ['claude', 'codex']

def ensure_ccpm():
    """Locate CCPM's skill directory, cloning it under the install root when absent."""
    for base in (LINUX / 'ccpm', ROOT / 'vendor/ccpm'):
        if present(base / 'skill/ccpm'): return base / 'skill/ccpm'
    repo = os.environ.get('AGENT_TEAM_CCPM_REPO', 'https://github.com/automazeio/ccpm.git')
    target = ROOT / 'vendor/ccpm'
    if DRY:
        note('clone', f'{repo} -> {target}')
        return target / 'skill/ccpm'
    if not shutil.which('git'):
        warn('git is missing: cannot fetch CCPM'); return None
    ref = os.environ.get('AGENT_TEAM_CCPM_REF', CCPM_REF)
    try:
        target.mkdir(parents=True, exist_ok=True)
        steps = [['git', 'init', '-q'], ['git', 'fetch', '-q', '--depth', '1', repo, ref], ['git', 'checkout', '-q', 'FETCH_HEAD']]
        for step in steps:
            result = subprocess.run(step, capture_output=True, text=True, timeout=180, cwd=str(target))
            if result.returncode != 0: break
    except (OSError, subprocess.SubprocessError) as error:
        warn(f'CCPM fetch failed ({error}); run: git clone {repo} {target} && git -C {target} checkout {ref}'); return None
    if result.returncode != 0 or not (target / 'skill/ccpm').is_dir():
        shutil.rmtree(target, ignore_errors=True)
        warn(f'CCPM fetch of {ref[:12]} failed; run: git clone {repo} {target} && git -C {target} checkout {ref}'); return None
    shutil.rmtree(target / '.git', ignore_errors=True)   # a plain copy of the skill, no VCS metadata
    note('clone', f'{repo} -> {target}')
    CREATED.append(target)
    return target / 'skill/ccpm'

# Files that carry behaviour, not user-authored learning: refreshed on every install.
CODE_FILES = {'team.py', 'build_setup.py', 'install_launchers.py', 'cli-shim', 'windows-profile.ps1', 'windows-team.ps1', 'install.ps1'}
EXECUTABLE = {'team.py', 'build_setup.py', 'install_launchers.py', 'cli-shim'}
PACKAGE_SKIP = {'__pycache__', '.DS_Store', 'backups', 'memory', 'state', 'vendor'}

def copy_package(source):
    """Copy the repo's team/ package (+ ../install.ps1) into ROOT.

    Code is refreshed. Content (rules, roles, skills, prompts, models.json) is refreshed only
    when the installed file is still exactly what a previous install wrote, so a file you edited
    or that an agent taught something new is never replaced (it is reported as kept)."""
    source = Path(source).resolve()
    state_path = ROOT / '.install.json'
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    hashes = state.get('files', {})
    files = {}
    for item in sorted(source.rglob('*')):
        rel = item.relative_to(source)
        if item.is_file() and not (set(rel.parts) & PACKAGE_SKIP) and item.suffix != '.pyc': files[rel.as_posix()] = item
    if (source.parent / 'install.ps1').is_file(): files['install.ps1'] = source.parent / 'install.ps1'
    for rel, item in files.items():
        data = item.read_bytes()
        dest = ROOT / rel
        digest = hashlib.sha256(data).hexdigest()
        if present(dest):
            current = hashlib.sha256(PLANNED[dest] if dest in PLANNED else dest.read_bytes()).hexdigest()
            if current != digest and rel not in CODE_FILES and hashes.get(rel) != current:
                KEPT.append(rel); continue
        write_bytes(dest, data, executable=rel in EXECUTABLE)
        hashes[rel] = digest
    if not DRY:
        new = {'files': hashes}
        if new != state: write(state_path, json.dumps(new, indent=2, sort_keys=True) + '\n')

def restore(stamp):
    """Put back every file saved under backups/<stamp>/ and remove files that install created."""
    src = ROOT / 'backups' / stamp
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z', stamp or ''): raise SystemExit(f'Invalid backup name {stamp!r}: expected a timestamp like 20260101T120000Z')
    if not src.is_dir(): raise SystemExit(f'No such backup: {src}')
    undo = ROOT / 'backups' / ('restore-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    def keep(path):
        if DRY or not Path(path).is_file(): return
        dest = undo / str(path).lstrip('/'); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
    for item in sorted(src.rglob('*')):
        if item.is_file() and item.name != 'CREATED.txt':
            target = Path('/') / item.relative_to(src)
            print(f'  {"would restore" if DRY else "restore"}: {target}')
            if not DRY: keep(target); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(item, target)
    journal = src / 'CREATED.txt'
    for line in (journal.read_text().splitlines() if journal.exists() else []):
        target = Path(line)
        if os.path.lexists(target):
            print(f'  {"would remove" if DRY else "remove"} (created by install): {target}')
            if not DRY:
                keep(target)
                if target.is_symlink() or target.is_file(): target.unlink()
                elif target.is_dir(): shutil.rmtree(target)
    print(('Dry run: nothing restored.' if DRY else f'Restored backup {stamp}. Previous state saved in {undo}.'))

ROLES = {
 'chief': ('Chief — Orchestrator', 'Owns planning, delegation, scope, user interaction, and final local approval.',
  'Turn an app idea into a detailed, reviewable delivery plan. Explain user journeys, scope and non-goals, architecture choices and alternatives, data ownership, repository tree, contracts, milestones, task dependencies, agents, validation, rollback, risks, and unresolved decisions. Wait for explicit plan approval before provisioning repositories, creating issues, or launching builders. Immediately run `agent-team spawn validator` (its own tmux pane), wait for its acknowledgement with `agent-team inbox`, and keep it addressable; open every later agent the same way, never as an in-process subagent. After approval, assign exclusive file ownership, topic branches and worktrees; use CCPM to track PRD → epic → tasks → issues. Resolve collisions, integrate verified changes, and communicate meaningful progress. You are the only agent that talks to the user: Validator and workers send questions and blockers to you with `agent-team send chief`, and you relay them. Split the approved plan into user-testable increments and deliver one at a time: finish, verify (tests, Validator, live check), hand the user what changed, exact how-to-test steps and the running demo URL with stop instructions, then wait for feedback or a go-ahead before the next increment. Start no autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly asks. You approve a push only after Validator approves the exact commit. Merge authority follows the user’s explicit delegation; by default present a ready PR and wait for user merge approval.',
  [
   ('project-plan','Specify journeys, non-goals, alternatives, architecture, tree, milestones, dependency graph, acceptance criteria, budget and rollback. Present concrete decisions for approval. Split the plan into user-testable increments, each stating what changes, how the user tests it and the demo URL or stop steps, and name which increment is next. Autonomy applies only inside the approved increment.','Approved plan with ordered user-testable increments and unresolved decisions recorded.'),
   ('team-bootstrap','Run `agent-team spawn validator` (own tmux pane, senior model, high effort) before any other work; Validator sends its acknowledgement on startup; check `agent-team inbox` and confirm the pane with `agent-team panes` for at most about 5 minutes, then report degraded mode to the user instead of waiting or looping indefinitely. Spawn builders only after plan approval. Never use in-process or native subagent tools for team roles; read-only in-process search helpers for lookups are fine.','Live Validator pane id and its acknowledgement from the inbox.'),
   ('ccpm-delivery','Map approved requirements to a PRD, technical epic, dependency-aware tasks and linked GitHub issues. Apply user worktree and commit conventions over conflicting CCPM defaults.','PRD-to-issue traceability and ordered work queue.'),
   ('ownership-map','Assign one owner per file or module, explicit integration boundaries and dependency contracts. Reserve shared files for Integrator.','Ownership table with collision handling.'),
   ('agent-selection','Choose the smallest sufficient specialist set and concurrency. Explain a missing capability before creating a new role; give it narrow outputs and skills. Open each agent with `agent-team spawn <role> --task <task> -C <worktree>`, using only agents of the team provider; the window re-tiles automatically and overflows to a new window past AGENT_TEAM_MAX_PANES.','Role hierarchy with capability justification and the spawn command for each agent.'),
   ('feature-mode','For an existing app, inspect architecture and current behavior, propose a scoped feature plan and compatibility checks, then wait for approval.','Approved feature delta and migration strategy.'),
   ('progress-steering','Report completed outcomes, next action and blockers; you are the single point of contact, so relay worker and Validator questions to the user. After each increment, verify it, then hand the user what changed, the demo URL if any, plus how-to-test and stop steps, and wait for feedback or a go-ahead before starting the next. Incorporate user corrections into the active plan and agent assignments without restarting completed work. Start no autonomous loops unless the user explicitly asks.','Increment handoff (changes, demo URL if any, plus how-to-test and stop steps) and the updated plan.'),
   ('push-approval','Compare exact HEAD, tests, CodeRabbit findings, Validator verdict and diff scope. Record Chief approval for that SHA; invalidate it on any new commit.','Chief push approval tied to exact SHA.'),
   ('merge-handoff','Present issue, PR, exact reviewed SHA, verification and rollback to the user. Merge only after explicit user approval or an existing clear merge delegation.','Reviewable PR and recorded merge authority.'),
   ('preference-learning','Capture explicit user corrections as dated preferences with provenance and scope; record inferred habits as tentative and expire contradicted ones.','Sanitized preference update and disclosed learning.')]),
 'validator': ('Validator — Independent Gatekeeper','Independently verifies every agent’s code, tests, review evidence and integration before push or merge.',
  'Challenge implementation using repository evidence rather than author claims. Read the approved plan and specs; reproduce bugs, inspect diffs and run focused tests plus relevant integration checks. Review security, performance, API compatibility, data safety and missing tests. Run CodeRabbit local CLI review, interpret findings rather than trusting exit status, and require all security/performance issues resolved or explicitly dispositioned by Chief. Never silently patch code you are approving: send findings to the owner and re-review its fix. Record pass/fail, exact SHA, commands, results and residual risk. Any code change invalidates previous approval. Stay available in your pane for Chief messages (read them with `agent-team inbox`, answer with `agent-team send chief`, and acknowledge your first message); approval is a local quality decision and does not grant merge authority. On startup, immediately send Chief an acknowledgement with `agent-team send chief` stating your role, model, effort and pwd. Report to Chief only: send verdicts, questions and blockers with `agent-team send chief` and never ask the user directly.',
  [
   ('acceptance-audit','Translate each approved acceptance criterion into observable evidence. Identify missing coverage before evaluating the implementation.','Criterion-to-evidence matrix.'),
   ('independent-diff','Inspect changed paths and call sites against base; locate behavior regressions and scope creep. Do not rely on author summaries.','Prioritized findings with path and reproduction.'),
   ('atomic-test-review','Check that each commit has focused behavior coverage, regressions fail on the old implementation, and assertions test outcomes.','Per-commit test evidence and gaps.'),
   ('coderabbit-gate','Run coderabbit review --agent --base <base> locally. Inspect structured findings; a successful command is not proof of a clean review. Handle authentication failure as pending.','Recorded review command, findings and dispositions.'),
   ('security-verification','Trace changed inputs through authorization, validation, storage and output; exercise permission denials and injection boundaries.','Concrete security findings or verified protections.'),
   ('performance-verification','Measure representative workloads before and after with comparable inputs and environment; investigate materially worse latency or resource use.','Reproducible comparison with limits.'),
   ('integration-verification','Validate frontend/backend contracts, migrations and shared modules on the integrated commit, including failure paths.','Integration result tied to SHA.'),
   ('live-verification','Start HTTP services on 0.0.0.0, curl health and a real feature route, report localhost/WSL URLs and stop instructions. For TUIs use a PTY session, not fictitious HTTP checks.','Observed runtime behavior and exact access details.'),
   ('sha-verdict','Record validator verdict for exact HEAD with commands, review outcomes and remaining risks. Refuse stale evidence after any commit.','Machine-readable verdict for current SHA.'),
   ('review-learning','Record recurring defects and user review corrections as scoped review checks; remove outdated checks and avoid speculative blanket rules.','Evidence-backed review checklist update.')]),
 'architect': ('Architect — System Designer','Designs module boundaries, contracts, repository structure, migrations and technical decisions.',
  'Convert product requirements into coherent system boundaries with practical complexity. Inspect existing architecture before introducing abstractions. Own contracts and design artifacts, not unrelated implementation. Compare options using concrete constraints, specify failure modes and versioning, and provide builders with measurable interface contracts. Review architecture drift at integration and keep ARCHITECTURE.md accurate.',
  [
   ('boundary-map','Map modules, responsibilities, dependency direction and runtime trust boundaries. Identify cyclic dependencies.','System boundary map.'),
   ('repo-tree','Propose a repository tree aligned with the chosen framework, test locations and ownership; avoid speculative layers.','Annotated directory plan.'),
   ('api-contracts','Specify request/response shapes, validation, error codes, auth requirements and versioning with examples.','Implementable API contract.'),
   ('domain-model','Define entities, invariants, aggregates and state transitions from actual user workflows.','Domain model and invariants.'),
   ('architecture-decisions','Compare viable alternatives, constraints and tradeoffs; write a concise dated decision with revisit conditions.','Architecture decision record.'),
   ('migration-design','Plan expand/contract changes, compatibility windows, data checks and local rollback before implementation.','Migration and rollback design.'),
   ('dependency-design','Choose minimal dependencies using installed versions and maintained official docs; explain lifecycle and licensing implications.','Dependency decision and constraints.'),
   ('failure-design','Specify timeouts, retry limits, idempotency and degraded behavior across component boundaries.','Failure-mode contract.'),
   ('integration-plan','Order contract, backend and frontend work; reserve shared files and define staging checkpoints.','Integration dependency graph.'),
   ('architecture-learning','Record proven design patterns and failed assumptions with context; revise future architecture preferences when evidence changes.','Scoped architecture memory.')]),
 'product': ('Product — Requirements & Experience','Owns PRDs, user journeys, feature scope, acceptance criteria and usability decisions.',
  'Clarify what users need and what success looks like. Convert vague app ideas into concrete workflows, accessible experiences and testable acceptance criteria. Distinguish explicit user preferences from assumptions. Partner with Chief on plans and Architect on feasibility, keeping scope controlled. Validate real behavior and copy rather than inventing demand or metrics.',
  [
   ('prd-writing','Describe target users, problem, journeys, scope, non-goals, requirements and measurable acceptance criteria.','Reviewable PRD.'),
   ('journey-mapping','Trace entry, happy path, interruptions, recovery and completion for each important user journey.','Journey map with edge cases.'),
   ('acceptance-criteria','Write observable Given/When/Then outcomes including failure and accessibility behavior.','Testable acceptance criteria.'),
   ('scope-prioritization','Rank features by user value, dependencies and cost; mark must-have versus deferred work explicitly.','Prioritized scope list.'),
   ('interaction-spec','Define control behavior, focus, keyboard navigation, validation and feedback for each screen.','Interaction specification.'),
   ('empty-error-copy','Write useful loading, empty, validation and error states that suggest the next action.','State inventory and product copy.'),
   ('feature-discovery','Inspect the current app, identify the requested behavioral delta and avoid redesigning adjacent flows.','Feature brief grounded in current behavior.'),
   ('usability-review','Exercise primary journeys with realistic inputs, record friction and propose targeted changes.','Usability findings and reproduction steps.'),
   ('release-notes','Describe shipped behavior and migration steps in user language; link issues and avoid claiming unfinished work.','Accurate release notes.'),
   ('product-learning','Record explicit UI and workflow preferences with examples and scope; keep unconfirmed interpretations tentative.','Product preference memory.')]),
 'backend': ('Backend — Services & APIs','Builds server routes, authorization, service logic, integrations, jobs and backend tests.',
  'Implement backend behavior from approved contracts using the repository’s conventions. Keep routing, orchestration and domain rules separable, handle errors explicitly and preserve API compatibility. Work only in the assigned worktree and paths. Coordinate schema ownership with Data and core algorithms with Engine. Supply focused tests, operational notes and exact commit evidence to Validator.',
  [
   ('route-implementation','Implement contract-defined routes with strict validation, statuses and error shapes; test public behavior.','Route changes and contract tests.'),
   ('authorization','Enforce authentication and object-level authorization at service boundaries; test cross-user denial and expiry.','Authorization implementation and denial tests.'),
   ('service-layer','Separate request handling from domain operations and persistence; reuse existing patterns.','Focused service logic with invariant tests.'),
   ('external-integration','Verify provider docs, validate responses, bound timeouts and map failures into stable application errors.','Integration adapter and failure tests.'),
   ('background-jobs','Design job idempotency, retry limits, concurrency and cancellation around documented ownership.','Job lifecycle implementation.'),
   ('idempotent-writes','Define idempotency keys and transaction boundaries; exercise duplicate and concurrent requests.','Repeat-safe write behavior.'),
   ('error-contract','Return actionable stable errors without secrets; preserve original context in appropriate internal diagnostics.','Error mapping and tests.'),
   ('backend-regression','Reproduce a defect through the service or route, write a failing regression, fix and rerun affected tests.','Fail-before/pass-after evidence.'),
   ('backend-observability','Add meaningful structured diagnostics and health checks for changed behavior without leaking sensitive data.','Operational diagnostics and health evidence.'),
   ('backend-learning','Save proven framework conventions and recurring integration pitfalls with version and repository scope.','Backend pattern memory.')]),
 'frontend': ('Frontend — UI & Accessibility','Builds responsive interfaces, client state, forms, interaction polish and accessible flows.',
  'Implement interfaces from approved product specs and existing design conventions. Own layout, state transitions, accessibility, network feedback and browser interaction. Keep product flows free of unnecessary internal implementation details. Coordinate contracts with Backend and verify real user journeys on the running app. Use browser evidence and targeted component tests rather than snapshot-only confidence.',
  [
   ('component-design','Build components around coherent responsibility and existing design tokens; avoid unnecessary abstraction.','Components aligned with surrounding UI.'),
   ('responsive-layout','Validate small, medium and wide viewports with real content, wrapping and overflow checks.','Responsive behavior evidence.'),
   ('accessible-controls','Use semantic controls, labels, focus handling, keyboard operation and contrast checks.','Accessible interaction implementation.'),
   ('client-state','Separate server and transient UI state; define transitions, cancellation and stale response handling.','Predictable state model and tests.'),
   ('forms-validation','Match contract constraints, associate errors with fields and preserve user input after failure.','Usable forms and validation tests.'),
   ('network-states','Implement loading, empty, retry and error states; avoid duplicate writes and stale updates.','Verified network feedback states.'),
   ('design-consistency','Use the existing typography, spacing and component patterns; explain necessary deviations.','Consistent visual implementation.'),
   ('browser-verification','Run the app and exercise changed journeys, capture console/network issues and accessible navigation.','Observed browser results.'),
   ('frontend-regression','Add behavior-focused component or journey coverage for a reproduced UI bug, then verify the actual browser flow.','Regression and live-flow evidence.'),
   ('frontend-learning','Record explicit layout, copy and interaction preferences using dated examples; avoid generalizing one screen to all apps.','Scoped UI preference memory.')]),
 'engine': ('Engine — Core Logic & Performance','Builds algorithms, parsers, state machines, simulations, scheduling and performance-sensitive core logic.',
  'Own deterministic computation and domain invariants independent of UI and transport. Define inputs, outputs, error cases and complexity constraints before implementing. Use representative and adversarial cases, reproducible seeds and measured performance. Preserve numerical accuracy and ordering guarantees. Coordinate persistence with Data and expose clear core APIs to Backend.',
  [
   ('algorithm-design','Define correctness invariants, input limits and time/space bounds; choose the simplest adequate algorithm.','Algorithm design and executable implementation.'),
   ('state-machines','Enumerate valid states, transitions, guards and terminal conditions; reject invalid transitions explicitly.','State machine with transition tests.'),
   ('parsing','Separate lexical and semantic errors, define grammar limits and test malformed and boundary inputs.','Parser with actionable error cases.'),
   ('simulation','Use reproducible seeds and explicit assumptions; validate conservation properties and compare known cases.','Reproducible simulation evidence.'),
   ('numeric-correctness','Define precision, units, rounding and overflow behavior; check extreme values and avoid silent conversions.','Numerical contract and boundary tests.'),
   ('concurrency','Specify shared state and locking, cancellation and ordering; reproduce races using controlled schedules.','Concurrency implementation and race checks.'),
   ('property-tests','Derive properties from domain invariants and generate meaningful inputs with shrinking and deterministic reproduction.','Invariant coverage with reproducible failures.'),
   ('benchmarking','Record baseline and candidate on identical workloads with warmup and variability; compare correctness too.','Benchmark artifact with environment.'),
   ('optimization','Locate a measured bottleneck, make a scoped change and verify output equivalence and resource improvement.','Measured optimization with regression evidence.'),
   ('engine-learning','Record effective algorithms, failed optimization ideas and numeric pitfalls with workload constraints.','Core-engine memory.')]),
 'data': ('Data — Storage & Integrity','Owns database schemas, queries, indexes, transactions, migrations and data validation.',
  'Protect data integrity through clear schemas, transactions and reversible local migrations. Inspect actual queries and schema before changing storage. Work with Architect on compatibility and Backend on access paths. Use local representative data, verify backups and rollback for migrations, and never assume production access is authorized. Provide query plans and integrity evidence.',
  [
   ('schema-design','Model constraints, relationships and ownership; enforce domain invariants in appropriate schema constraints.','Schema and integrity constraints.'),
   ('local-migrations','Implement reversible expand/contract migrations locally and exercise upgrade, rollback and reapply.','Migration evidence and rollback steps.'),
   ('query-analysis','Inspect real SQL and query plans on representative data before proposing changes.','Query plan and bottleneck evidence.'),
   ('index-design','Choose indexes from access patterns; measure read benefit and write/storage cost.','Measured index change.'),
   ('transactions','Define atomic boundaries, isolation and retry handling; test concurrent conflicts and partial failures.','Transaction semantics and tests.'),
   ('data-validation','Validate imports and writes at boundaries with explicit error reporting and no silent coercion.','Validation and rejected-input evidence.'),
   ('backfill-design','Plan resumable bounded batches, progress tracking, duplicate handling and integrity checks.','Backfill procedure and local proof.'),
   ('backup-restore','Create local backup and verify a restore into an isolated database before destructive local migration work.','Restore verification.'),
   ('data-fixtures','Build realistic synthetic fixtures that exercise constraints and boundaries without private data.','Repeatable fixture set.'),
   ('data-learning','Record database-version-specific pitfalls and proven integrity checks with the affected schema scope.','Storage memory.')]),
 'qa': ('QA — Test Engineer','Builds meaningful regression, integration, browser and exploratory test coverage.',
  'Translate acceptance criteria into tests that challenge real behavior. Reproduce bugs before fixing coverage, choose the smallest useful test layer, and keep tests deterministic. Own test fixtures, meaningful failure diagnostics and high-risk journey coverage. Do not weaken assertions to get a green run. Distinguish code failure, flaky infrastructure and pre-existing failures. Validator remains the final independent reviewer.',
  [
   ('test-strategy','Map requirements and risks to unit, integration and journey tests, avoiding duplicated or implementation-mirroring assertions.','Risk-based test matrix.'),
   ('regression-reproduction','Capture exact inputs, environment and failure; prove a regression fails on the original behavior.','Minimal reproduction and failing test.'),
   ('unit-behavior','Test observable outputs and invariants with boundary cases; mock only true external boundaries.','Focused unit coverage.'),
   ('integration-tests','Exercise real component boundaries and isolated persistence with realistic contract inputs.','Integration suite and isolation evidence.'),
   ('journey-tests','Automate the important user path through stable semantic selectors and real assertions.','User journey coverage.'),
   ('exploratory-testing','Probe error recovery, cancellation, repeated actions and malformed inputs around changed behavior.','Exploratory findings with repro steps.'),
   ('flaky-tests','Identify nondeterminism, isolate timing or shared state, and verify the fix with a justified repeat run.','Flake diagnosis and corrected test.'),
   ('fixture-isolation','Use unique resources, deterministic seeds and cleanup that preserves unrelated work.','Repeatable isolated test setup.'),
   ('coverage-gaps','Inspect changed control paths and acceptance criteria for meaningful missing cases instead of chasing a percentage.','Prioritized coverage gaps.'),
   ('qa-learning','Record recurring failure modes and user expectations as scoped test heuristics with supporting examples.','Test-engineering memory.')]),
 'security': ('Security — Application Reviewer','Reviews trust boundaries, authorization, secrets, dependencies and abuse cases.',
  'Focus on concrete exploitable risks in authorized repositories. Map input and privilege boundaries, review changed code and demonstrate issues using harmless local reproductions. Collaborate with owners on fixes and verify protections independently. Keep secrets out of logs, skills and source control. Scope work to the requested application and report severity with evidence, not speculative generic checklists.',
  [
   ('threat-model','Map assets, actors, trust boundaries and likely abuse cases for the approved feature.','Focused threat model.'),
   ('authorization-audit','Trace role and object-level checks; test cross-tenant, cross-user and privilege escalation denials locally.','Authorization findings and denial evidence.'),
   ('input-boundaries','Trace untrusted input into queries, commands, rendering and serialization; verify context-appropriate protections.','Boundary analysis and harmless local repros.'),
   ('secret-hygiene','Review staged diffs and logging paths for sensitive material; use secret names, never values, in findings.','Secret-free diff and configuration guidance.'),
   ('dependency-review','Check exact dependency versions and official advisories relevant to reachable application paths.','Relevant dependency findings.'),
   ('session-security','Verify token expiry, revocation, cookie flags and session fixation handling against the application contract.','Session protection evidence.'),
   ('file-upload','Check content validation, path handling, size limits and storage access with harmless local files.','Upload abuse-case tests.'),
   ('secure-errors','Verify errors and diagnostics avoid secrets and private data while remaining useful for investigation.','Safe error and log checks.'),
   ('security-fix-check','Reproduce an issue locally, verify the fix blocks the original case and confirm legitimate behavior still works.','Fix verification and regression evidence.'),
   ('security-learning','Record confirmed security pitfalls with affected boundaries and versions, retiring irrelevant blanket checks.','Scoped security review memory.')]),
 'platform': ('Platform — Local Runtime & Tooling','Owns local environments, packaging, WSL/Windows paths, developer tooling and observability without remote CI.',
  'Make the project easy to build, run, verify and stop locally. Own reproducible environment commands, package scripts, containers when needed, ports and tooling integration. Respect the strict local-gating policy: do not add or depend on remote CI/CD. Validate both WSL and Windows path assumptions and document exact access URLs. Preserve existing configuration and avoid unnecessary system changes.',
  [
   ('local-environment','Inspect existing runtime versions and locks; provide the minimum reproducible setup commands.','Verified local environment.'),
   ('build-packaging','Use native project scripts and locks to create a reproducible build, validating artifacts and entry points.','Build commands and checked artifacts.'),
   ('wsl-windows-paths','Translate paths safely across WSL and Windows, preserving spaces and argument boundaries.','Cross-platform path checks.'),
   ('local-services','Start required local services with isolated storage and documented stop commands.','Service lifecycle instructions.'),
   ('port-verification','Choose an available port, bind HTTP servers to 0.0.0.0, check curl responses and distinguish verified URLs from advertised addresses.','Health evidence and localhost/WSL URLs.'),
   ('local-gates','Create local lint, type and test commands appropriate to the change; never add remote automation workflows.','Local verification entry points.'),
   ('tool-integration','Inspect tool help and supported config before wiring hooks; preserve existing integrations and report unsupported features.','Validated tooling integration.'),
   ('runtime-diagnostics','Add scoped health and diagnostics to distinguish startup, network and application failures.','Actionable local runtime diagnostics.'),
   ('rollback-runtime','Document stopping, configuration restore and artifact rollback, then verify on an isolated local setup.','Reversible local runtime procedure.'),
   ('platform-learning','Save working OS/tool version combinations, quoting pitfalls and preferred startup commands with provenance.','Environment memory.')]),
 'integrator': ('Integrator — Git & Release Coordinator','Coordinates isolated worktrees, atomic commits, conflict resolution, gated pushes and reviewable PRs.',
  'Own shared integration paths and git coordination. Inspect status, branch and remote before every mutation. Create one topic branch and worktree per writer, preserve user changes, and stage explicit paths. Integrate only reviewed commits in dependency order; resolve conflicts using contracts and revalidate affected behavior. Enforce exact-SHA Validator and Chief approvals before a push. Open issue-linked PRs after local gates and await authorized merge. Never force push, push main/master or enable remote CI.',
  [
   ('worktree-isolation','Create sibling worktrees using agent-team worktree <role> <task>; pass the directory to `agent-team spawn -C`. Confirm the `pwd` of the pane, branch and root equal the assignment before edits; do not rely on agent-definition isolation.','Unique role worktree and topic branch, with the verified cwd of the pane.'),
   ('atomic-staging','Inspect diff and stage explicit task paths; exclude unrelated work, secrets and generated artifacts.','Focused staged diff.'),
   ('conventional-commits','Commit one coherent behavior plus its meaningful tests as type(scope): summary, referencing the issue.','Atomic conventional commit.'),
   ('integration-order','Integrate dependency-ready reviewed commits into a dedicated topic branch with shared-file ownership.','Ordered integration record.'),
   ('conflict-resolution','Inspect both sides and approved contracts; resolve intentionally, preserve behavior and rerun affected checks.','Resolved conflict with verification.'),
   ('sha-gated-push','Use agent-team gate record for Validator and Chief, then agent-team gate push. Stale or missing approval blocks push.','Topic push for exact approved SHA.'),
   ('issue-linked-pr','Create a PR with concrete behavior, validation, residual risks and Closes #N; use body files for multiline text.','Reviewable linked PR.'),
   ('merge-readiness','Check exact PR head equals locally approved SHA, resolve review findings and present user merge decision.','Merge-ready evidence packet.'),
   ('git-recovery','Diagnose status and reflog before recovering; preserve work and choose reversible operations without force or hard resets.','Documented reversible recovery.'),
   ('integration-learning','Record recurring conflict causes and preferred commit/PR presentation with scope and evidence.','Git coordination memory.')])
}

RULES = '''---
tags: [claude-code, codex, global-rules, brainstorm-first, coderabbit, github-flow]
scope: global
updated: 2026-10-27
---

# Universal engineering rules

## Brainstorm first: never code blind
- Trigger: the user discusses a project, sounds like they want to start one, or asks for a feature, change, update, refactor or fix whose full scope is not already pinned down.
- Before any code, scaffolding, task list or plan, run an in-depth brainstorm (use the brainstorming skill when available) until you can state back WHAT is being built, for whom and why.
- Cover: goal and users; the real-world workflow step by step; scope, non-goals and phases; physical and system constraints (hardware, network, OS, existing software, budget); data and integrations; edge cases, failure modes and abuse cases; how success will be tested and demoed.
- Read existing code and docs first so you do not ask what the repo already answers. Ask a few focused questions at a time, most important first, offer options with a recommendation, and keep a running list of open questions.
- Finish by reflecting the full scope back in your own words and getting the user's confirmation. Only then write PROJECT.md (confirmed facts plus open questions, never invented facts) and move to planning.
- Changes to existing software get the same treatment: current behavior, desired behavior, blast radius, regression risk. The brainstorm scales with the change but is never skipped; only a request that is already fully specified (exact file and exact edit) may go straight to code.
- If the user says something is "not for coding yet" or "just context", record it and do not code.

## Scope of these rules
- Full workflow (plan, issue, topic branch and worktree, review gates) for features, bug fixes and refactors in a git repo. Small fully specified edits and non-repo directories: keep the change targeted, follow conventions, verify, no ceremony.
- Follow direct user instructions and higher-priority runtime or managed policy; these rules never override them.
- Team mode (AGENT_TEAM_PROVIDER set, or the user asks for a team): also read ~/.agent-team/TEAM_MODE.md.
- Windows sessions run in PowerShell; agent-team, tmux, gh and coderabbit may live in WSL. Check WSL before reporting a tool missing.

## Context
- Read relevant files and inspect boundaries before writing. Check PROJECT.md, ARCHITECTURE.md and TASKS.md in the repo root; if absent, record the gap rather than inventing facts.
- Read ~/.agent-team/memory/preferences.md at the start of work. Explicit user corrections are authoritative within their scope; inferred preferences stay tentative.
- Keep changes targeted to the approved task, match repository conventions, preserve unrelated work.

## Plan, then execute autonomously
- For a new app or substantial feature, after the brainstorm propose an in-depth plan: journeys, requirements and non-goals, architecture alternatives, data and contracts, annotated repo tree, dependencies, milestones, acceptance tests, risks, budget and rollback. Wait for explicit approval or modification before provisioning or implementation.
- Approval authorizes ordinary implementation, local tests, installs needed for the plan, topic commits and issue/PR operations within the approved increment. Avoid repeated permission questions. Product decisions and merge approval still need the user's stated authority.
- Deliver one user-testable increment at a time: verify it, then hand over what changed, exact how-to-test steps, and the running demo URL with stop instructions, and wait for the user's go-ahead before the next. Autonomy applies within an approved increment only.
- Give concise progress updates, incorporate steering, report blockers honestly, and ask only for decisions that materially change the outcome.
- No autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly requests one.

## Code quality: no spaghetti
- Small single-purpose functions and modules, clear boundaries, one-directional dependencies. No god files, copy-paste duplication, dead code or speculative abstraction. Reuse and extend existing patterns before adding new ones.
- Handle errors explicitly at boundaries; never swallow them or add silent fallbacks. Validate and type data at boundaries. No magic numbers or hard-coded config.
- Every behavior gets a test; a bug fix starts with a failing test. Never weaken tests.
- Use the matching skills when installed: codebase-design, code-simplification, constraint-driven-development, test-driven-development, systematic-debugging.

## Security baseline
- No secrets in code, logs, commits or memory; keep .env out of git and ship .env.example. Validate all external input, use parameterized queries, enforce authorization on every route, escape output, review dependencies, return safe error messages.
- Run security-and-hardening or a security review on anything touching auth, input, files, network or dependencies before a PR.
- Dev and demo servers bind to 127.0.0.1 by default; use 0.0.0.0 only when something else (such as WSL) needs to reach them, and say so.
- Never deploy to production, incur recurring costs, delete unrelated data or leak secrets without explicit approval.

## UI and design
- Before UI work load design-match: pick references, scan live sites for real tokens, write a spec, build from it, and compare screenshots. For artifacts load artifact-design first.
- No AI-slop patterns. Verify in a real browser at 390px and 1440px, including empty, loading and error states, before claiming done.

## Git and GitHub
- Work in a topic branch and sibling worktree; verify `pwd` before any edit. Never push to main/master or the remote default branch, force push, or overwrite unrelated work. Stage explicit paths; commit as <type>(<scope>): <summary> with linked issue references; test each coherent behavior before committing.
- Create or reuse a GitHub issue before feature or bug work. If there is no remote, auth or network, report the missing prerequisite; never fabricate issue IDs. Use CCPM for PRD, epic, tasks and linked issues; these git rules override CCPM defaults. For a brand-new app, propose private repo provisioning in the plan; never auto-publish the home directory or unrelated files.
- Push only after local review of the exact HEAD (a new commit invalidates it). Open a PR with `Closes #N` and local verification evidence. The user is final merge authority unless they explicitly delegate it.

## Local review and verification
- Run focused tests for each change plus the relevant lint, type, build and integration checks. Never assert verification that did not run.
- Run CodeRabbit locally before push or PR (typically `coderabbit review --agent --base <base>`). Inspect findings: exit code zero alone is not a clean verdict. Resolve security and performance findings, document other dispositions; missing auth, tool or network leaves review pending.
- STRICT NO CI: do not create, configure, trigger or rely on remote CI/CD. Existing third-party automation may still trigger on push; report it rather than promising control.
- HTTP features: verify health and real behavior with curl or a browser, report localhost and WSL IP URLs with verified status and stop instructions, and leave a requested demo running. TUI: verify in a PTY.

## Learning and skills
- Record stable user preferences in ~/.agent-team/memory/preferences.md with date, provenance, scope and confidence; project facts belong in repo docs. Never store credentials or private payloads. Separate explicit corrections from inference, retire contradicted notes, disclose meaningful learning.
- After a repeated successful workflow, create a narrow SKILL.md (trigger, inputs, procedure, outputs, verification, failure handling), reusing ECC/CCPM where appropriate. Share through ~/.agent-team/skills; run `agent-team sync` after approved updates.
- Preserve backups before changing personal configuration.
'''

BOOT_COMMON = '''You are Chief, the main orchestrator of this {{PROVIDER}} team session, started by {{PROVIDER}}-team inside tmux. Read your personal chief role (~/.agent-team/roles/chief.md), the universal rules and shared preferences first.

Provider rule: this is a {{PROVIDER}} team. Use ONLY {{PROVIDER}} agents and never launch an agent of any other provider. Chief runs {{CHIEF_MODEL}}, Validator runs {{VALIDATOR_MODEL}}, and workers run {{WORKER_MODEL}}, all at {{EFFORT}} effort.

Your FIRST action, before reading specs or planning, is `agent-team spawn validator`. It opens Validator in its own tmux pane at {{EFFORT}} effort. Validator sends its acknowledgement (role, model, effort, pwd) to you on startup. Wait for it by running `agent-team inbox` and checking `agent-team panes`, for at most about 5 minutes; never wait or loop indefinitely. If it cannot be spawned or has not answered by then, report degraded mode to the user and stop gated delivery; never bypass the Validator gate. Do not start builders yet.

{{EXTRA}}

Every later agent is opened with `agent-team spawn <role> --task <task> -C <worktree>`. Each agent gets its own pane in this window, and the window re-tiles automatically (extra windows open when it is full). Message agents with `agent-team send <role> <message>` (a durable file in the mailbox plus a one-line pane notice) and read replies with `agent-team inbox`; check your own inbox regularly: a notice pointing at the mailbox file is typed into your pane only when your input line is empty, otherwise it shows briefly in the tmux status bar, and the mailbox file is always the durable record. `agent-team panes` shows who is alive. Keep handoffs, findings and approvals in these files.

You are the user's only point of contact. Validator and workers send questions and blockers to you with `agent-team send chief`; you relay them and never let an agent ask the user directly. Do not start autonomous loops (/loop, continuous or ralph-style agent loops, self-rescheduling) unless the user explicitly requests one.

Read the repository specs and ask the user for the app idea if none is supplied. Produce an in-depth plan and wait for explicit user approval before implementation. After approval select specialists, define hierarchy, ownership and repo tree, use CCPM and GitHub issues, and create a separate worktree for each writer with `agent-team worktree <role> <task>`. Spawn each writer with `-C` set to that worktree and verify every pane's actual cwd before it edits. Split the approved plan into user-testable increments and deliver one at a time: finish, verify (tests, Validator, live check), hand the user what changed, exact how-to-test steps and the running demo URL with stop instructions, then wait for their feedback or go-ahead before the next increment. Require Validator plus Chief approval of the exact SHA before any push. The user controls merging unless explicitly delegated.
'''

BOOT_EXTRA = {
 'claude': "Do not use the Agent/Task tool or experimental in-process agent teams for team roles; every team role is a tmux pane. Read-only in-process search helpers for lookups are allowed.",
 'codex': "Do not use native subagent threads (spawn_agent or /agent) for team roles; every team role is a tmux pane. Read-only in-process search helpers for lookups are allowed.",
}
BOOT = {p: BOOT_COMMON.replace('{{EXTRA}}', e) for p, e in BOOT_EXTRA.items()}

def update_toml(path, top, sections):
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    for key,val in top.items():
        first = re.search(r'^\[',text,re.M)
        boundary = first.start() if first else len(text)
        prefix = text[:boundary]
        line = f'{key} = {json.dumps(val)}\n' if not isinstance(val,bool) else f'{key} = {str(val).lower()}\n'
        if re.search(r'^'+re.escape(key)+r'\s*=',prefix,re.M):
            prefix = re.sub(r'^'+re.escape(key)+r'\s*=.*\n?',lambda _:line,prefix,flags=re.M)
        else: prefix += line
        text = prefix + text[boundary:]
    for section, values in sections.items():
        pattern = r'^\['+re.escape(section)+r'\]\s*\n'
        match = re.search(pattern,text,re.M)
        if not match:
            text += '\n['+section+']\n'
            match = re.search(pattern,text,re.M)
        nxt = re.search(r'^\[',text[match.end():],re.M)
        end = match.end()+nxt.start() if nxt else len(text)
        body=text[match.end():end]
        for key,val in values.items():
            line = f'{key} = {str(val).lower() if isinstance(val,bool) else json.dumps(val)}\n'
            if re.search(r'^'+re.escape(key)+r'\s*=',body,re.M): body=re.sub(r'^'+re.escape(key)+r'\s*=.*\n?',lambda _:line,body,flags=re.M)
            else: body+=line
        text=text[:match.end()]+body+text[end:]
    if tomllib:tomllib.loads(text)
    write(path,text)

def shared_team():
    """The sibling team.py (managed_rules lives there once)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import team
    return team

def yolo_wanted():
    """YOLO defaults are strictly explicit: --yolo (AGENT_TEAM_YOLO=1) writes the marker, a later plain run
    follows the marker, --no-yolo removes it. Nothing is inferred from existing settings."""
    if os.environ.get('AGENT_TEAM_NO_YOLO') == '1': return False
    return os.environ.get('AGENT_TEAM_YOLO') == '1' or present(ROOT / 'yolo')

def strip_toml_keys(path, pairs):
    """Remove top-level `key = "value"` lines whose value is exactly what the YOLO defaults wrote."""
    if not present(path): return
    text = slurp(path)
    first = re.search(r'^\[', text, re.M)
    cut = first.start() if first else len(text)
    head = text[:cut]
    for key, value in pairs.items():
        head = re.sub(r'^' + re.escape(key) + r'\s*=\s*' + re.escape(json.dumps(value)) + r'[ \t]*\n?', '', head, flags=re.M)
    if head + text[cut:] != text: write(path, head + text[cut:])

def write_rules(path, rules):
    """Install the shared rules into a global instruction file as a marked block (the user's own text stays)."""
    path = Path(path)
    current = slurp(path) if present(path) and (path in PLANNED or path.is_file()) else None
    write(path, shared_team().managed_rules(current, rules))

PREFERENCES = '# User preferences\n\nShipped defaults of this setup (AI-Setup); replace or extend them with your own explicit corrections:\n- Brainstorm first: an in-depth scope discussion before any coding session, for new projects and for changes, features and updates.\n- Detailed Chief plan and your approval before app/feature implementation.\n- YOLO execution for authorized tasks with regular interaction and steering.\n- Chief plus independent Validator in team sessions.\n- Separate writer worktrees, atomic behavior tests and topic commits/pushes.\n- Local CodeRabbit review; no remote CI gates; you control merges.\n- Shared Claude/Codex skills and documented learning across WSL and Windows.\n\nRecord your own preferences below with date, provenance, scope and confidence (explicit corrections are authoritative; inferences stay tentative).\n'

def apply():
    providers = installed_providers()
    yolo = yolo_wanted()
    no_yolo = os.environ.get('AGENT_TEAM_NO_YOLO') == '1'
    if yolo: write(ROOT / 'yolo', YOLO_MARKER_TEXT)
    elif no_yolo: remove(ROOT / 'yolo')
    homes = [home for home in (LINUX, WINDOWS) if home is not None]
    # The install's Windows choice, so doctor checks exactly what was installed ('none' = deliberately skipped).
    write(ROOT/'windows-target',(str(WINDOWS) if WINDOWS else 'none')+'\n')
    seed(ROOT/'UNIVERSAL.md',RULES)
    rules=slurp(ROOT/'UNIVERSAL.md')
    for prov,text in BOOT.items():seed(ROOT/f'bootstrap-{prov}.txt',text)
    seed(ROOT/'models.json',json.dumps({'claude':{'chief':'claude-opus-5-5','validator':'claude-opus-5-5','worker':'claude-sonnet-5-5'},'codex':{'chief':'gpt-6.1-sol','validator':'gpt-6.1-sol','worker':'gpt-6-luna'},'effort':'high'},indent=2)+'\n')
    seed(ROOT/'memory/preferences.md', PREFERENCES)
    roster=['# Personal team roster\n\nChief orchestrates; Validator independently gates; specialists start after plan approval. Every agent runs in its own tmux pane (`agent-team spawn`), and a team uses only agents of its own provider. All workers default to high effort and may use xhigh for difficult tasks.\n']
    skill_names=[]
    for role,(title,desc,body,skills) in ROLES.items():
        assert len(skills)==10
        names=[f'team-{role}-{s[0]}' for s in skills]
        skill_names.extend(names)
        memo=ROOT/f'memory/{role}/MEMORY.md'
        seed(memo,f'# {title} memory\n\nRead shared preferences first. Add dated, scoped findings with provenance. No credentials.\n')
        prompt=f'# {title}\n\n{body}\n\n## Operating contract\nRead universal rules, PROJECT.md, ARCHITECTURE.md and TASKS.md before coding. Read shared preferences and ~/.agent-team/memory/{role}/MEMORY.md. Verify role, issue, branch, worktree, owned paths and acceptance criteria. Chief owns user decisions; Validator reviews independently. Work within the approved scope and return exact SHA plus test/review evidence. Keep learning evidence-backed and scoped.\n\n## Ten specialist skills\n'+ '\n'.join(f'- `{n}`: {s[1]}' for n,s in zip(names,skills))+'\n\n## Handoff\nReturn task/issue, worktree/branch, paths, behavior, SHA, commands/results, blockers and next action. Never approve your own implementation as Validator.\n'
        seed(ROOT/f'roles/{role}.md',prompt)
        prompt=slurp(ROOT/f'roles/{role}.md')
        roster.append(f'## {title}\n\n{desc}\n\n'+ '\n'.join(f'- `{n}` — {s[2]}' for n,s in zip(names,skills))+'\n')
        for name,(slug,procedure,evidence) in zip(names,skills):
            skill=f'---\nname: {name}\ndescription: {json.dumps("Use for "+role+" work involving "+slug.replace("-"," ")+" in an approved engineering team task.")}\n---\n\n# {title}: {slug.replace("-"," ").title()}\n\n## Inputs\nApproved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.\n\n## Procedure\n{procedure}\n\n## Evidence and output\n{evidence}\nProvide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.\n\n## Failure handling\nReport missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.\n'
            seed(ROOT/f'skills/{name}/SKILL.md',skill)
        for home in homes:
            if 'claude' in providers:
                model=('claude-opus-5-5' if role in ['chief','validator'] else 'claude-sonnet-5-5')
                yaml=f'---\nname: {role}\ndescription: {json.dumps(desc)}\nmodel: {model}\neffort: high\n'+('permissionMode: bypassPermissions\n' if yolo else '')+'memory: user\n'
                if role not in ['chief','validator','product','architect']:yaml+='isolation: worktree\n'
                # Load relevant skills on demand; do not inject all 120 skills into every agent.
                write(home/f'.claude/agents/{role}.md',yaml+'---\n\n'+prompt)
            if 'codex' in providers:
                cmodel='gpt-6.1-sol' if role in ['chief','validator'] else 'gpt-6-luna'
                manifest=f'name = {json.dumps(role)}\ndescription = {json.dumps(desc)}\nmodel = {json.dumps(cmodel)}\nmodel_reasoning_effort = "high"\ndeveloper_instructions = {json.dumps(prompt)}\n'
                write(home/f'.codex/agents/{role}.toml',manifest)
    seed(ROOT/'ROSTER.md','\n'.join(roster))
    # Skills a user or agent added under skills/ are linked too.
    existing=[p.name for p in (ROOT/'skills').iterdir() if p.is_dir()] if (ROOT/'skills').is_dir() else []
    all_skills=sorted(set(skill_names)|set(existing))
    ccpm=ensure_ccpm()
    for home in homes:
        if 'claude' in providers:
            write_rules(home/'.claude/CLAUDE.md',rules)
            settings_path=home/'.claude/settings.json'
            settings=json.loads(slurp(settings_path)) if present(settings_path) else {}
            settings.setdefault('env',{}).update({'CLAUDE_CODE_SUBAGENT_MODEL':'claude-sonnet-5-5'})
            if yolo:
                settings.setdefault('permissions',{})['defaultMode']='bypassPermissions'
                settings['skipDangerousModePermissionPrompt']=True
            elif no_yolo:
                if settings.get('permissions',{}).get('defaultMode')=='bypassPermissions':
                    del settings['permissions']['defaultMode']
                    if not settings['permissions']:del settings['permissions']
                settings.pop('skipDangerousModePermissionPrompt',None)
            elif settings.get('permissions',{}).get('defaultMode')=='bypassPermissions' and home==LINUX:
                NOTES.append('settings.json still has bypassPermissions (YOLO is off now); remove it with ./install.sh --no-yolo')
            settings.update({'model':'claude-sonnet-5-5','effortLevel':'high'})
            if home==LINUX:NOTES.append(f'sets the global Claude model (claude-sonnet-5-5) and effort (high) in {settings_path}; the previous file is backed up')
            for model in ['claude-sonnet-5-5','claude-opus-5-5']:
                settings.setdefault('modelSettings',{}).setdefault(model,{})['effortLevel']='high'
            write(settings_path,json.dumps(settings,indent=2)+'\n')
        if 'codex' in providers:
            write_rules(home/'.codex/AGENTS.md',rules)
            if no_yolo:strip_toml_keys(home/'.codex/config.toml',{'approval_policy':'never','sandbox_mode':'danger-full-access'})
            update_toml(home/'.codex/config.toml',{'model':'gpt-6-luna','model_reasoning_effort':'high',**({'approval_policy':'never','sandbox_mode':'danger-full-access'} if yolo else {})},{'features':{'multi_agent':True},'agents':{'enabled':True,'max_concurrent_threads_per_session':11,'default_subagent_model':'gpt-6-luna','default_subagent_reasoning_effort':'high'}})
        skillsdirs=[home/'.claude/skills' for p in providers if p=='claude']+[home/'.agents/skills' for p in providers if p=='codex']
        # CCPM has no binary: it is a discoverable skill with bundled references.
        if ccpm is not None:
            for base in skillsdirs:
                if home==LINUX:link(base/'ccpm',ccpm)
                elif not present(base/'ccpm') and Path(ccpm).is_dir():copy_tree(ccpm,base/'ccpm')
        for name in all_skills:
            for base in skillsdirs:
                dest=base/name
                if home==LINUX:link(dest,ROOT/'skills'/name)
                else:write(dest/'SKILL.md',slurp(ROOT/'skills'/name/'SKILL.md'))
    return {'roles':len(ROLES),'skills':sum(len(x[3]) for x in ROLES.values()),'providers':providers,'homes':[str(h) for h in homes]}

def main(argv=None):
    global DRY
    parser=argparse.ArgumentParser(description='Apply the shared agent-team configuration to this home (backed up, idempotent).')
    parser.add_argument('--dry-run',action='store_true',help='print every planned change; write nothing')
    parser.add_argument('--no-yolo',action='store_true',help='remove the YOLO marker and the bypass keys it added (backed up)')
    parser.add_argument('--yolo',action='store_true',help='opt in to YOLO defaults: agents skip permission prompts (bypassPermissions, danger-full-access)')
    parser.add_argument('--package-from',metavar='TEAM_DIR',help="first copy this repo's team/ package into ~/.agent-team")
    parser.add_argument('--restore',metavar='TIMESTAMP',help='restore the files saved in ~/.agent-team/backups/TIMESTAMP')
    args=parser.parse_args(argv)
    DRY=args.dry_run
    if args.yolo and args.no_yolo:parser.error('--yolo and --no-yolo conflict')
    if args.yolo:os.environ['AGENT_TEAM_YOLO']='1'
    if args.no_yolo:os.environ['AGENT_TEAM_NO_YOLO']='1'
    if args.restore is not None:
        restore(args.restore);return 0
    if args.package_from:copy_package(args.package_from)
    summary=apply()
    print(f'Providers: {", ".join(summary["providers"])}; {summary["roles"]} roles, {summary["skills"]} skills; homes: {", ".join(summary["homes"])}')
    report()
    finish()
    return 0

if __name__=='__main__':sys.exit(main())
