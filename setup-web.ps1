param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonPath) {
    $LocalPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $LocalPython) { $PythonPath = $LocalPython }
    elseif (Test-Path -LiteralPath 'D:/anaconda/envs/FinRL/python.exe') { $PythonPath = 'D:/anaconda/envs/FinRL/python.exe' }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python interpreter not found: $PythonPath" }
& $PythonPath -m pip install --target .runtime/python --upgrade -r requirements-web-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
Push-Location frontend
try {
    npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Open Start Lab.cmd to launch the local app.'
