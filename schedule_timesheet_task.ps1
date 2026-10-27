# PowerShell script to register SenseLive Daily Timesheet Auto-Logger in Windows Task Scheduler
$TaskName = "SenseLive_Daily_Timesheet"
$PythonPath = (Get-Command python).Source
$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ScriptPath = Join-Path $CurrentDir "auto_timesheet_logger.py"
$WorkingDir = $CurrentDir

Write-Host "Registering task '$TaskName' to run daily at 6:00 PM (Mon-Sat)..." -ForegroundColor Cyan
Write-Host "Target script: $ScriptPath" -ForegroundColor Gray

# Action: Run Python script silently in the background
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkingDir

# Trigger: Monday through Saturday at 6:00 PM
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday,Saturday -At 6:00PM

# Settings: Allow on battery, start when available
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register or update
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Automatically audits and logs daily git work to SenseLive Odoo timesheets."

Write-Host "SUCCESS: Task '$TaskName' is now registered and will run automatically at 6:00 PM!" -ForegroundColor Green
