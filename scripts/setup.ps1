param([switch]$WithOcr)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.python'
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    uv venv --python 3.12 .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python 3.12 environment' }
} else {
    & .venv/Scripts/python.exe -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use a Python 3.12 project environment"'
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv is not Python 3.12; preserve it and use another environment' }
}
$extras = if ($WithOcr) { '.[test,ocr]' } else { '.[test]' }
if (Test-Path -LiteralPath 'requirements.lock.txt') {
    uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Locked dependency installation failed' }
    uv pip install --python .venv/Scripts/python.exe --no-deps -e $extras
} else {
    uv pip install --python .venv/Scripts/python.exe -e $extras
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if (!(Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Host 'Ready. Configure .env, then .venv/Scripts/python.exe -m day7_rag doctor'
