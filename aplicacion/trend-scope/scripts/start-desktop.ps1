$ErrorActionPreference = 'Stop'
$earthAppRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $earthAppRoot
$earthPython = Join-Path $earthAppRoot '.venv\Scripts\python.exe'
$earthTauri = Join-Path $earthAppRoot 'node_modules\.bin\tauri.cmd'
if (!(Test-Path -LiteralPath $earthPython) -or !(Test-Path -LiteralPath $earthTauri)) {
    throw 'Faltan dependencias. Consultá README.md para preparar Python y Node.'
}
$env:VIRTUAL_ENV = Join-Path $earthAppRoot '.venv'
$env:PYO3_PYTHON = $earthPython
$earthPythonBase = & $earthPython -c 'import sys; print(sys.base_prefix)'
$earthCargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
$env:PATH = "$env:VIRTUAL_ENV\Scripts;$earthPythonBase;$earthCargoBin;$env:PATH"
& $earthTauri dev
exit $LASTEXITCODE
