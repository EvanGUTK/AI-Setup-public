<#
.SYNOPSIS
  Native Windows installer for AI-Setup. No WSL and no tmux.

.DESCRIPTION
  Installs, into the current user's profile:
    - the shared engineering rules as a managed block in ~/.claude/CLAUDE.md
    - the team skills (and role docs) and the design-match skill
    - Claude Code plugins listed in native/plugins.json (core tier; -All adds optional)
    - the CCPM skill and the design-systems library, fetched from pinned upstream commits
    - a blank preferences template (only if you have none)
  Pane teams (claude-team / codex-team) need tmux and are not part of the native install.

  Every file it changes is backed up first to ~/.agent-team/backups/<timestamp>/.
  Nothing here handles credentials: you still run `claude` then /login yourself.

.PARAMETER DryRun       Show what would change; write nothing.
.PARAMETER All          Also install the optional plugin tier.
.PARAMETER SkipPlugins  Do not touch plugins.
.PARAMETER SkipExtras   Do not fetch CCPM or the design-systems library (no network use by git).
.PARAMETER Restore      Restore the backup <timestamp> and remove files that install created.
.PARAMETER Uninstall    Remove what this installer added (plugins are listed, not removed).
.PARAMETER TargetHome   Install under this directory instead of the user profile (sandbox/testing).
.PARAMETER ManifestPath Use another plugins manifest (testing).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$All,
    [switch]$SkipPlugins,
    [switch]$SkipExtras,
    [string]$Restore,
    [switch]$Uninstall,
    [string]$TargetHome,
    [string]$ManifestPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if ($PSVersionTable.PSVersion.Major -lt 5) { throw 'Windows PowerShell 5.1 or newer is required.' }
if ($Restore -and $Uninstall) { throw 'Use -Restore or -Uninstall, not both.' }

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$HomeDir = if ($TargetHome) { $TargetHome } else { $env:USERPROFILE }
if (-not $HomeDir) { throw 'Cannot determine the target home directory (USERPROFILE is empty).' }
$AgentTeam = [IO.Path]::Combine($HomeDir, '.agent-team')
$ClaudeDir = [IO.Path]::Combine($HomeDir, '.claude')
$SkillsDir = [IO.Path]::Combine($ClaudeDir, 'skills')
$DesignDir = [IO.Path]::Combine($ClaudeDir, 'design-systems')
$RulesFile = [IO.Path]::Combine($ClaudeDir, 'CLAUDE.md')
$MarkerFile = [IO.Path]::Combine($AgentTeam, 'native-sources.json')
$ManifestFile = if ($ManifestPath) { $ManifestPath } else { [IO.Path]::Combine($RepoRoot, 'native', 'plugins.json') }
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$BeginMark = '<!-- BEGIN AGENT TEAM -->'
$EndMark = '<!-- END AGENT TEAM -->'
$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$BackupRoot = [IO.Path]::Combine($AgentTeam, 'backups', $Stamp)
$Created = New-Object System.Collections.ArrayList
$Problems = New-Object System.Collections.ArrayList

# ---------------------------------------------------------------- small helpers
function Write-Step([string]$Text) { Write-Host ''; Write-Host "== $Text" }
function Write-Plan([string]$Text) { if ($DryRun) { Write-Host "  would: $Text" } else { Write-Host "  $Text" } }
function Add-Problem([string]$Text) { [void]$Problems.Add($Text); Write-Host "  PROBLEM: $Text" }
function Test-Tool([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Get-Prop($Obj, [string]$Name, $Default) {
    $prop = $Obj.PSObject.Properties[$Name]
    if ($null -ne $prop) { return $prop.Value }
    return $Default
}
function Read-TextLf([string]$Path) {
    return [IO.File]::ReadAllText($Path, $Utf8).TrimStart([char]0xFEFF).Replace("`r`n", "`n")
}
function Get-RelativePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $base = [IO.Path]::GetFullPath($HomeDir).TrimEnd('\') + '\'
    if (-not $full.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to touch a path outside the target home: $Path" }
    return $full.Substring($base.Length)
}
function Save-Backup([string]$Path) {
    if ($DryRun -or -not (Test-Path -LiteralPath $Path)) { return }
    $dest = [IO.Path]::Combine($BackupRoot, 'files', (Get-RelativePath $Path))
    New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath $Path -Destination $dest -Recurse -Force
}
function Register-Created([string]$Path) { [void]$Created.Add((Get-RelativePath $Path)) }

# Write text only when it differs. Returns $true when a change was (or would be) made.
function Set-FileText([string]$Path, [string]$Text) {
    $exists = Test-Path -LiteralPath $Path
    if ($exists -and ([IO.File]::ReadAllText($Path, $Utf8) -ceq $Text)) { return $false }
    if ($DryRun) { return $true }
    if ($exists) { Save-Backup $Path } else { Register-Created $Path }
    New-Item -ItemType Directory -Force (Split-Path -Parent $Path) | Out-Null
    [IO.File]::WriteAllText($Path, $Text, $Utf8)
    return $true
}
function Initialize-FileText([string]$Path, [string]$Text) {
    if (Test-Path -LiteralPath $Path) { return $false }
    return (Set-FileText $Path $Text)
}

function Get-TreeHash([string]$Dir) {
    if (-not (Test-Path -LiteralPath $Dir)) { return '' }
    $root = (Resolve-Path -LiteralPath $Dir).ProviderPath.TrimEnd('\') + '\'
    $lines = @()
    foreach ($f in (Get-ChildItem -LiteralPath $Dir -Recurse -File | Sort-Object FullName)) {
        $lines += ('{0}|{1}' -f $f.FullName.Substring($root.Length).Replace('\', '/'), (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash)
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    return ([BitConverter]::ToString($sha.ComputeHash($Utf8.GetBytes(($lines -join "`n"))))).Replace('-', '')
}
# Make $Dest an exact copy of $Src. Returns $true when a change was (or would be) made.
function Sync-Dir([string]$Src, [string]$Dest) {
    if ((Get-TreeHash $Src) -eq (Get-TreeHash $Dest)) { return $false }
    if ($DryRun) { return $true }
    if (Test-Path -LiteralPath $Dest) {
        Save-Backup $Dest
        Remove-Item -LiteralPath $Dest -Recurse -Force
    } else { Register-Created $Dest }
    New-Item -ItemType Directory -Force (Split-Path -Parent $Dest) | Out-Null
    Copy-Item -LiteralPath $Src -Destination $Dest -Recurse -Force
    return $true
}

function Save-CreatedList {
    if ($DryRun -or $Created.Count -eq 0) { return }
    New-Item -ItemType Directory -Force $BackupRoot | Out-Null
    [IO.File]::WriteAllText([IO.Path]::Combine($BackupRoot, 'CREATED.txt'), (($Created.ToArray()) -join "`n") + "`n", $Utf8)
}

# ---------------------------------------------------------------- rules block (same logic as agent-team's managed_rules)
function Get-RulesBody {
    $text = Read-TextLf ([IO.Path]::Combine($RepoRoot, 'team', 'UNIVERSAL.md'))
    $rx = New-Object System.Text.RegularExpressions.Regex('\A---\n.*?\n---\n', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    return $rx.Replace($text, '', 1).Trim("`n")
}
function Get-ManagedRules([string]$Existing, [string]$Body) {
    $block = "$BeginMark`n$Body`n$EndMark`n"
    if ([string]::IsNullOrWhiteSpace($Existing)) { return $block }
    $bi = $Existing.IndexOf($BeginMark)
    if ($bi -ge 0) {
        $rest = $Existing.Substring($bi + $BeginMark.Length)
        $ri = $rest.IndexOf($EndMark)
        if ($ri -ge 0) { return $Existing.Substring(0, $bi) + $block + $rest.Substring($ri + $EndMark.Length).TrimStart("`n") }
    }
    if ($Existing.Contains('# Universal engineering rules')) { return $block }
    return $Existing.TrimEnd("`n") + "`n`n" + $block
}
function Remove-ManagedRules([string]$Existing) {
    $bi = $Existing.IndexOf($BeginMark)
    if ($bi -lt 0) { return $Existing }
    $rest = $Existing.Substring($bi + $BeginMark.Length)
    $ri = $rest.IndexOf($EndMark)
    if ($ri -lt 0) { return $Existing }
    return $Existing.Substring(0, $bi) + $rest.Substring($ri + $EndMark.Length).TrimStart("`n")
}

# ---------------------------------------------------------------- native tool wrappers
function Invoke-Native([string]$Exe, [string[]]$ToolArgs) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @ToolArgs 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    return [pscustomobject]@{ Code = $code; Output = (@($out) -join "`n") }
}
function Invoke-Claude([string[]]$ToolArgs) {
    $oldCfg = $env:CLAUDE_CONFIG_DIR
    if ($TargetHome) { $env:CLAUDE_CONFIG_DIR = $ClaudeDir }
    try { return (Invoke-Native 'claude' $ToolArgs) }
    finally { $env:CLAUDE_CONFIG_DIR = $oldCfg }
}
function Invoke-Git([string[]]$ToolArgs) {
    $r = Invoke-Native 'git' $ToolArgs
    if ($r.Code -ne 0) { throw "git $($ToolArgs -join ' ') failed: $($r.Output)" }
    return $r.Output
}
function Get-PinnedCheckout([string]$Repo, [string]$Sha, [string]$SubPath) {
    $tmp = [IO.Path]::Combine([IO.Path]::GetTempPath(), 'ai-setup-' + [Guid]::NewGuid().ToString('N'))
    try {
        [void](Invoke-Git @('clone', '--quiet', '--depth', '1', '--filter=blob:none', '--no-checkout', '--sparse', $Repo, $tmp))
        [void](Invoke-Git @('-C', $tmp, 'sparse-checkout', 'set', $SubPath))
        [void](Invoke-Git @('-C', $tmp, 'fetch', '--quiet', '--depth', '1', 'origin', $Sha))
        [void](Invoke-Git @('-C', $tmp, 'checkout', '--quiet', '--detach', $Sha))
        $head = (Invoke-Git @('-C', $tmp, 'rev-parse', 'HEAD')).Trim()
        if ($head -ne $Sha) { throw "pinned checkout resolved to $head, expected $Sha" }
        return $tmp
    } catch {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
        throw
    }
}
function Remove-TempTree([string]$Path) {
    if ($Path -and (Test-Path -LiteralPath $Path)) { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue }
}

function Get-Markers {
    if (Test-Path -LiteralPath $MarkerFile) {
        try { return ((Read-TextLf $MarkerFile) | ConvertFrom-Json) } catch { }
    }
    return ([pscustomobject]@{})
}
function Test-MarkerCurrent([string]$Key, [string]$Sha) {
    $m = Get-Markers
    return ((Get-Prop $m $Key '') -eq $Sha)
}
function Set-Marker([string]$Key, [string]$Sha) {
    if ($DryRun) { return }
    $m = Get-Markers
    $h = [ordered]@{}
    foreach ($p in $m.PSObject.Properties) { $h[$p.Name] = $p.Value }
    $h[$Key] = $Sha
    [void](Set-FileText $MarkerFile (([pscustomobject]$h | ConvertTo-Json) + "`n"))
}

# Manifest entries keep name and marketplace apart so no literal "name@host" string sits in a public file.
function Get-PluginId($Plugin) { return "$($Plugin.name)@$($Plugin.marketplace)" }

function Get-TeamSkillNames {
    return @(Get-ChildItem -LiteralPath ([IO.Path]::Combine($RepoRoot, 'team', 'skills')) -Directory | ForEach-Object { $_.Name })
}

# ---------------------------------------------------------------- restore
if ($Restore) {
    Write-Step "Restore backup $Restore"
    $src = [IO.Path]::Combine($AgentTeam, 'backups', $Restore)
    if (-not (Test-Path -LiteralPath $src)) { throw "No such backup: $src" }
    $filesRoot = [IO.Path]::Combine($src, 'files')
    $createdFile = [IO.Path]::Combine($src, 'CREATED.txt')
    if (Test-Path -LiteralPath $createdFile) {
        foreach ($rel in ((Read-TextLf $createdFile) -split "`n")) {
            if (-not $rel) { continue }
            $target = [IO.Path]::Combine($HomeDir, $rel)
            [void](Get-RelativePath $target)
            if (Test-Path -LiteralPath $target) {
                if ($DryRun) { Write-Host "  would remove created: $rel" } else { Remove-Item -LiteralPath $target -Recurse -Force; Write-Host "  removed created: $rel" }
            }
        }
    }
    if (Test-Path -LiteralPath $filesRoot) {
        $base = (Resolve-Path -LiteralPath $filesRoot).ProviderPath.TrimEnd('\') + '\'
        foreach ($f in (Get-ChildItem -LiteralPath $filesRoot -Recurse -File)) {
            $rel = $f.FullName.Substring($base.Length)
            $target = [IO.Path]::Combine($HomeDir, $rel)
            [void](Get-RelativePath $target)
            if ($DryRun) { Write-Host "  would restore: $rel"; continue }
            New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $target -Force
            Write-Host "  restored: $rel"
        }
    }
    Write-Host ''
    Write-Host 'Plugins are not reverted by -Restore. Remove them with `claude plugin uninstall <id>` if needed.'
    exit 0
}

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    Write-Step 'Uninstall'
    if (Test-Path -LiteralPath $RulesFile) {
        $cur = [IO.File]::ReadAllText($RulesFile, $Utf8)
        $new = Remove-ManagedRules $cur
        if ($new -cne $cur) {
            if ($DryRun) { Write-Host '  would remove the managed rules block from ~/.claude/CLAUDE.md' }
            else { [void](Set-FileText $RulesFile $new); Write-Host '  removed the managed rules block from ~/.claude/CLAUDE.md' }
        }
    }
    $names = @(Get-TeamSkillNames) + @('design-match', 'ccpm')
    $removed = 0
    foreach ($n in $names) {
        foreach ($dir in @([IO.Path]::Combine($SkillsDir, $n), [IO.Path]::Combine($AgentTeam, 'skills', $n))) {
            if (Test-Path -LiteralPath $dir) {
                $removed++
                if (-not $DryRun) { Save-Backup $dir; Remove-Item -LiteralPath $dir -Recurse -Force }
            }
        }
    }
    Write-Host "  $(if ($DryRun) { 'would remove' } else { 'removed' }) $removed skill folders"
    $indexFile = [IO.Path]::Combine($DesignDir, 'INDEX.md')
    if ((Test-Path -LiteralPath $indexFile) -and ([IO.File]::ReadAllText($indexFile, $Utf8) -match 'Design system reference index')) {
        if (-not $DryRun) { Save-Backup $DesignDir; Remove-Item -LiteralPath $DesignDir -Recurse -Force }
        Write-Host "  $(if ($DryRun) { 'would remove' } else { 'removed' }) ~/.claude/design-systems"
    }
    Write-Host ''
    Write-Host 'Kept on purpose: ~/.agent-team (your preferences and memory) and all plugins.'
    if (Test-Path -LiteralPath $ManifestFile) {
        $mf = (Read-TextLf $ManifestFile) | ConvertFrom-Json
        Write-Host 'To remove plugins, run:'
        foreach ($p in @($mf.plugins)) { Write-Host "  claude plugin uninstall $(Get-PluginId $p)" }
    }
    Save-CreatedList
    if (-not $DryRun -and (Test-Path -LiteralPath $BackupRoot)) { Write-Host "Backup of removed files: $BackupRoot (restore with -Restore $Stamp)" }
    exit 0
}

# ---------------------------------------------------------------- install
Write-Host "AI-Setup native Windows install$(if ($DryRun) { ' (DRY RUN: nothing is written)' })"
Write-Host "Target home: $HomeDir"

Write-Step 'Prerequisites'
$hasGit = Test-Tool 'git'
$hasClaude = Test-Tool 'claude'
foreach ($t in @(@('git', $hasGit, 'needed to fetch CCPM and the design library'),
                 @('claude', $hasClaude, 'needed to install plugins'),
                 @('node', (Test-Tool 'node'), 'needed by several plugins and MCP servers'),
                 @('gh', (Test-Tool 'gh'), 'optional, for GitHub issues and PRs'),
                 @('bash', (Test-Tool 'bash'), 'Git Bash, used by Claude Code on Windows'))) {
    Write-Host ('  {0,-8} {1}' -f $(if ($t[1]) { 'ok' } else { 'MISSING' }), "$($t[0])  ($($t[2]))")
}
if (-not (Test-Path -LiteralPath $ManifestFile)) { throw "Missing plugin manifest: $ManifestFile" }
$manifest = (Read-TextLf $ManifestFile) | ConvertFrom-Json

# --- rules and team package
Write-Step 'Rules and team package'
$teamSrc = [IO.Path]::Combine($RepoRoot, 'team')
$body = Get-RulesBody
$newRules = Get-ManagedRules $(if (Test-Path -LiteralPath $RulesFile) { [IO.File]::ReadAllText($RulesFile, $Utf8) } else { $null }) $body
if (Set-FileText $RulesFile $newRules) { Write-Plan 'write the managed rules block in ~/.claude/CLAUDE.md' } else { Write-Host '  rules block already current' }
$changed = 0
foreach ($f in @('UNIVERSAL.md', 'TEAM_MODE.md', 'ROSTER.md')) {
    if (Set-FileText ([IO.Path]::Combine($AgentTeam, $f)) (Read-TextLf ([IO.Path]::Combine($teamSrc, $f)))) { $changed++ }
}
foreach ($r in (Get-ChildItem -LiteralPath ([IO.Path]::Combine($teamSrc, 'roles')) -File -Filter '*.md')) {
    if (Set-FileText ([IO.Path]::Combine($AgentTeam, 'roles', $r.Name)) (Read-TextLf $r.FullName)) { $changed++ }
}
Write-Plan "copy $changed team doc files to ~/.agent-team"
$seeded = 0
if (Initialize-FileText ([IO.Path]::Combine($AgentTeam, 'memory', 'preferences.md')) (Read-TextLf ([IO.Path]::Combine($RepoRoot, 'native', 'preferences.template.md')))) { $seeded++ }
foreach ($r in (Get-ChildItem -LiteralPath ([IO.Path]::Combine($teamSrc, 'roles')) -File -Filter '*.md')) {
    $title = ((Read-TextLf $r.FullName) -split "`n")[0].TrimStart('#', ' ')
    $memo = "# $title memory`n`nRead shared preferences first. Add dated, scoped findings with provenance. No credentials.`n"
    if (Initialize-FileText ([IO.Path]::Combine($AgentTeam, 'memory', $r.BaseName, 'MEMORY.md')) $memo) { $seeded++ }
}
Write-Plan "seed $seeded memory templates (existing ones are never overwritten)"

# --- skills
Write-Step 'Skills'
$n = 0; $same = 0
foreach ($name in (Get-TeamSkillNames)) {
    $src = [IO.Path]::Combine($teamSrc, 'skills', $name)
    if (Sync-Dir $src ([IO.Path]::Combine($SkillsDir, $name))) { $n++ } else { $same++ }
    [void](Sync-Dir $src ([IO.Path]::Combine($AgentTeam, 'skills', $name)))
}
Write-Plan "install or update $n team skills ($same already current)"
$dm = Sync-Dir ([IO.Path]::Combine($RepoRoot, 'native', 'skills', 'design-match')) ([IO.Path]::Combine($SkillsDir, 'design-match'))
Write-Host "  design-match: $(if ($dm) { if ($DryRun) { 'would install' } else { 'installed' } } else { 'already current' })"

# --- pinned extras (CCPM, design systems)
Write-Step 'CCPM skill and design-systems library'
if ($SkipExtras) { Write-Host '  skipped (-SkipExtras)' }
elseif (-not $hasGit) { Add-Problem 'git not found: CCPM and the design-systems library were skipped' }
else {
    $ex = $manifest.extras
    $c = $ex.ccpm
    if ((Test-MarkerCurrent 'ccpm' $c.sha) -and (Test-Path -LiteralPath ([IO.Path]::Combine($SkillsDir, $c.target)))) { Write-Host '  ccpm: already at the pinned commit' }
    elseif ($DryRun) { Write-Host "  would fetch ccpm at $($c.sha.Substring(0,12)) from $($c.repo)" }
    else {
        $co = $null
        try {
            $co = Get-PinnedCheckout $c.repo $c.sha $c.path
            [void](Sync-Dir ([IO.Path]::Combine($co, ($c.path -replace '/', '\'))) ([IO.Path]::Combine($SkillsDir, $c.target)))
            Set-Marker 'ccpm' $c.sha
            Write-Host "  ccpm: installed at $($c.sha.Substring(0,12))"
        } catch { Add-Problem "ccpm: $($_.Exception.Message)" } finally { Remove-TempTree $co }
    }
    $d = $ex.designSystems
    if ((Test-MarkerCurrent 'designSystems' $d.sha) -and (Test-Path -LiteralPath $DesignDir)) { Write-Host '  design systems: already at the pinned commit' }
    elseif ($DryRun) { Write-Host "  would fetch design systems at $($d.sha.Substring(0,12)) from $($d.repo)" }
    else {
        $co = $null
        $stage = [IO.Path]::Combine([IO.Path]::GetTempPath(), 'ai-setup-stage-' + [Guid]::NewGuid().ToString('N'))
        try {
            $co = Get-PinnedCheckout $d.repo $d.sha $d.path
            $srcDir = [IO.Path]::Combine($co, ($d.path -replace '/', '\'))
            New-Item -ItemType Directory -Force $stage | Out-Null
            $rows = @()
            foreach ($dir in (Get-ChildItem -LiteralPath $srcDir -Directory | Sort-Object Name)) {
                $file = [IO.Path]::Combine($dir.FullName, 'DESIGN.md')
                if (-not (Test-Path -LiteralPath $file)) { continue }
                New-Item -ItemType Directory -Force ([IO.Path]::Combine($stage, $dir.Name)) | Out-Null
                Copy-Item -LiteralPath $file -Destination ([IO.Path]::Combine($stage, $dir.Name, 'DESIGN.md'))
                $head = @(Get-Content -LiteralPath $file -TotalCount 6 -Encoding UTF8)
                $cat = ''; $feel = ''
                foreach ($line in $head) {
                    if ($line -match '^>\s*Category:\s*(.+)$') { $cat = $Matches[1].Trim() }
                    elseif ($line -match '^>\s*(.+)$' -and -not $feel) { $feel = $Matches[1].Trim() }
                }
                $rows += ('| {0} | {1} | {2} |' -f $dir.Name, $cat.Replace('|', '/'), $feel.Replace('|', '/'))
            }
            if ($rows.Count -eq 0) { throw 'no DESIGN.md files found upstream' }
            $header = "# Design system reference index`n`nSource: $($d.repo) at $($d.sha) ($($d.license)), $($d.path)/. Each folder holds one DESIGN.md extracted from real pages (palette, type, geometry, layout, do/don't).`nOpen only the 1-3 closest matches; do not read the whole library.`n`n| name | category | feel |`n|---|---|---|`n"
            [IO.File]::WriteAllText([IO.Path]::Combine($stage, 'INDEX.md'), $header + ($rows -join "`n") + "`n", $Utf8)
            $lic = [IO.Path]::Combine($co, 'LICENSE')
            if (Test-Path -LiteralPath $lic) { Copy-Item -LiteralPath $lic -Destination ([IO.Path]::Combine($stage, "LICENSE-upstream-$($d.license).txt")) }
            [void](Sync-Dir $stage $DesignDir)
            Set-Marker 'designSystems' $d.sha
            Write-Host "  design systems: $($rows.Count) installed at $($d.sha.Substring(0,12))"
        } catch { Add-Problem "design systems: $($_.Exception.Message)" } finally { Remove-TempTree $co; Remove-TempTree $stage }
    }
}

# --- plugins
$loginNeeded = New-Object System.Collections.ArrayList
$noteLines = New-Object System.Collections.ArrayList
Write-Step "Plugins ($(if ($All) { 'core + optional' } else { 'core only' }))"
if ($SkipPlugins) { Write-Host '  skipped (-SkipPlugins)' }
elseif (-not $hasClaude) { Add-Problem 'claude CLI not found: plugins were skipped. Install Claude Code, then run this script again.' }
else {
    foreach ($m in @($manifest.marketplaces)) {
        if (Get-Prop $m 'builtIn' $false) { continue }
        if ($DryRun) { Write-Host "  would: claude plugin marketplace add $($m.source)"; continue }
        $r = Invoke-Claude @('plugin', 'marketplace', 'add', $m.source)
        if ($r.Code -ne 0 -and $r.Output -notmatch '(?i)already') { Add-Problem "marketplace $($m.source): $($r.Output)" }
        else { Write-Host "  marketplace ready: $($m.name)" }
    }
    $installed = @{}
    $listed = Invoke-Claude @('plugin', 'list', '--json')
    if ($listed.Code -eq 0) {
        try { foreach ($p in @(($listed.Output | ConvertFrom-Json))) { $installed[$p.id] = $p.version } } catch { Write-Host '  (could not parse the installed plugin list; will try every install)' }
    }
    $okCount = 0; $skipCount = 0
    foreach ($p in @($manifest.plugins)) {
        if ($p.tier -ne 'core' -and -not $All) { continue }
        $pluginId = Get-PluginId $p
        if ($installed.ContainsKey($pluginId)) {
            $skipCount++
            if ($installed[$pluginId] -ne $p.tested) { [void]$noteLines.Add("${pluginId}: installed $($installed[$pluginId]), manifest tested $($p.tested)") }
        } elseif ($DryRun) {
            Write-Host "  would: claude plugin install $pluginId --scope user"
            $okCount++
        } else {
            $r = Invoke-Claude @('plugin', 'install', $pluginId, '--scope', 'user')
            if ($r.Code -eq 0) { $okCount++; Write-Host "  installed: $pluginId" }
            else { Add-Problem "plugin ${pluginId}: $($r.Output)"; continue }
        }
        if (Get-Prop $p 'login' $false) { [void]$loginNeeded.Add($pluginId) }
        $note = Get-Prop $p 'note' ''
        if ($note) { [void]$noteLines.Add("${pluginId}: $note") }
    }
    Write-Host "  $okCount $(if ($DryRun) { 'to install' } else { 'installed' }), $skipCount already installed"
}

Save-CreatedList

# ---------------------------------------------------------------- summary
Write-Step 'Done'
if ($Problems.Count -gt 0) { Write-Host "$($Problems.Count) problem(s) above. The rest of the install finished; fix them and run this script again (it is safe to repeat)." }
if (-not $DryRun -and (Test-Path -LiteralPath $BackupRoot)) { Write-Host "Backups of anything changed: $BackupRoot (undo with: .\install-native.ps1 -Restore $Stamp)" }
if ($noteLines.Count -gt 0) { Write-Host ''; Write-Host 'Notes:'; foreach ($l in $noteLines) { Write-Host "  - $l" } }
Write-Host ''
Write-Host 'Manual steps (credentials are never automated):'
Write-Host '  1. Run `claude`, then /login. Logging in with the same account also brings your account-synced plugins.'
Write-Host '  2. Run /reload-plugins (or restart Claude Code).'
Write-Host '  3. Optional: gh auth login; coderabbit auth login (CodeRabbit CLI is not verified on native Windows).'
if ($loginNeeded.Count -gt 0) { Write-Host "  4. Plugins that need their own login or key: $((@($loginNeeded) | Sort-Object -Unique) -join ', ')" }
$synced = @($manifest.synced)
if ($synced.Count -gt 0) { Write-Host "  Account-synced plugins (not installable here): $($synced -join ', ')" }
Write-Host ''
Write-Host 'Pane teams (claude-team / codex-team) need tmux and are not part of the native install.'
if ($Problems.Count -gt 0) { exit 1 }
exit 0
