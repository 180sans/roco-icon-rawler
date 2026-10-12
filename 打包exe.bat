@echo off
chcp 65001 >nul
cd /d "%~dp0"
python build_exe.py
if errorlevel 1 (
    echo 打包失败，请查看上方错误。
) else (
    echo 打包成功，程序和发布压缩包位于 dist 文件夹。
)
pause
