@echo off
title LiveCaptionZH - 实时中文字幕
cd /d %~dp0
set HF_ENDPOINT=https://hf-mirror.com
set HF_HUB_DISABLE_XET=1
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
if not exist .venv\Scripts\python.exe (
  echo [错误] 还没安装，请先双击 install.cmd
  pause
  exit /b 1
)
echo ============================================================
echo   实时中文字幕 LiveCaptionZH
echo   这个窗口不要关，关掉就退出字幕。
echo ============================================================
echo.
cd src
..\.venv\Scripts\python.exe main.py %*
cd ..
echo.
echo 字幕已停止。
pause