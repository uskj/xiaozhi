<# :
@echo off
powershell -ExecutionPolicy Bypass -Command "iex((Get-Content -LiteralPath '%~f0' | Select-Object -Skip 7) -join [Environment]::NewLine)"
pause
exit /b 0
: #>
Write-Host "Hello from PS1"
$x = 1 + 2
Write-Host "Result: $x"
