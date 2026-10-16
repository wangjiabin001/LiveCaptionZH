@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================================
echo   LiveCaptionZH 实时中文字幕 - 安装
echo ============================================================
if not exist .venv (
  echo [1/3] 创建 Python 虚拟环境 ...
  python -m venv .venv
  if errorlevel 1 (
    echo [错误] 没找到 python，请先安装 Python 3.10+ 并勾选 Add to PATH
    pause & exit /b 1
  )
) else (
  echo [1/3] 虚拟环境已存在，跳过
)
echo [2/3] 安装依赖（约 3GB，首次较慢）...
.venv\Scripts\python.exe -m pip install --upgrade pip -q
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo [错误] 依赖安装失败 & pause & exit /b 1 )
echo [3/3] 完成
echo.
echo   下一步：双击 start.cmd 开始使用
echo   首次运行会自动下载识别模型和翻译模型（约 2.5GB，走 hf-mirror 镜像）
echo.
pause