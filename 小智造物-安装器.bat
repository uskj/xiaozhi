@echo off
chcp 65001 >nul
title 小智造物 安装中...
echo.
echo   正在启动安装程序...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
