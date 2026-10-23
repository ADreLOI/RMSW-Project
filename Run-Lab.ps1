param(
    [ValidateSet('Dashboard','Test','Smoke','Full')][string]$Action = 'Dashboard',
    [switch]$Setup,
    [ValidateRange(1024,65535)][int]$Port = 8768,
    [ValidateRange(1,8)][int]$Workers = 2
)
$ErrorActionPreference = 'Stop'
$simulationPath = Join-Path $PSScriptRoot 'code/simulation'
$venvPython = Join-Path $simulationPath '.venv/Scripts/python.exe'
if ($Setup) {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & python -m venv (Join-Path $simulationPath '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    }
    & $venvPython -m pip install -e $simulationPath
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
}
$labPython = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = (Join-Path $simulationPath 'src') + [IO.Path]::PathSeparator + $previousPythonPath
Push-Location -LiteralPath $simulationPath
try {
    & $labPython -c 'import numpy, matplotlib, psutil'
    if ($LASTEXITCODE -ne 0) { throw 'Dependencies are missing. Run this script again with -Setup.' }
    switch ($Action) {
        'Dashboard' { & $labPython -m usv_sim.dashboard --port $Port }
        'Test' { & $labPython -m unittest discover -s tests -v }
        'Smoke' { & $labPython -m usv_sim.workflow --preset smoke }
        'Full' { & $labPython -m usv_sim.workflow --preset full --workers $Workers }
    }
    if ($LASTEXITCODE -ne 0) { throw "Lab command failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
