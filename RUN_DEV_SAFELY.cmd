@echo off
setlocal
cd /d "%~dp0"
echo.
echo Yomu Note v0.8.5 DEVELOPMENT SOURCE RUN
 echo.
echo Uses separate test preferences; does not install or replace Yomu Note.
echo Only open COPIES of your notebooks for testing.
set YOMU_INTEGRATION_DEV=1
call run-windows.bat
