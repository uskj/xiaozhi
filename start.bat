@echo off
title 小智 - 一键启动
echo ========================================
echo        欢迎使用小智 AI 助手
echo ========================================
echo.
echo 正在检查依赖...
pip install edge_tts requests -q
echo.
echo 正在启动小智...
python main.py
pause
