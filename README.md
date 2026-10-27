# SenseLive Daily Timesheet Auto-Logger & Verifier

An automated worker that tracks your daily software engineering work across all projects in `d:\claude\SenseLive\`, audits your Odoo timesheets, and auto-submits accurate 8-hour timesheet entries directly to the SenseLive Odoo portal (`portal.senselive.io`).

---

## Features

1. **Multi-Project Git Detection**:
   * Scans all repositories under `d:\claude\SenseLive\` (e.g. `MoM Agent`, `SenseLead App`, `Website-2025`, etc.) for git commits and file modifications made today.
2. **Pre-Check & Field-by-Field Audit**:
   * Checks if timesheets are already filled for the day.
   * If filled, audits all fields:
     * **Description**: Verifies it is not blank, placeholder (`'/'`), or too short.
     * **Task**: Verifies an assigned task exists (e.g. *frontend development*, *backend development*, *testing*, *deployment*).
     * **Project**: Verifies it is mapped to the right enterprise project (not generic *Internal*).
     * **Hours**: Verifies the day totals a full 8.0 hours.
   * If any detail is missing, prompts you with an interactive Windows dialog for guidance.
3. **Interactive Guidance on Incomplete or Zero-Work Days**:
   * If you made zero git commits on a given day (e.g. meetings, offsite), it prompts:
     `"No code changes detected for today. Do you need to fill your timesheet anyway?"`
     * Clicking **Yes**: Prompts for task notes (pre-filled with general R&D) and project name, then logs 8.0h.
     * Clicking **No**: Safely skips today's entry without logging duplicates.
   * Has a 60-second safety timeout so it won't hang if you are away.
4. **Desktop Notifications**:
   * Shows a native Windows popup confirming logged hours, active projects, or warnings if a repository has no matching project on Odoo.
5. **Zero External Dependencies**:
   * Uses native Python standard library (`xmlrpc.client`, `subprocess`, `json`, `pathlib`). No pip installs required.

---

## Directory Structure

```
SenseLive-AutoTimesheet/
├── auto_timesheet_logger.py    # Main automation & audit engine
├── schedule_timesheet_task.ps1 # Registers Windows Scheduled Task (6:00 PM Mon-Sat)
├── run_timesheet.bat           # 1-click manual runner / test script
├── .env                        # Odoo credentials & workspace path
├── .env.example                # Sample environment template
├── logs/                       # Log files (auto_timesheet.log)
└── README.md                   # Documentation
```

---

## Setup & Scheduling

### Run Manually
Double click `run_timesheet.bat` or run:
```powershell
python auto_timesheet_logger.py
```

### Register Daily 6:00 PM Trigger in Windows Task Scheduler
Right-click `schedule_timesheet_task.ps1` and select **Run with PowerShell**, or execute:
```powershell
powershell -ExecutionPolicy Bypass -File .\schedule_timesheet_task.ps1
```

Task Name: `SenseLive_Daily_Timesheet`  
Trigger: **Monday through Saturday at 6:00 PM**
