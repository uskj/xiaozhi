<# :
@echo off
powershell -ExecutionPolicy Bypass -Command "iex((Get-Content -LiteralPath '%~f0' | Select-Object -Skip 7) -join [Environment]::NewLine)"
pause
exit /b 0
: #>
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Write-Host "step1"
$Target = Join-Path $env:LOCALAPPDATA "物思"
Write-Host "step2: $Target"
$pyDir = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310"
$pyScripts = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\Scripts"
$env:PATH = "$pyDir;$pyScripts;$env:PATH"
Write-Host "step3: PATH set"
