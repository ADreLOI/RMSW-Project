[CmdletBinding()]
param(
    [ValidateSet('menu','start','stop')][string]$Action = 'menu',
    [ValidateSet('docker','native')][string]$Mode = 'docker',
    [ValidateSet('engine','both')][string]$Services = 'both',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$sim = Join-Path $repo 'code/simulator'
$stateDir = Join-Path $repo '.lab-launcher'
$venv = Join-Path $sim '.venv/Scripts/python.exe'
$localUrl = 'http://127.0.0.1:8768'
$requestedRelay = $env:LAB_RELAY_URL
$requestedKey = $env:LAB_ENGINE_KEY
[void][IO.Directory]::CreateDirectory($stateDir)

function Get-LocalKey {
    $file = Join-Path $stateDir 'engine.key'
    if (-not (Test-Path -LiteralPath $file)) {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        [IO.File]::WriteAllText($file, [Convert]::ToBase64String($bytes))
    }
    return [IO.File]::ReadAllText($file).Trim()
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose --project-directory $repo -f (Join-Path $repo 'compose.yaml') @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose non ha completato il comando. Controlla che Docker Desktop sia avviato in modalita Linux.' }
}

function Get-NativeService($name) {
    $infoFile = Join-Path $stateDir "$name.json"
    if (Test-Path -LiteralPath $infoFile) {
        $info = Get-Content -LiteralPath $infoFile -Raw | ConvertFrom-Json
        $process = Get-Process -Id $info.pid -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $info.started) {
            return $process
        }
    }
}

function Test-DockerService($name) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    # Native mode also works when Docker Desktop is stopped or has never been installed.
    $ErrorActionPreference = 'Continue'
    $running = & docker compose --project-directory $repo -f (Join-Path $repo 'compose.yaml') ps -q $name 2>$null
    return $LASTEXITCODE -eq 0 -and [bool]$running
}

function Initialize-Python {
    if (-not (Test-Path -LiteralPath $venv)) {
        $base = $env:LAB_PYTHON
        if ($base) { & $base -m venv (Join-Path $sim '.venv') }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $sim '.venv') }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv (Join-Path $sim '.venv') }
        else { throw 'Installa Python 3.10+ per la modalita nativa, oppure scegli Docker.' }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venv)) {
            throw 'Serve Python 3.10+ per creare .venv. Se hai solo Docker, scegli la modalita Docker.'
        }
    }
    & $venv -c "import importlib.util as u, sys; sys.exit(any(u.find_spec(p) is None for p in ('aiohttp','matplotlib','numpy','psutil','usv_sim','webapp')))"
    if ($LASTEXITCODE -ne 0) {
        & $venv -m pip install -e (Join-Path $repo 'code[deploy]')
        if ($LASTEXITCODE -ne 0) { throw 'Installazione delle dipendenze Python fallita.' }
    }
}

function Start-Native($name) {
    $process = Get-NativeService $name
    $infoFile = Join-Path $stateDir "$name.json"
    if ($process) {
        $info = Get-Content -LiteralPath $infoFile -Raw | ConvertFrom-Json
        if ($name -eq 'engine' -and $info.relay -ne $env:LAB_RELAY_URL) {
            throw 'Il motore usa un altro server. Fermalo dal menu prima di cambiare destinazione.'
        }
        if (Test-Path -LiteralPath $info.stop) { throw "$name si sta arrestando." }
        return
    }
    $instance = [guid]::NewGuid().ToString('N')
    $env:LAB_STOP_FILE = Join-Path $stateDir "$instance.stop"
    $env:LAB_READY_FILE = Join-Path $stateDir "$instance.ready"
    $module = if ($name -eq 'engine') { 'usv_sim.engine' } else { 'webapp.relay' }
    $process = Start-Process -FilePath $venv -ArgumentList '-m',$module -WorkingDirectory $sim -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir "$name.out.log") -RedirectStandardError (Join-Path $stateDir "$name.err.log")
    $info = @{ pid=$process.Id; started=$process.StartTime.ToUniversalTime().Ticks.ToString(); stop=$env:LAB_STOP_FILE; ready=$env:LAB_READY_FILE; relay=$env:LAB_RELAY_URL }
    [IO.File]::WriteAllText($infoFile, ($info | ConvertTo-Json))
    for ($i=0; $i -lt 120; $i++) {
        if ($process.HasExited) { throw (Get-Content (Join-Path $stateDir "$name.err.log") -Tail 12 | Out-String) }
        if (Test-Path -LiteralPath $info.ready) { return }
        Start-Sleep -Milliseconds 250
    }
    [IO.File]::WriteAllText($info.stop, '')
    throw "$name non pronto. Controlla $stateDir\$name.err.log"
}

function Stop-Native($name) {
    $process = Get-NativeService $name
    $file = Join-Path $stateDir "$name.json"
    if (-not (Test-Path -LiteralPath $file)) { return }
    $info = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
    if ($process) {
        [IO.File]::WriteAllText($info.stop, '')
        if (-not $process.WaitForExit(15000)) {
            Write-Host "$name sta completando il lavoro in coda. Si fermera in automatico."
            return
        }
    }
    foreach ($path in @($file, $info.ready, $info.stop)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
}

function Wait-LocalStack {
    for ($i=0; $i -lt 45; $i++) {
        try {
            $health = Invoke-RestMethod "$localUrl/health" -TimeoutSec 2
            if ($health.service -eq 'usv-web' -and $health.engine_connected) { return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'Il pannello non ha confermato il collegamento al motore. Controlla i log indicati nella guida.'
}

function Manage($operation, $runtime, $scope) {
    $guard = [IO.File]::Open((Join-Path $stateDir 'menu.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $started = @()
    try {
        $remote = $scope -eq 'engine' -and $requestedRelay
        $env:LAB_ENGINE_KEY = if ($requestedKey) { $requestedKey } else { Get-LocalKey }
        if ($remote -and -not $requestedKey -and $operation -eq 'start') { throw 'Per un server remoto imposta anche LAB_ENGINE_KEY.' }
        $env:LAB_RELAY_URL = if ($remote) { $requestedRelay } elseif ($runtime -eq 'docker') { 'http://web:8768' } else { $localUrl }
        $env:LAB_PUBLIC_ORIGIN = $localUrl
        $env:LAB_WEB_PASSWORD = ''
        $env:PORT = '8768'
        $env:LAB_WEB_BIND = '127.0.0.1'
        $names = if ($scope -eq 'both') { @('web','engine') } else { @('engine') }
        if ($operation -eq 'stop') {
            if ($runtime -eq 'docker') {
                Invoke-Compose (@('stop') + $names)
                Invoke-Compose (@('rm','-f') + $names)
            } else {
                Stop-Native 'engine'
                if ($scope -eq 'both') { Stop-Native 'web' }
            }
            Write-Host 'Arresto richiesto.'
            return
        }
        if ($runtime -eq 'native') { Initialize-Python }
        foreach ($name in $names) {
            if ($runtime -eq 'docker') {
                if (Get-NativeService $name) { throw "Ferma prima $name in modalita nativa." }
                $running = Invoke-Compose @('ps','-q',$name)
                if ($running -and $name -eq 'engine') {
                    $target = & docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' $running | Where-Object { $_ -like 'LAB_RELAY_URL=*' }
                    if ($target -ne "LAB_RELAY_URL=$env:LAB_RELAY_URL") { throw 'Ferma prima il motore Docker per cambiare destinazione.' }
                }
                if (-not $running) {
                    $started += $name
                    Invoke-Compose @('up','-d','--build','--no-deps','--wait','--wait-timeout','90',$name)
                }
            } else {
                if (Test-DockerService $name) { throw "Ferma prima $name in modalita Docker." }
                if (-not (Get-NativeService $name)) { $started += $name }
                Start-Native $name
            }
        }
        if ($scope -eq 'both') {
            Wait-LocalStack
            Write-Host "Webapp pronta: $localUrl"
            if (-not $NoBrowser) { Start-Process $localUrl }
        } else {
            Write-Host "Motore avviato. Destinazione: $env:LAB_RELAY_URL"
        }
    } catch {
        $failure = $_
        [array]::Reverse($started)
        foreach ($name in $started) {
            try {
                if ($runtime -eq 'native') { Stop-Native $name }
                else { Invoke-Compose @('stop',$name) }
            } catch { Write-Warning $_.Exception.Message }
        }
        throw $failure
    } finally { $guard.Dispose() }
}

if ($Action -ne 'menu') { Manage $Action $Mode $Services; exit 0 }
$choices = @(
    @('start','docker','engine'), @('start','native','engine'),
    @('start','docker','both'), @('start','native','both'),
    @('stop','docker','engine'), @('stop','native','engine'),
    @('stop','docker','both'), @('stop','native','both')
)
while ($true) {
    Write-Host @'

USV Research Lab
  1  Avvia motore                   Docker
  2  Avvia motore                   Nativo
  3  Avvia motore + webapp locale   Docker
  4  Avvia motore + webapp locale   Nativo
  5  Ferma motore                   Docker
  6  Ferma motore                   Nativo
  7  Ferma motore + webapp          Docker
  8  Ferma motore + webapp          Nativo
  0  Esci dal menu
'@
    $selection = Read-Host 'Scelta'
    if ($selection -eq '0') { break }
    if ($selection -notmatch '^[1-8]$') { continue }
    $arguments = $choices[[int]$selection - 1]
    try { Manage @arguments } catch { Write-Host $_.Exception.Message -ForegroundColor Red }
}
