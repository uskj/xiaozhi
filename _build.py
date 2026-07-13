import base64, os

base = r"C:\Users\zhaox\Desktop\xiaozhi"

# Read source files
files = {}
for f in ["main.py", "index.html", "config.json"]:
    with open(os.path.join(base, f), "rb") as fh:
        files[f] = base64.b64encode(fh.read()).decode()

# Also encode start.bat
start_lines = [
    "@echo off",
    "chcp 65001 >nul",
    "title \u5c0f\u667a\u7269\u7269",
    "python --version >nul 2>&1",
    'if %errorlevel% neq 0 (',
    '    echo.',
    '    echo  \u672a\u68c0\u6d4b\u5230 Python\uff0c\u8bf7\u5148\u8fd0\u884c\u5b89\u88c5\u7a0b\u5e8f\uff01',
    '    pause',
    '    exit /b 1',
    ')',
    'python -c "import serial" >nul 2>&1',
    'if %errorlevel% neq 0 (',
    '    echo.',
    '    echo  \u672a\u68c0\u6d4b\u5230 pyserial\uff0c\u8bf7\u5148\u8fd0\u884c\u5b89\u88c5\u7a0b\u5e8f\uff01',
    '    pause',
    '    exit /b 1',
    ')',
    'cd /d "%~dp0"',
    'python main.py',
    'pause',
]
files["start.bat"] = base64.b64encode(("\r\n".join(start_lines)).encode("utf-8")).decode()

# Build PS1 content
ps_lines = []
a = ps_lines.append

a('[Console]::OutputEncoding = [Text.Encoding]::UTF8')
a('Write-Host ""')
a('Write-Host "  ============================================" -ForegroundColor Cyan')
a('Write-Host "     \u5c0f\u667a\u7269\u7269 - Arduino AI \u5b66\u4e60\u5e73\u53f0" -ForegroundColor Cyan')
a('Write-Host "     \u4e00\u952e\u5b89\u88c5\u7a0b\u5e8f" -ForegroundColor Cyan')
a('Write-Host "  ============================================" -ForegroundColor Cyan')
a('Write-Host ""')
a('')
a('$Target = Join-Path $env:LOCALAPPDATA "\u5c0f\u667a\u7269\u7269"')
a('Write-Host "  \u5b89\u88c5\u76ee\u5f55: $Target"')
a('')
a('Write-Host ""')
a('Write-Host "  [1/5] \u521b\u5efa\u7a0b\u5e8f\u76ee\u5f55..." -ForegroundColor Yellow')
a('New-Item -ItemType Directory -Path $Target -Force | Out-Null')
a('New-Item -ItemType Directory -Path (Join-Path $Target "data") -Force | Out-Null')
a('Write-Host "    OK" -ForegroundColor Green')
a('')

a('Write-Host "  [2/5] \u91ca\u653e\u7a0b\u5e8f\u6587\u4ef6..." -ForegroundColor Yellow')

for fname, b64 in files.items():
    a('Write-Host "    ' + fname + '..." -NoNewline')
    chunks = [b64[i:i+4096] for i in range(0, len(b64), 4096)]
    a('$b64 = ""')
    for chunk in chunks:
        a('$b64 += "' + chunk + '"')
    a('$bytes = [Convert]::FromBase64String($b64)')
    a('[IO.File]::WriteAllBytes((Join-Path $Target "' + fname + '"), $bytes)')
    a('Write-Host " OK" -ForegroundColor Green')

a('')

# Python check - avoid nested quotes issue by using single-line approach
a('Write-Host "  [3/5] \u68c0\u6d4b Python \u73af\u5883..." -ForegroundColor Yellow')
a('$pyOk = $false')
a('try { $v = python --version 2>&1; if ($LASTEXITCODE -eq 0) { $pyOk = $true } } catch {}')
a('if (-not $pyOk) {')
a('    Write-Host "    Python \u672a\u5b89\u88c5\uff0c\u6b63\u5728\u81ea\u52a8\u5b89\u88c5..." -ForegroundColor Red')
a('    Write-Host "    [\u5982\u5f39\u51fa\u5b89\u88c5\u7a97\u53e3\uff0c\u8bf7\u6309\u9ed8\u8ba4\u9009\u9879\u4e0b\u4e00\u6b65]"')
a('    try { winget install Python.Python.3.10 --silent --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null } catch {}')
a('    if (-not $pyOk) {')
a('        Write-Host "    \u8bf7\u624b\u52a8\u5b89\u88c5 Python 3.10+" -ForegroundColor Red')
a('        Write-Host "    https://www.python.org/downloads/" -ForegroundColor Yellow')
a('    }')
a('} else {')
a('    Write-Host "    $v" -ForegroundColor Green')
a('}')
a('')

# pyserial
a('Write-Host "  [4/5] \u5b89\u88c5\u4e32\u53e3\u901a\u4fe1\u5e93..." -ForegroundColor Yellow')
a('$serOk = $false')
a('try { python -c "import serial" 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $serOk = $true } } catch {}')
a('if (-not $serOk) { pip install pyserial -q 2>&1 | Out-Null }')
a('Write-Host "    pyserial \u5c31\u7eea" -ForegroundColor Green')
a('')

# arduino-cli
a('Write-Host "  [5/5] \u68c0\u6d4b Arduino \u7f16\u8bd1\u73af\u5883..." -ForegroundColor Yellow')
a('$hasCli = Get-Command arduino-cli -ErrorAction SilentlyContinue')
a('if (-not $hasCli) {')
a('    Write-Host "    \u6b63\u5728\u4e0b\u8f7d Arduino \u7f16\u8bd1\u5668..."')
a('    $toolsDir = Join-Path $Target "tools"')
a('    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null')
a('    $zipFile = Join-Path $env:TEMP "arduino-cli.zip"')
a('    Invoke-WebRequest -Uri "https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip" -OutFile $zipFile')
a('    Expand-Archive -Path $zipFile -DestinationPath $toolsDir -Force')
a('    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue')
a('    $env:PATH = "$toolsDir;$env:PATH"')
a('}')
a('$hasCore = arduino-cli core list 2>&1 | Select-String "arduino:avr"')
a('if (-not $hasCore) {')
a('    Write-Host "    \u6b63\u5728\u5b89\u88c5 Arduino AVR \u6838\u5fc3..."')
a('    arduino-cli core update-index 2>&1 | Out-Null')
a('    arduino-cli core install arduino:avr 2>&1 | Out-Null')
a('}')
a('Write-Host "    Arduino \u73af\u5883\u5c31\u7eea" -ForegroundColor Green')
a('')

# Shortcut
a('Write-Host ""')
a('$lnk = Join-Path $env:USERPROFILE "Desktop\\\u5c0f\u667a\u7269\u7269.lnk"')
a('$sh = New-Object -COM WScript.Shell')
a('$sc = $sh.CreateShortcut($lnk)')
a('$sc.TargetPath = Join-Path $Target "start.bat"')
a('$sc.WorkingDirectory = $Target')
a('$sc.Description = "\u5c0f\u667a\u7269\u7269 - Arduino AI \u5b66\u4e60\u5e73\u53f0"')
a('$sc.Save()')
a('Write-Host "  \u684c\u9762\u5feb\u6377\u65b9\u5f0f\u5df2\u521b\u5efa" -ForegroundColor Green')
a('')

# Done
a('Write-Host ""')
a('Write-Host "  ============================================" -ForegroundColor Cyan')
a('Write-Host "   \u5b89\u88c5\u5b8c\u6210\uff01" -ForegroundColor Green')
a('Write-Host "  ============================================" -ForegroundColor Cyan')
a('Write-Host ""')
a('Write-Host "  \u4f7f\u7528\u65b9\u6cd5\uff1a"')
a('Write-Host "    1. \u7528USB\u7ebf\u8fde\u63a5Arduino\u5230\u7535\u8111"')
a('Write-Host "    2. \u53cc\u51fb\u684c\u9762 \u5c0f\u667a\u7269\u7269 \u5feb\u6377\u65b9\u5f0f"')
a('Write-Host "    3. \u5f00\u59cb\u548c\u5c0f\u667a\u804a\u5929\u5427\uff01"')
a('Write-Host ""')
a('')
a('$launch = Read-Host "  \u73b0\u5728\u5c31\u542f\u52a8\u5417\uff1f(Y/N)"')
a('if ($launch -eq "Y" -or $launch -eq "y") {')
a('    Start-Process (Join-Path $Target "start.bat")')
a('}')
a('')
a('Read-Host "  \u6309\u56de\u8f66\u9000\u51fa"')

ps_content = "\r\n".join(ps_lines)

# Base64 encode the entire PS1 content
ps_b64 = base64.b64encode(ps_content.encode("utf-8")).decode()

# Batch header: decode base64 to temp ps1, run it, clean up
# Split base64 into 80-char lines for batch compatibility
b64_lines = [ps_b64[i:i+80] for i in range(0, len(ps_b64), 80)]
b64_joined = "\r\n".join(b64_lines)

batch_content = f"""@echo off
title \u5c0f\u667a\u7269\u7269 \u5b89\u88c5\u4e2d...
echo.
echo   ============================================
echo      \u5c0f\u667a\u7269\u7269 - Arduino AI \u5b66\u4e60\u5e73\u53f0
echo      \u4e00\u952e\u5b89\u88c5\u7a0b\u5e8f
echo   ============================================
echo.
echo   \u6b63\u5728\u51c6\u5b89\u88c5\u7a0b\u5e8f...
echo.

REM Decode embedded PS1 installer
set "TEMP_PS1=%TEMP%\\xiaozhi_install.ps1"
(
for /f "delims=" %%a in ('findstr /b /r "[A-Za-z0-9+/=]" "%~f0"') do (
    echo %%a
)
) > "%TEMP_PS1%"

REM Run PS1 installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP_PS1%"
set "ERR=%ERRORLEVEL%"

REM Cleanup
del "%TEMP_PS1%" 2>nul

if %ERR% neq 0 (
    echo.
    echo   \u5b89\u88c5\u51fa\u9519\uff0c\u8bf7\u91cd\u8bd5
)
pause
exit /b %ERR%

---BEGIN XIAOZHI_PS1_BASE64---
{b64_joined}
---END XIAOZHI_PS1_BASE64---
"""

out = os.path.join(base, "\u5c0f\u667a\u7269\u7269-\u5b89\u88c5\u5668.bat")
with open(out, "w", encoding="utf-8") as f:
    f.write(batch_content)

size = os.path.getsize(out)
print(f"OK: {size:,} bytes")
