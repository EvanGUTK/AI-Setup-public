# Loaded by user PowerShell profiles; native CLIs retain user authentication.
$teamBin = Join-Path $env:USERPROFILE '.agent-team\bin'
if (($env:PATH -split ';') -notcontains $teamBin) { $env:PATH = "$teamBin;$env:PATH" }

# The real executable behind a name, bypassing the functions defined below.
function global:Get-AgentNative([string]$Name, [string]$Fallback) {
    $app = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($app) { return $app.Source }
    return $Fallback
}

# YOLO defaults are opt-in (install.ps1 -Yolo or install.sh --yolo create %USERPROFILE%\.agent-team\yolo).
# AGENT_TEAM_NO_BYPASS=1 turns the injected flag off for one session.
function global:Test-AgentYolo { (Test-Path (Join-Path $env:USERPROFILE '.agent-team\yolo')) -and -not $env:AGENT_TEAM_NO_BYPASS }

function global:claude {
    $native = Get-AgentNative 'claude' (Join-Path $env:USERPROFILE '.local\bin\claude.exe')
    $management = @('plugin','auth','login','logout','mcp','update','install','doctor','setup','help','--help','-h','--version','-V')
    $explicit = @($args | Where-Object { ($_ -split '=',2)[0] -eq '--permission-mode' }).Count -gt 0
    if ((Test-AgentYolo) -and ($args.Count -eq 0 -or $args[0] -notin $management) -and '--dangerously-skip-permissions' -notin $args -and -not $explicit) {
        & $native --dangerously-skip-permissions @args
    } else { & $native @args }
}

function global:codex {
    $native = Get-AgentNative 'codex' (Join-Path $env:USERPROFILE 'AppData\Roaming\npm\codex.cmd')
    $management = @('agents','exec','e','review','login','logout','mcp','plugin','app-server','remote-control','completion','update','doctor','sandbox','debug','apply','cloud','exec-server','features','help','queue','archive','delete','migrate-rollouts','unarchive','--help','-h','--version','-V')
    $explicit = @($args | Where-Object { ($_ -split '=',2)[0] -in @('-s','--sandbox','-a','--ask-for-approval','--approve-for-me') }).Count -gt 0
    if ((Test-AgentYolo) -and ($args.Count -eq 0 -or $args[0] -notin $management) -and '--dangerously-bypass-approvals-and-sandbox' -notin $args -and -not $explicit) {
        & $native --dangerously-bypass-approvals-and-sandbox @args
    } else { & $native @args }
}

function global:claude-team {
    & (Join-Path $env:USERPROFILE '.agent-team\windows-team.ps1') -Provider claude @args
}
function global:codex-team {
    & (Join-Path $env:USERPROFILE '.agent-team\windows-team.ps1') -Provider codex @args
}
function global:agent-team {
    $targetFile = Join-Path $env:USERPROFILE '.agent-team\wsl-target.json'
    if (-not (Test-Path $targetFile)) { throw "Missing $targetFile. Run ./install.sh inside WSL first." }
    $cfg = Get-Content -Raw $targetFile | ConvertFrom-Json
    $distro = @(); if ($cfg.distro) { $distro = @('-d', $cfg.distro) }
    & wsl.exe @distro --exec "$($cfg.home)/.local/bin/agent-team" @args
}
