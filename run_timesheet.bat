@echo off
cd /d "%~dp0"
echo ==============================================
echo Running SenseLive Daily Timesheet Auto-Logger
echo ==============================================
python auto_timesheet_logger.py
pause
