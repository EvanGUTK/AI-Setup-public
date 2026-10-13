<#
.SYNOPSIS
  Windows half of the AI-Setup install: PowerShell profile hook, PATH and native ECC plugins.
.DESCRIPTION
  Run ./install.sh inside WSL first; it writes the team files and wsl-target.json under
  %USERPROFILE%\.agent-team and copies this script there. Then run, in Windows PowerShell:
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.agent-team\install.ps1"
  claude-team / codex-team (.cmd) call into WSL; plain claude/codex keep using the native Windows CLIs.
  -Yolo opts in to YOLO defaults: plain claude/codex get their skip-permission flags injected.
  Safe to run repeatedly. Existing profile files are backed up before the first change.
#>
param([switch]$NoPlugins, [switch]$Yolo)
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:USERPROFILE '.agent-team'
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$backup = Join-Path $base "profile-backups\$stamp"

# Source of the Windows scripts: next to this file (installed copy) or in team\ (repo checkout).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = if (Test-Path (Join-Path $here 'team\windows-profile.ps1')) { Join-Path $here 'team' } else { $here }
New-Item -ItemType Directory -Force -Path (Join-Path $base 'bin') | Out-Null
foreach ($name in 'windows-profile.ps1','windows-team.ps1') {
    $from = Join-Path $source $name
    $to = Join-Path $base $name
    if ((Test-Path $from) -and ($from -ne $to)) { Copy-Item -LiteralPath $from -Destination $to -Force }
}
# Same bytes as install_launchers.cmd_launcher (CRLF); an existing file is never rewritten, so a WSL rerun is a no-op.
foreach ($provider in 'claude','codex') {
    $cmdPath = Join-Path $base "bin\$provider-team.cmd"
    if (-not (Test-Path $cmdPath)) {
        $cmd = "@echo off`r`nrem Starts $provider-team inside WSL (distro and home come from wsl-target.json).`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File `"%USERPROFILE%\.agent-team\windows-team.ps1`" -Provider $provider %*`r`n"
        [IO.File]::WriteAllText($cmdPath, $cmd, (New-Object Text.UTF8Encoding($false)))
    }
}
# Same text as build_setup.YOLO_MARKER_TEXT (LF); written only when missing.
if ($Yolo -and -not (Test-Path (Join-Path $base 'yolo'))) {
    [IO.File]::WriteAllText((Join-Path $base 'yolo'), "Written by install.sh --yolo (or install.ps1 -Yolo). While this file exists, agents run with permission prompts skipped (Claude bypassPermissions, Codex danger-full-access). Turn it off with ./install.sh --no-yolo.`n", (New-Object Text.UTF8Encoding($false)))
}
if (-not (Test-Path (Join-Path $base 'wsl-target.json'))) {
    Write-Warning 'wsl-target.json is missing: run ./install.sh inside WSL so claude-team/codex-team can find the Linux side.'
}

$documents = [Environment]::GetFolderPath('MyDocuments')
$profiles = @(
    (Join-Path $documents 'WindowsPowerShell\profile.ps1'),
    (Join-Path $documents 'WindowsPowerShell\Microsoft.PowerShell_profile.ps1'),
    (Join-Path $documents 'PowerShell\profile.ps1'),
    (Join-Path $documents 'PowerShell\Microsoft.PowerShell_profile.ps1')
)
foreach ($profilePath in $profiles) {
    $parent = Split-Path $profilePath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $text = if (Test-Path $profilePath) { [IO.File]::ReadAllText($profilePath) } else { '' }
    if ($text -notmatch '# BEGIN PERSONAL AGENT TEAM') {
        if (Test-Path $profilePath) {
            New-Item -ItemType Directory -Force -Path $backup | Out-Null
            $label = (Split-Path $parent -Leaf) + '-' + (Split-Path $profilePath -Leaf)
            Copy-Item -LiteralPath $profilePath -Destination (Join-Path $backup $label)
        }
        $text += "`r`n# BEGIN PERSONAL AGENT TEAM`r`n. `"`$env:USERPROFILE\.agent-team\windows-profile.ps1`"`r`n# END PERSONAL AGENT TEAM`r`n"
        [IO.File]::WriteAllText($profilePath, $text, (New-Object Text.UTF8Encoding($false)))
    }
}

$teamBin = Join-Path $base 'bin'
$userPath = [Environment]::GetEnvironmentVariable('Path','User')
if (($userPath -split ';') -notcontains $teamBin) {
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    [IO.File]::WriteAllText((Join-Path $backup 'user-path.txt'), "$userPath")
    [Environment]::SetEnvironmentVariable('Path', "$teamBin;$userPath", 'User')
}

# ECC through each native Windows CLI's own plugin lifecycle, when that CLI is installed.
if (-not $NoPlugins) {
    $claude = Get-Command claude -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $claude) {
        $fallback = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
        if (Test-Path $fallback) { $claude = Get-Item $fallback }
    }
    if ($claude) {
        $exe = if ($claude.PSObject.Properties['Source']) { $claude.Source } else { $claude.FullName }
        try {
            $plugins = & $exe plugin list --json | ConvertFrom-Json
            $ecc = $plugins | Where-Object { $_.id -eq 'ecc@ecc' -and $_.scope -eq 'user' }
            if (-not $ecc) {
                & $exe plugin marketplace add affaan-m/ECC
                & $exe plugin install ecc@ecc --scope user
            } elseif (-not $ecc.enabled) {
                & $exe plugin enable ecc@ecc --scope user
            }
        } catch { Write-Warning "Claude ECC plugin step failed ($_). After logging in run: claude plugin marketplace add affaan-m/ECC; claude plugin install ecc@ecc --scope user" }
    }
    $codex = Get-Command codex -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($codex) {
        try {
            $listing = (& $codex.Source plugin list | Out-String)
            if ($listing -notmatch '(?m)^ecc@ecc\s+installed') {
                & $codex.Source plugin marketplace add affaan-m/ECC
                & $codex.Source plugin add ecc@ecc
            }
        } catch { Write-Warning "Codex ECC plugin step failed ($_). Run: codex plugin marketplace add affaan-m/ECC; codex plugin add ecc@ecc" }
    }
}
Write-Output 'AI-Setup Windows integration installed: PowerShell profiles, team-command PATH, claude-team/codex-team launchers. Open a new PowerShell window.'
