@echo off
setlocal

cd /d "%~dp0"
set PORT=8787

echo 正在启动小红书智能发布工作台...
echo 地址: http://127.0.0.1:%PORT%

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  start "XHS Workspace Backend" /min py -3 backend\server.py --port %PORT%
) else (
  start "XHS Workspace Backend" /min python backend\server.py --port %PORT%
)

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%PORT%"

echo.
echo 已打开浏览器。如果页面没有打开，请手动访问:
echo http://127.0.0.1:%PORT%
echo.
echo 关闭这个窗口不会停止后台服务；需要停止时请关闭名为 XHS Workspace Backend 的命令行窗口。
pause
