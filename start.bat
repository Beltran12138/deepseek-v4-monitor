@echo off
chcp 65001 > nul
title DeepSeek V4 Monitor
cd /d %~dp0
echo.
echo  ============================================
echo    DeepSeek V4 发布信号监控器 启动中...
echo  ============================================
echo.
python monitor.py
pause
