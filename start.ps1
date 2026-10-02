param([string]$PythonPath = '', [int]$Port = 8765, [switch]$Legacy, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonPath) {
    $LocalPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $LocalPython) { $PythonPath = $LocalPython }
    elseif (Test-Path -LiteralPath 'D:/anaconda/envs/FinRL/python.exe') { $PythonPath = 'D:/anaconda/envs/FinRL/python.exe' }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python interpreter not found: $PythonPath" }
if ($Legacy) {
    & $PythonPath -m streamlit run app.py
} else {
    $LaunchArgs = @('scripts/serve.py', '--port', "$Port")
    if ($NoBrowser) { $LaunchArgs += '--no-browser' }
    & $PythonPath @LaunchArgs
}
