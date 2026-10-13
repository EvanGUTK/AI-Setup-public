param(
    [Parameter(Mandatory=$true)][ValidateSet('claude','codex')][string]$Provider,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$TeamArgs
)
$ErrorActionPreference = 'Stop'
# Where the Linux side lives: written by install.sh into wsl-target.json (distro name + Linux home).
$target = Join-Path $env:USERPROFILE '.agent-team\wsl-target.json'
if (-not (Test-Path $target)) { throw "Missing $target. Run ./install.sh inside WSL first." }
$cfg = Get-Content -Raw $target | ConvertFrom-Json
$distro = @(); if ($cfg.distro) { $distro = @('-d', $cfg.distro) }
$here = $PWD.ProviderPath
if ($here -match '^\\\\wsl(?:\$|\.localhost)\\[^\\]+\\(.*)$') {
    $linuxPath = '/' + ($Matches[1] -replace '\\','/')
} else {
    $linuxPath = (& wsl.exe @distro --exec wslpath -a $here | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $linuxPath.StartsWith('/')) {
        throw "Cannot translate current directory to WSL: $here"
    }
}
& wsl.exe @distro --exec "$($cfg.home)/.local/bin/$Provider-team" -C $linuxPath @TeamArgs
exit $LASTEXITCODE
