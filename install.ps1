#Requires -Version 5.1
<#
.SYNOPSIS
  Brings a Windows machine from nothing to a working solai vault.

.DESCRIPTION
  Eight stages, each idempotent and each reporting what it did. Nothing is installed twice,
  nothing already on the machine is overwritten, and every stage that cannot finish on its own
  says so and is repeated in the summary at the end.

  The public half needs no account: stages 0 to 3 leave a working Claude Code with the solai
  plugin registered. Stage 4 restores a private configuration repository and is the only stage
  that asks who you are; skip it with -PublicOnly and everything else still works.

.PARAMETER DryRun
  Report what each stage would do and write nothing.

.PARAMETER SkipApps
  Skip stage 1. For a machine that already has Git, Python and Obsidian.

.PARAMETER PublicOnly
  Stop after stage 3. No private configuration, no OneDrive, no hand-off.

.PARAMETER NoHandoff
  Run every stage but do not open the guided page at the end.

.PARAMETER CloseWhenDone
  Close this window after the summary, but only when the summary has nothing in it for you to
  do. A run that ends with a list stays on screen: closing a window over the one thing the
  reader still has to act on would be worse than leaving it open.

.PARAMETER ConfigRepo
  The private configuration repository, as owner/name. Default: the constant below.

.EXAMPLE
  irm https://raw.githubusercontent.com/supervoidproxima/solai/main/install.ps1 | iex

.EXAMPLE
  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/supervoidproxima/solai/main/install.ps1))) -DryRun
#>
[CmdletBinding()]
param(
  [switch] $DryRun,
  [switch] $SkipApps,
  [switch] $PublicOnly,
  [switch] $NoHandoff,
  [switch] $CloseWhenDone,
  [string] $PackageRepo = 'supervoidproxima/solai',
  [string] $ConfigRepo  = 'supervoidproxima/claude-config'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Native tools write progress and notices to stderr. Under 'Stop' that becomes a terminating
# error and the script dies on a line that was not a failure at all: on a fresh machine the
# Python launcher announces "Python install manager was successfully updated" and killed the
# whole run. Under PowerShell 7 one preference switches the behaviour off; under Windows
# PowerShell 5.1 - which is what `irm | iex` uses - there is no such switch, so every native
# call goes through Invoke-Native, which lowers the preference for the duration and decides
# success by exit code.
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
  $PSNativeCommandUseErrorActionPreference = $false
}
$script:NativeExit = 0
function Invoke-Native {
  param(
    [Parameter(Mandatory)] [string] $Exe,
    [Parameter(ValueFromRemainingArguments = $true)] [object[]] $Arguments
  )
  # A caller that hands over a prepared argument list - `Invoke-Native 'git' @($helper + @('fetch'))`
  # - is building an array, not splatting one, so the whole list arrives as a single element and
  # collapses into one space-joined token on the command line. Flatten it here instead of asking
  # every call site to remember which form it used.
  $argv = @()
  foreach ($a in $Arguments) { $argv += @($a) }
  $argv = [string[]] @($argv | Where-Object { $null -ne $_ })
  $saved = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $out = & $Exe @argv 2>&1
    $script:NativeExit = $LASTEXITCODE
  } catch {
    $out = $_.Exception.Message
    $script:NativeExit = 1
  } finally {
    $ErrorActionPreference = $saved
  }
  return (($out | Out-String).Trim())
}

# --------------------------------------------------------------------------- reporting
$script:Stage   = 0
$script:Total   = 8
$script:Todo    = New-Object System.Collections.Generic.List[string]
$script:Failed  = $false

function Write-Stage([string] $Name) {
  Write-Host ''
  Write-Host ("[{0}/{1}] {2}" -f $script:Stage, $script:Total, $Name) -ForegroundColor Cyan
  $script:Stage++
}
function Say([string] $Verdict, [string] $Text) {
  $colour = switch ($Verdict) {
    'ok'        { 'Green' }
    'installed' { 'Green' }
    'skipped'   { 'DarkGray' }
    'would'     { 'DarkGray' }
    'action'    { 'Yellow' }
    'failed'    { 'Red' }
    default     { 'Gray' }
  }
  Write-Host ("      {0,-10} {1}" -f $Verdict, $Text) -ForegroundColor $colour
}
function Need([string] $Text) {
  $script:Todo.Add($Text) | Out-Null
  Say 'action' $Text
}
function Have([string] $Command) {
  $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# --------------------------------------------------------------------------- 0. preflight
Write-Stage 'preflight'

# A machine can carry several OneDrive roots (personal plus one per work tenant), and the
# environment variable names only one of them. More than one root can hold an 'Obsidian Vaults'
# folder too, so taking the first match is not enough: on a machine whose personal OneDrive holds
# a few leftover vaults and whose work tenant holds every real one, first-match pointed the guided
# page at the wrong root. Rank instead - a root that already holds a solai place wins, then the
# root with the most vaults in it, and the discovery order breaks any remaining tie.
$oneDriveRoots = @(Get-ChildItem $env:USERPROFILE -Directory -Filter 'OneDrive*' -ErrorAction SilentlyContinue |
                   Select-Object -ExpandProperty FullName)
foreach ($e in @($env:OneDriveCommercial, $env:OneDrive)) {
  if ($e -and ($oneDriveRoots -notcontains $e)) { $oneDriveRoots += $e }
}
$vaultRoot = $null
$onedrive  = $null
$ranked    = @()
for ($i = 0; $i -lt $oneDriveRoots.Count; $i++) {
  $root      = $oneDriveRoots[$i]
  $candidate = Join-Path $root 'Obsidian Vaults'
  if (-not (Test-Path $candidate)) { continue }
  $vaults = @(Get-ChildItem $candidate -Directory -ErrorAction SilentlyContinue)
  $places = @($vaults | Where-Object { Test-Path (Join-Path $_.FullName '_system/os/answers.toml') })
  $ranked += [pscustomobject]@{ Root = $root; Vaults = $candidate; Places = $places.Count; Count = $vaults.Count; Order = $i }
}
if ($ranked.Count -gt 0) {
  $best = @($ranked | Sort-Object @{ Expression = 'Places'; Descending = $true },
                                  @{ Expression = 'Count';  Descending = $true },
                                  @{ Expression = 'Order';  Descending = $false })[0]
  $onedrive  = $best.Root
  $vaultRoot = $best.Vaults
} elseif ($oneDriveRoots.Count -gt 0) {
  $onedrive  = $oneDriveRoots[0]
  $vaultRoot = Join-Path $onedrive 'Obsidian Vaults'
}
$claudeDir = Join-Path $env:USERPROFILE '.claude'
$marketDir = Join-Path $claudeDir 'plugins\marketplaces\solai'

# Obsidian installs per user under Programs\; the other two paths cover older per-user and
# machine-wide installs.
$obsidian = $null
foreach ($o in @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'),
    (Join-Path $env:LOCALAPPDATA 'Obsidian\Obsidian.exe'),
    (Join-Path $env:ProgramFiles 'Obsidian\Obsidian.exe'))) {
  if (Test-Path $o) { $obsidian = $o; break }
}

# `python` on a bare Windows machine is often the Store app-execution alias: it is on PATH, it
# answers, and it is not an interpreter. Believe a version only when it looks like one, and try
# the py launcher before giving up.
$pyVersion = $null
$pyExe     = $null
foreach ($candidate in @(@('python', @('-c', "import sys;print('%d.%d' % sys.version_info[:2])")),
                         @('py',     @('-3', '-c', "import sys;print('%d.%d' % sys.version_info[:2])")))) {
  if (-not (Have $candidate[0])) { continue }
  $reported = Invoke-Native $candidate[0] @($candidate[1])
  $match = [regex]::Match($reported, '(?m)^\s*(\d+\.\d+)\s*$')
  if ($script:NativeExit -eq 0 -and $match.Success) {
    $pyVersion = $match.Groups[1].Value
    $pyExe     = $candidate[0]
    break
  }
}
$pyOk = [bool]($pyVersion -and ([version]$pyVersion -ge [version]'3.11'))

# winget ships with App Installer, so a machine can have it installed and unreachable at the same
# time: the Store alias folder is not always on PATH, and the run used to stop and tell the reader
# to install something they already had. Look for it where it actually lives, then put its folder
# on PATH for this session and for the user permanently.
$wingetNote = $null
$wingetDir  = $null
if (-not (Have 'winget')) {
  $aliasDir   = Join-Path (Join-Path $env:LOCALAPPDATA 'Microsoft') 'WindowsApps'
  $candidates = @(Join-Path $aliasDir 'winget.exe')
  try {
    foreach ($a in @(Get-AppxPackage -Name 'Microsoft.DesktopAppInstaller' -ErrorAction SilentlyContinue)) {
      if ($a.InstallLocation) { $candidates += (Join-Path $a.InstallLocation 'winget.exe') }
    }
  } catch { }
  foreach ($c in $candidates) {
    if ((-not $wingetDir) -and (Test-Path $c)) { $wingetDir = Split-Path $c -Parent }
  }
  if ($wingetDir) {
    if (($env:PATH -split ';') -notcontains $wingetDir) { $env:PATH = $env:PATH.TrimEnd(';') + ';' + $wingetDir }
    $userPath = [string] [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (($userPath -split ';') -notcontains $wingetDir) {
      if ($DryRun) {
        $wingetNote = "would put winget on your PATH: $wingetDir"
      } else {
        [Environment]::SetEnvironmentVariable('PATH', ($userPath.TrimEnd(';') + ';' + $wingetDir).TrimStart(';'), 'User')
        $wingetNote = "winget was installed but not on PATH: added $wingetDir"
      }
    } else {
      $wingetNote = "winget found at $wingetDir, this session picks it up"
    }
  }
}

$present = [ordered]@{
  'winget'      = ((Have 'winget') -or ($null -ne $wingetDir))
  'git'         = (Have 'git')
  'python 3.11+'= $pyOk
  'gh'          = (Have 'gh')
  'claude'      = (Have 'claude')
  'Obsidian'    = ($null -ne $obsidian)
  '~/.claude'   = (Test-Path $claudeDir)
  'vault root'  = [bool]($vaultRoot -and (Test-Path $vaultRoot))
}
foreach ($k in $present.Keys) {
  Say $(if ($present[$k]) { 'ok' } else { 'missing' }) $k
}
if ($pyVersion) {
  Say $(if ($pyOk) { 'ok' } else { 'action' }) ("python {0}, via {1}" -f $pyVersion, $pyExe)
} elseif (Have 'python') {
  Say 'action' 'python is on PATH but does not answer: the Microsoft Store alias, not an interpreter'
}
if ($wingetNote) { Say 'ok' $wingetNote }

if (-not $present['winget']) {
  Say 'failed' 'winget is required and was not found. Install App Installer from the Microsoft Store, or turn its app-execution alias back on in Settings, then run this again.'
  return
}

if ($DryRun) {
  Write-Host ''
  Write-Host '      dry run: stages 1 to 8 would run as listed above. Nothing was written.' -ForegroundColor DarkGray
  if ($CloseWhenDone) {
    Write-Host '      would close this window afterwards, unless the summary had a list in it.' -ForegroundColor DarkGray
  }
  return
}

# --------------------------------------------------------------------------- 1. applications
Write-Stage 'applications'

if ($SkipApps) {
  Say 'skipped' '-SkipApps'
} else {
  $packages = @(
    @{ Id = 'Git.Git';             Name = 'Git';         Have = $present['git'] },
    @{ Id = 'Python.Python.3.13';  Name = 'Python 3.13'; Have = $pyOk },
    @{ Id = 'Obsidian.Obsidian';   Name = 'Obsidian';    Have = $present['Obsidian'] },
    @{ Id = 'GitHub.cli';          Name = 'GitHub CLI';  Have = $present['gh'] }
  )
  foreach ($p in $packages) {
    if ($p.Have) { Say 'ok' $p.Name; continue }
    Write-Host ("      installing  {0} - approve the elevation prompt when Windows asks ..." -f $p.Name) -ForegroundColor DarkGray
    $null = Invoke-Native 'winget' 'install' '--id' $p.Id '--exact' '--silent' '--accept-package-agreements' '--accept-source-agreements'
    switch ($script:NativeExit) {
      0       { Say 'installed' $p.Name }
      # 1602 is the MSI code for "cancelled at the prompt", which on this path means the UAC
      # dialog was dismissed rather than anything being wrong with the package.
      1602    { Need ("{0}: the elevation prompt was dismissed. Run: winget install --id {1}" -f $p.Name, $p.Id) }
      default { Need ("install {0} by hand (exit {2}): winget install --id {1}" -f $p.Name, $p.Id, $script:NativeExit) }
    }
  }
  Say 'ok' 'PATH changes take effect in a new terminal'
}

# --------------------------------------------------------------------------- 2. Claude Code
Write-Stage 'Claude Code'

if (Have 'claude') {
  Say 'ok' ("already installed: " + (Invoke-Native 'claude' '--version'))
} else {
  # The native installer needs no elevation and keeps itself updated afterwards.
  irm https://claude.ai/install.ps1 | iex
  $local = Join-Path $env:USERPROFILE '.local\bin'
  if (Test-Path (Join-Path $local 'claude.exe')) {
    $env:Path = "$local;$env:Path"
    Say 'installed' (Invoke-Native 'claude' '--version')
  } else {
    Need 'install Claude Code by hand: irm https://claude.ai/install.ps1 | iex'
  }
}

# --------------------------------------------------------------------------- 3. the plugin
Write-Stage 'the solai plugin'

# A GitHub-sourced marketplace is cloned into plugins\marketplaces\<name>; a directory-sourced
# one is registered in place. Ask the register, not the disk.
$known      = Join-Path $claudeDir 'plugins\known_marketplaces.json'
$registered = (Test-Path $known) -and ((Get-Content $known -Raw) -match '"solai"')

if (-not (Have 'claude')) {
  Need ('register the plugin once Claude Code is installed: /plugin marketplace add ' + $PackageRepo)
} elseif ($registered) {
  $null = Invoke-Native 'claude' 'plugin' 'marketplace' 'update' 'solai'
  Say 'ok' 'marketplace already registered, updated'
} else {
  $null = Invoke-Native 'claude' 'plugin' 'marketplace' 'add' $PackageRepo
  if ($script:NativeExit -eq 0) { Say 'installed' ("marketplace " + $PackageRepo) }
  else { Need ("run in a Claude Code session: /plugin marketplace add " + $PackageRepo) }

  $null = Invoke-Native 'claude' 'plugin' 'install' 'solai@solai'
  if ($script:NativeExit -eq 0) { Say 'installed' 'plugin solai@solai' }
  else { Need 'run in a Claude Code session: /plugin install solai@solai' }
}

if (Have 'claude') {
  $installed = Invoke-Native 'claude' 'plugin' 'list'
  Say $(if ($installed -match 'solai') { 'ok' } else { 'action' }) 'claude plugin list reports solai'
}

if ($PublicOnly) {
  Write-Host ''
  Write-Host '      -PublicOnly: stopping here. Run `claude` and then /solai.' -ForegroundColor DarkGray
  return
}

# --------------------------------------------------------------------------- 4. private config
Write-Stage 'private configuration'

$configMarker = Join-Path $claudeDir 'CLAUDE.md'
if (Test-Path $configMarker) {
  Say 'ok' 'a configuration is already present, leaving it alone'
} else {
  $answer = Read-Host ("      restore the private configuration from {0}? (y/N)" -f $ConfigRepo)
  if ($answer -notmatch '^(y|yes)$') {
    Say 'skipped' 'no private configuration'
  } elseif (-not (Have 'git')) {
    Need 'install Git, then run this script again'
  } else {
    # Git for Windows bundles Git Credential Manager, which signs in through the browser and
    # needs no elevation. The GitHub CLI is used only if it happens to be here and logged in:
    # its installer is machine-wide, and on a locked-down machine it cannot be installed at all.
    $helper = @()
    if (Have 'gh') {
      $status = Invoke-Native 'gh' 'auth' 'status'
      if ($status -match 'Logged in') {
        $helper = @('-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential')
        Say 'ok' 'authenticating through the GitHub CLI'
      }
    }
    if ($helper.Count -eq 0) {
      Say 'ok' 'authenticating through Git Credential Manager: a browser window will open once'
    }
    # ~/.claude already exists (Claude Code made it), so `git clone` would refuse. Fetch into it.
    New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
    Push-Location $claudeDir
    try {
      if (-not (Test-Path (Join-Path $claudeDir '.git'))) { $null = Invoke-Native 'git' 'init' '--quiet' }
      $remotes = Invoke-Native 'git' 'remote'
      if ($remotes -notmatch '(?m)^origin$') {
        $null = Invoke-Native 'git' 'remote' 'add' 'origin' ("https://github.com/{0}.git" -f $ConfigRepo)
      }
      $null = Invoke-Native 'git' @($helper + @('fetch', '--quiet', 'origin'))
      if ($script:NativeExit -ne 0) { throw 'fetch failed' }
      $remoteInfo = Invoke-Native 'git' @($helper + @('remote', 'show', 'origin'))
      $branch = ([regex]::Match($remoteInfo, 'HEAD branch:\s*(\S+)')).Groups[1].Value
      if (-not $branch) { $branch = 'main' }
      $null = Invoke-Native 'git' 'checkout' '-f' '-B' $branch ("origin/{0}" -f $branch) '--quiet'
      if ($script:NativeExit -ne 0) { throw 'checkout failed' }
      Say 'installed' ("configuration restored from {0} ({1})" -f $ConfigRepo, $branch)
    } catch {
      Need ("restore the configuration by hand: git clone https://github.com/{0}.git" -f $ConfigRepo)
    } finally {
      Pop-Location
    }
  }
}

# --------------------------------------------------------------------------- 5. local settings
Write-Stage 'machine-local settings'

$localSettings = Join-Path $claudeDir 'settings.local.json'
$template      = Join-Path $claudeDir 'templates\settings.local.template.json'
if (Test-Path $localSettings) {
  Say 'ok' 'settings.local.json already present'
} elseif (Test-Path $template) {
  Copy-Item $template $localSettings
  Say 'installed' 'settings.local.json from the template'
} else {
  Say 'skipped' 'no template in this configuration'
}
Say 'ok' 'credentials never sync: the first `claude` run opens a browser to log in'

# --------------------------------------------------------------------------- 6. OneDrive
Write-Stage 'OneDrive and the vaults'

if (-not $onedrive) {
  Need 'sign in to OneDrive, then run this script again to pick up the vault folder'
} elseif ($vaultRoot -and (Test-Path $vaultRoot)) {
  $count = (Get-ChildItem $vaultRoot -Directory -ErrorAction SilentlyContinue).Count
  Say 'ok' ("{0} ({1} folders)" -f $vaultRoot, $count)
  Say 'ok' 'mark the folder "always keep on this device" in File Explorer: online-only files break git and Obsidian'
} else {
  Write-Host ("      waiting for {0} to appear (Ctrl+C to stop) ..." -f $vaultRoot) -ForegroundColor DarkGray
  $deadline = (Get-Date).AddMinutes(10)
  while (-not (Test-Path $vaultRoot) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 10 }
  if (Test-Path $vaultRoot) { Say 'ok' $vaultRoot }
  else { Need ("let OneDrive finish syncing, then open a vault from {0}" -f $vaultRoot) }
}

# --------------------------------------------------------------------------- 7. doctor
Write-Stage 'doctor'

if (Have 'claude') {
  (Invoke-Native 'claude' 'doctor') -split "`r?`n" | Select-Object -First 12 |
    ForEach-Object { Write-Host ("      " + $_) -ForegroundColor DarkGray }
}

$pkg = Join-Path $marketDir 'plugins\solai'
if (-not (Test-Path $pkg)) { $pkg = Join-Path $claudeDir 'solai\plugins\solai' }
$runner = Join-Path $pkg 'tests\run_tests.py'
if ((Test-Path $runner) -and $pyExe) {
  $out = Invoke-Native $pyExe $runner
  $line = ($out -split "`n" | Where-Object { $_ -match 'assertions passed' } | Select-Object -First 1)
  if (-not $line) { $line = 'test runner produced no count line' }
  Say $(if ($out -match 'GREEN') { 'ok' } else { 'action' }) ("$line".Trim())
} else {
  Say 'skipped' 'test runner not found at the installed package path'
}

# --------------------------------------------------------------------------- 8. hand off
Write-Stage 'the guided page'

$serve = Join-Path $pkg 'skills\solai-scaffold\serve.py'
if ($NoHandoff) {
  Say 'skipped' '-NoHandoff'
} elseif ((Test-Path $serve) -and $pyExe) {
  Say 'ok' 'opening the guided page. Close it with Ctrl+C when you are done.'
  # Not through Invoke-Native: this one is meant to stay in the foreground and print as it goes.
  # --once: the page stops itself once a session is started, so this terminal is handed back
  # instead of being held open by a server behind the window the reader is now working in.
  if ($vaultRoot) { & $pyExe $serve --vaults $vaultRoot --once }
  else { & $pyExe $serve --once }
} else {
  if (Test-Path $serve) {
    Need ("start the guided page by hand: py `"{0}`"" -f $serve)
  } else {
    Need 'the guided page was not found in the installed package: reinstall the plugin, then run serve.py by hand'
  }
}

# --------------------------------------------------------------------------- summary
Write-Host ''
if ($script:Todo.Count -eq 0) {
  Write-Host 'Done. Nothing is left for you to do by hand.' -ForegroundColor Green
} else {
  Write-Host ("Done, with {0} thing(s) left for you:" -f $script:Todo.Count) -ForegroundColor Yellow
  foreach ($t in $script:Todo) { Write-Host ("  - " + $t) -ForegroundColor Yellow }
}
Write-Host ''

# The window this ran in has nothing left to hold: the session opened in a console of its own
# and the page stopped itself. Closing it is Stop-Process on this host rather than `exit`,
# which under `irm | iex` ends the piped script and leaves the prompt sitting there.
if ($CloseWhenDone) {
  if ($script:Todo.Count -gt 0) {
    Write-Host '  this window stays open: the list above is for you.' -ForegroundColor Yellow
  } else {
    Write-Host '  closing this window.' -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
    Stop-Process -Id $PID
  }
}
