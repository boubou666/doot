<#
.SYNOPSIS
    Installe doot pour l'utilisateur courant (Windows 10/11). Pas besoin d'admin.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoAutostart
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -MinSeconds 300 -MaxSeconds 1800
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -BurstMin 2 -BurstMax 5
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -BurstMin 2 -BurstMax 5 -Formation canon
#>
[CmdletBinding()]
param(
    [int]    $MinSeconds = 600,
    [int]    $MaxSeconds = 3600,
    [int]    $BurstMin   = 1,
    [int]    $BurstMax   = 1,
    [double] $BurstDelay = 0.6,
    [ValidateSet('random', 'canon')]
    [string] $Formation  = 'random',
    [switch] $NoAutostart
)

$ErrorActionPreference = 'Stop'

function Write-Head { param($Text) Write-Host "`n$Text" -ForegroundColor White }
function Write-Item { param($Text) Write-Host "  $Text" }

# Les drapeaux de salve ne sont ecrits que s'ils changent quelque chose : sans
# eux, la commande engendree reste exactement celle d'avant les salves. Le
# raccourci veut une ligne, Start-Process un tableau, d'ou les deux formes.
#
# "$BurstDelay" tient sur la culture invariante : PowerShell ne suit pas la
# locale pour ses conversions, on aura donc 0.6 et jamais 0,6, ce qu'argparse
# refuserait.
$salveArgs = @()
if ($BurstMax -gt 1) {
    $salveArgs = @('--burst-min', "$BurstMin",
                   '--burst-max', "$BurstMax",
                   '--burst-delay', "$BurstDelay")
}
$formationArgs = @()
if ($Formation -ne 'random') {
    $formationArgs = @('--formation', $Formation)
}
$autostartArgs = @($salveArgs) + @($formationArgs)
$salveTexte = if ($autostartArgs) { ' ' + ($autostartArgs -join ' ') } else { '' }

Write-Head 'doot - installation'

$Src        = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\doot'
$AppDir     = Join-Path $InstallDir 'app'
$BinDir     = Join-Path $InstallDir 'bin'

# ------------------------------------------------------------- python --------

function Find-Python {
    # Sans guillemets internes : PowerShell les mange en passant a un exe natif.
    $probeScript = 'import sys; print(sys.executable); print(sys.version_info[0]); print(sys.version_info[1])'
    $candidates = @(
        @{ File = 'py';      Args = @('-3') },
        @{ File = 'python3'; Args = @() },
        @{ File = 'python';  Args = @() }
    )

    # Le stub "Python" du Microsoft Store repond du texte libre et un code
    # d'erreur : on verifie le code de sortie et on parse defensivement.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        foreach ($c in $candidates) {
            if (-not (Get-Command $c.File -ErrorAction SilentlyContinue)) { continue }

            # @callArgs : splatting. Un @(...) litteral serait passe comme UN seul argument.
            $callArgs = @($c.Args) + @('-c', $probeScript)
            try {
                $probe = @(& $c.File @callArgs)
            } catch { continue }

            if ($LASTEXITCODE -ne 0 -or $probe.Count -lt 3) { continue }
            $exe = "$($probe[0])".Trim()
            try {
                $ver = [version]::new([int]"$($probe[1])".Trim(), [int]"$($probe[2])".Trim())
            } catch { continue }
            if ($exe -and (Test-Path $exe) -and $ver -ge [version]'3.8') { return $exe }
        }
    } finally {
        $ErrorActionPreference = $previous
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Item 'Python 3.8+ est introuvable.'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Item 'Installe-le puis relance ce script :'
        Write-Item '  winget install -e --id Python.Python.3.12'
    } else {
        Write-Item 'Installe-le depuis https://www.python.org/downloads/ (coche "tcl/tk" et "Add to PATH").'
    }
    exit 1
}
Write-Item "python      : $python"

$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }

& $python -c 'import tkinter' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Item 'tkinter     : MANQUANT -> reinstalle Python en cochant "tcl/tk and IDLE"'
} else {
    Write-Item 'tkinter     : OK'
}
Write-Item 'audio       : winsound (integre a Windows)'

# ------------------------------------------------------------ fichiers -------

Write-Head 'Copie des fichiers'

# Un daemon en cours garde le dossier du code ouvert : sous Windows on ne peut
# pas remplacer des fichiers verrouilles. On l'arrete avant, sinon une simple
# reinstallation par-dessus echoue sur un message obscur.
$DataDir = Join-Path $env:LOCALAPPDATA 'doot'
$PidFile = Join-Path $DataDir 'doot.pid'
$daemonTournait = $false
if (Test-Path $PidFile) {
    $daemonPid = (Get-Content $PidFile -Raw).Trim()
    if ($daemonPid -match '^\d+$' -and (Get-Process -Id $daemonPid -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $daemonPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        $daemonTournait = $true
        Write-Item "daemon      : arrete (pid $daemonPid) le temps de la copie"
        Start-Sleep -Milliseconds 400
    }
}

if (Test-Path $AppDir) {
    try {
        Remove-Item $AppDir -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Item 'ATTENTION   : impossible de remplacer le code, un processus le retient.'
        Write-Item '  -> ferme doot (doot --stop) puis relance ce script.'
        exit 1
    }
}
New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
Copy-Item (Join-Path $Src 'doot') -Destination (Join-Path $AppDir 'doot') -Recurse -Force
Write-Item "code        : $AppDir\doot"

$EngineVersion = '0.2.1'
$EngineUrl = "https://github.com/boubou666/desktop-overlay/releases/download/v$EngineVersion/desktop_overlay-$EngineVersion-py3-none-any.whl"
$EngineSha256 = 'c752c46c077390a1f6cc6569dae09df302a2d0810b6a555122366be38928c972'
$EngineInstaller = @"
import hashlib
import io
import sys
import urllib.request
import zipfile

url, expected, target = sys.argv[1:]
with urllib.request.urlopen(url, timeout=30) as response:
    wheel = response.read()
actual = hashlib.sha256(wheel).hexdigest()
if actual != expected:
    raise SystemExit(
        "desktop-overlay: SHA-256 inattendu ({} au lieu de {})".format(
            actual, expected
        )
    )
with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
    archive.extractall(target)
"@
& $python -c $EngineInstaller $EngineUrl $EngineSha256 $AppDir
if ($LASTEXITCODE -ne 0) {
    Write-Item "Echec de l'installation de desktop-overlay $EngineVersion."
    exit 1
}
Write-Item "moteur      : desktop-overlay $EngineVersion"

$cmdPath = Join-Path $BinDir 'doot.cmd'
@"
@echo off
set "PYTHONPATH=$AppDir;%PYTHONPATH%"
"$python" -m doot %*
"@ | Set-Content -Path $cmdPath -Encoding ASCII
Write-Item "commande    : $cmdPath"

# PATH utilisateur (pas de PATH machine, pas d'admin)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$BinDir", 'User')
    Write-Item "PATH        : $BinDir ajoute (rouvre ton terminal)"
} else {
    Write-Item 'PATH        : deja configure'
}

# --------------------------------------------------------- demarrage ---------

$startup  = [Environment]::GetFolderPath('Startup')
$lnkPath  = Join-Path $startup 'doot.lnk'

if (-not $NoAutostart) {
    Write-Head 'Demarrage automatique'
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = "-m doot --min $MinSeconds --max $MaxSeconds$salveTexte --quiet"
    $lnk.WorkingDirectory = $AppDir
    $lnk.Description      = 'doot - squelette trompettiste saisonnier'
    $lnk.WindowStyle      = 7
    $lnk.Save()

    # PYTHONPATH utilisateur pour que le raccourci trouve le module
    $envPyPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')
    if (-not $envPyPath -or $envPyPath -notlike "*$AppDir*") {
        $newPyPath = if ($envPyPath) { "$envPyPath;$AppDir" } else { $AppDir }
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $newPyPath, 'User')
    }
    Write-Item "raccourci   : $lnkPath"
    Write-Item 'doot demarrera a la prochaine ouverture de session.'
} else {
    if (Test-Path $lnkPath) { Remove-Item $lnkPath -Force }
    Write-Item 'demarrage automatique ignore (-NoAutostart)'
}

# Fiche d'installation, relue par `doot --update`.
$RecordDir = Join-Path $env:LOCALAPPDATA 'doot'
New-Item -ItemType Directory -Path $RecordDir -Force | Out-Null
$commit = ''
if ((Test-Path (Join-Path $Src '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    $commit = (& git -C $Src rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { $commit = '' }
}
[ordered]@{
    source       = $Src
    commit       = "$commit".Trim()
    min          = $MinSeconds
    max          = $MaxSeconds
    burst_min    = $BurstMin
    burst_max    = $BurstMax
    burst_delay  = $BurstDelay
    formation    = $Formation
    autostart    = (-not $NoAutostart.IsPresent)
    app_dir      = $AppDir
    bin_dir      = $BinDir
    python       = $python
    pythonw      = $pythonw
    platform     = 'Windows'
    installed_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
} | ConvertTo-Json | Set-Content -Path (Join-Path $RecordDir 'install.json') -Encoding utf8
Write-Item "fiche       : $RecordDir\install.json"

if ($daemonTournait) {
    $env:PYTHONPATH = "$AppDir;$env:PYTHONPATH"
    Start-Process -FilePath $pythonw `
        -ArgumentList (@("-m", "doot", "--min", $MinSeconds, "--max", $MaxSeconds) + $autostartArgs + @("--quiet")) `
        -WorkingDirectory $AppDir -WindowStyle Hidden
    Write-Item 'daemon      : redemarre avec le nouveau code'
}

Write-Head 'Termine'
Write-Item 'Teste tout de suite : doot --once --ignore-season'
Write-Item 'Etat                : doot --status'
Write-Item 'Desinstaller        : powershell -ExecutionPolicy Bypass -File .\uninstall.ps1'
Write-Host ''
$env:PYTHONPATH = "$AppDir;$env:PYTHONPATH"
& $python -m doot --art
