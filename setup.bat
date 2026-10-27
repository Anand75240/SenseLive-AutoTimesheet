@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo           SenseLive Daily Timesheet Auto-Logger - 1-Click Setup
echo ======================================================================
echo.

:: 1. Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.8+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Check if .env already exists
if exist "%~dp0.env" (
    echo [INFO] Found an existing .env configuration file.
    set /p RECONFIG="Do you want to re-configure your credentials? (y/N): "
    if /i not "!RECONFIG!"=="y" (
        goto :SCHEDULE
    )
)

echo.
echo Please enter your SenseLive Odoo credentials:
echo (Your password is saved locally on your laptop only, never shared).
echo.

:PROMPT_EMAIL
set /p USER_EMAIL="Enter your SenseLive Portal Email (e.g. yourname@senselive.io): "
if "%USER_EMAIL%"=="" (
    echo [!] Email cannot be empty.
    goto :PROMPT_EMAIL
)

:PROMPT_PASS
set /p USER_PASS="Enter your SenseLive Portal Password: "
if "%USER_PASS%"=="" (
    echo [!] Password cannot be empty.
    goto :PROMPT_PASS
)

echo.
echo Enter the path to your local workspace folder containing your projects:
set DEFAULT_WS=D:\SenseLive
if not exist "D:\SenseLive" (
    set DEFAULT_WS=%USERPROFILE%\SenseLive
)
set /p USER_WS="Workspace Path [Default: %DEFAULT_WS%]: "
if "%USER_WS%"=="" set USER_WS=%DEFAULT_WS%

:: Write .env
(
echo # SenseLive Odoo Credentials
echo ODOO_URL=https://portal.senselive.io
echo ODOO_DB=SenseLIve
echo ODOO_USER=%USER_EMAIL%
echo ODOO_PASS=%USER_PASS%
echo WORKSPACE_ROOT=%USER_WS%
) > "%~dp0.env"

echo.
echo [OK] Credentials saved successfully to local .env!

:SCHEDULE
echo.
echo Registering daily 6:00 PM background schedule in Windows Task Scheduler...
powershell -ExecutionPolicy Bypass -File "%~dp0schedule_timesheet_task.ps1"

echo.
echo ======================================================================
echo [SUCCESS] Setup Complete!
echo.
echo Your timesheets will now automatically:
echo   1. Scan your git commits across your projects every day at 6:00 PM.
echo   2. Match your projects and tasks in Odoo.
echo   3. Fill your 8-hour timesheet lines automatically.
echo   4. Show a desktop alert if you made zero commits or if anything is missing.
echo ======================================================================
echo.
pause
