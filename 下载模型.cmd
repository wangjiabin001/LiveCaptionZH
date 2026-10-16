@echo off
chcp 65001 >nul
cd /d %~dp0
set HF_ENDPOINT=https://hf-mirror.com
echo 开始下载模型（识别 3GB + 翻译 2.4GB，支持断点续传）...
echo 中途关掉也没事，下次运行会自动接着下。
echo.
.venv\Scripts\python.exe tools\fetch_models.py %*
pause
