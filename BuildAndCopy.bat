:: 一键打包exe并拷贝到U盘，此脚本仅用于个人本地开发，与项目功能无关

@echo off
chcp 65001
echo 开始生成可执行文件...

:: 1. 切换到指定目录并执行pyinstaller
cd /d C:\github\sd_express_tester
pyinstaller main.spec --clean

:: 检查pyinstaller是否执行成功
if %ERRORLEVEL% neq 0 (
    echo PyInstaller执行失败！
    pause
    exit /b 1
)

echo PyInstaller执行完成

:: 2. 复制文件到目标目录
echo 正在复制文件到 E:\sd_express_tester...
if not exist "E:\sd_express_tester" mkdir "E:\sd_express_tester"
xcopy /Y /E "C:\github\sd_express_tester\dist\*.*" "E:\sd_express_tester\"

:: 检查复制是否成功
if %ERRORLEVEL% neq 0 (
    echo 文件复制失败！
    pause
    exit /b 1
)

echo 所有操作已完成！
pause