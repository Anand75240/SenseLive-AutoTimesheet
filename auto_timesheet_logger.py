"""SenseLive Daily Timesheet Auto-Logger & Verifier.
Automatically scans projects in the workspace for daily git activity,
audits Odoo timesheets, and logs exactly ONE single clean 8.0-hour timesheet entry
with a unified single description per day.
"""
import os
import sys
import json
import logging
import datetime
import subprocess
import xmlrpc.client
from pathlib import Path

# Self-contained directories
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Built-in lightweight .env loader (zero external pip dependencies)
def load_env_file(env_path: Path):
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k not in os.environ:
                    os.environ[k] = v

load_env_file(BASE_DIR / ".env")

# Configure logging
logging.basicConfig(
    filename=str(LOG_DIR / "auto_timesheet.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)

class CleanFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        return msg.encode("ascii", "replace").decode("ascii")

console.setFormatter(CleanFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(console)

# ---------------- CONFIGURATION ----------------
ODOO_URL = os.getenv("ODOO_URL", "https://portal.senselive.io")
ODOO_DB = os.getenv("ODOO_DB", "SenseLIve")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_PASS = os.getenv("ODOO_PASS", "")

# Root workspace containing user projects
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", r"d:\claude\SenseLive"))

# Explicit mapping from folder names or aliases to Odoo project search queries
PROJECT_ALIASES = {
    "mom agent": "Senselive_minutes",
    "senselive minutes": "Senselive_minutes",
    "senselive-minutes": "Senselive_minutes",
    "senselead app": "SENSE-LEAD-APP",
    "sense-lead-app": "SENSE-LEAD-APP",
    "senselead": "SENSE-LEAD-APP",
    "ai symmary generator": "AI_EMS",
    "senselive website": "Platform_Development",
    "website-2025": "WEBSITE_development",
    "k40": "K40_Integration",
}


def notify_user(title: str, message: str, is_warning: bool = False):
    """Displays a native Windows popup notification."""
    icon_code = 48 if is_warning else 64  # 48 = Warning icon, 64 = Information icon
    clean_msg = message.replace('"', '`"').replace("'", "`'")
    clean_title = title.replace('"', '`"').replace("'", "`'")
    ps_cmd = (
        f"$wshell = New-Object -ComObject Wscript.Shell; "
        f"$wshell.Popup('{clean_msg}', 8, '{clean_title}', {icon_code})"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False)
    except Exception as e:
        logging.warning(f"Could not display Windows notification: {e}")


def prompt_user_no_work(target_date: datetime.date):
    """
    When no git activity is detected, asks the user via a native Windows popup
    whether they want to fill their timesheet anyway.
    Times out safely after 60 seconds if user is away.
    """
    today_str = target_date.strftime("%d %b %Y")
    ps_script = f"""
    $wshell = New-Object -ComObject Wscript.Shell
    # 36 = Yes/No buttons (4) + Question icon (32)
    # 60 second timeout: returns 6 (Yes), 7 (No), -1 (Timeout)
    $choice = $wshell.Popup("No code commits or file changes were detected for today ({today_str}).`n`nDo you need to fill your timesheet for today anyway?", 60, "SenseLive Timesheet Check", 36)
    
    if ($choice -ne 6) {{
        $reason = if ($choice -eq -1) {{ "timeout" }} else {{ "no" }}
        Write-Output (ConvertTo-Json @{{ fill = $false; reason = $reason }})
        exit
    }}
    
    Add-Type -AssemblyName Microsoft.VisualBasic
    $desc = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Enter task description for today's timesheet (single concise sentence):",
        "SenseLive Timesheet - Task Description",
        "Technical coordination, client calls, documentation, and sprint review"
    )
    
    if (-not $desc) {{
        Write-Output (ConvertTo-Json @{{ fill = $false; reason = "cancelled" }})
        exit
    }}
    
    $proj = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Enter Odoo Project name or keyword (e.g. Senselive_minutes, SENSE-LEAD-APP, Platform_Development):",
        "SenseLive Timesheet - Project",
        "Senselive_minutes"
    )
    
    if (-not $proj) {{
        $proj = "Senselive_minutes"
    }}
    
    Write-Output (ConvertTo-Json @{{ fill = $true; description = $desc; project = $proj }})
    """
    try:
        res = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_script], text=True).strip()
        data = json.loads(res)
        return data.get("fill", False), data.get("description", ""), data.get("project", "Senselive_minutes")
    except Exception as e:
        logging.warning(f"Interactive prompt error: {e}")
        return False, "", ""


def prompt_user_guide_audit(target_date: datetime.date, issues: list):
    """
    Shows an interactive Windows prompt detailing exactly what is missing or incomplete
    in today's timesheet and asks the user for guidance.
    """
    today_str = target_date.strftime("%d %b %Y")
    issues_text = "`n".join(f"• {iss}" for iss in issues)
    
    ps_script = f"""
    $wshell = New-Object -ComObject Wscript.Shell
    # 36 = Yes/No buttons (4) + Question icon (32). Timeout = 60s
    $msg = "Timesheet Audit Alert for {today_str}:`n`n{issues_text}`n`nWould you like me to fix and log a single clean 8.0h timesheet entry automatically?"
    $choice = $wshell.Popup($msg, 60, "SenseLive Timesheet Audit - Guidance Needed", 36)
    
    if ($choice -ne 6) {{
        $reason = if ($choice -eq -1) {{ "timeout" }} else {{ "user_declined" }}
        Write-Output (ConvertTo-Json @{{ fix = $false; reason = $reason }})
        exit
    }}
    
    Write-Output (ConvertTo-Json @{{ fix = $true }})
    """
    try:
        res = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_script], text=True).strip()
        data = json.loads(res)
        return data.get("fix", False)
    except Exception as e:
        logging.warning(f"Interactive guide prompt error: {e}")
        return False


def get_git_repos(root_dir: Path):
    """Finds all git repositories in the root directory."""
    repos = []
    if not root_dir.exists():
        return repos
    for item in root_dir.iterdir():
        if item.is_dir():
            if (item / ".git").exists():
                repos.append(item)
            else:
                for sub in item.iterdir():
                    if sub.is_dir() and (sub / ".git").exists():
                        repos.append(sub)
    return repos


def synthesize_single_description(commits: list, repo_name: str) -> str:
    """Creates a single clean, natural sentence from commits instead of multiple chained lines."""
    if not commits:
        return f"Development, optimization, and testing for {repo_name}."

    def commit_priority(c: str) -> int:
        cl = c.lower()
        if "feat" in cl: return 100
        if "fix" in cl: return 80
        if "refactor" in cl or "perf" in cl: return 60
        if "test" in cl: return 40
        if "doc" in cl: return 30
        return 10

    sorted_commits = sorted(commits, key=commit_priority, reverse=True)

    cleaned = []
    for c in sorted_commits:
        msg = c.strip()
        if ":" in msg:
            prefix, rest = msg.split(":", 1)
            if any(t in prefix.lower() for t in ["feat", "fix", "chore", "refactor", "docs", "style", "test", "build"]):
                msg = rest.strip()
        if msg:
            cleaned.append(msg[0].upper() + msg[1:])

    if not cleaned:
        return f"Ongoing development and system improvements for {repo_name}."

    if len(cleaned) == 1:
        desc = cleaned[0]
    else:
        desc = f"{cleaned[0]}, and {cleaned[1].lower()}."

    desc = desc.strip().rstrip(".").strip() + "."
    if len(desc) > 200:
        desc = desc[:197] + "..."
    return desc


def get_daily_activity_for_repo(repo_path: Path, target_date: datetime.date):
    """Extracts commit messages and active file changes for today."""
    since_str = f"{target_date.isoformat()} 00:00:00"
    until_str = f"{target_date.isoformat()} 23:59:59"
    
    try:
        cmd = [
            "git", "-C", str(repo_path), "log",
            f"--since={since_str}", f"--until={until_str}",
            "--pretty=format:%s"
        ]
        res = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        commits = [line.strip() for line in res.splitlines() if line.strip()]
    except Exception:
        commits = []

    try:
        st_cmd = ["git", "-C", str(repo_path), "status", "--porcelain"]
        st_res = subprocess.check_output(st_cmd, text=True, stderr=subprocess.DEVNULL).strip()
        uncommitted = [l for l in st_res.splitlines() if l.strip()]
    except Exception:
        uncommitted = []

    if not commits and not uncommitted:
        return None

    desc = synthesize_single_description(commits, repo_path.name)

    return {
        "repo_name": repo_path.name,
        "repo_path": repo_path,
        "commits": commits,
        "uncommitted_count": len(uncommitted),
        "description": desc,
    }


def select_primary_project(active_projects: list):
    """
    Selects the single most significant project worked on today
    to ensure only 1 clean timesheet line of 8.0 hours is logged.
    """
    if not active_projects:
        return None
    ranked = sorted(
        active_projects,
        key=lambda p: (len(p.get("commits", [])), p.get("uncommitted_count", 0)),
        reverse=True
    )
    return ranked[0]


def connect_odoo():
    """Authenticates to Odoo via XML-RPC."""
    if not ODOO_USER or not ODOO_PASS:
        raise ValueError("Missing Odoo credentials! Please run setup.bat or configure your .env file.")
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    if not uid:
        raise ConnectionError(f"Failed to authenticate with Odoo user '{ODOO_USER}'. Check credentials in .env.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def match_odoo_project(models, uid, repo_name: str, all_projects: list):
    """Matches repository name to an Odoo project."""
    repo_lower = repo_name.lower()
    
    search_keyword = None
    for alias, keyword in PROJECT_ALIASES.items():
        if alias in repo_lower:
            search_keyword = keyword
            break

    if search_keyword:
        for p in all_projects:
            if search_keyword.lower() in p["name"].lower():
                return p

    tokens = [t for t in repo_lower.replace("-", " ").replace("_", " ").split() if len(t) > 2]
    for p in all_projects:
        p_name_lower = p["name"].lower()
        if any(token in p_name_lower for token in tokens):
            return p

    return None


def select_best_task(models, uid, project_id: int, description: str):
    """Finds best matching task under project or defaults to first available."""
    tasks = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'project.task', 'search_read',
        [[['project_id', '=', project_id]]],
        {'fields': ['id', 'name'], 'limit': 10}
    )
    if not tasks:
        return False, None

    desc_lower = description.lower()
    for t in tasks:
        t_name = t['name'].lower()
        if "frontend" in desc_lower and "frontend" in t_name:
            return t['id'], t['name']
        if ("backend" in desc_lower or "api" in desc_lower or "db" in desc_lower or "docker" in desc_lower) and "backend" in t_name:
            return t['id'], t['name']
        if ("test" in desc_lower or "bug" in desc_lower or "fix" in desc_lower) and "testing" in t_name:
            return t['id'], t['name']
        if ("deploy" in desc_lower or "container" in desc_lower or "server" in desc_lower) and "deployment" in t_name:
            return t['id'], t['name']

    return tasks[0]['id'], tasks[0]['name']


def audit_timesheet_entries(entries: list):
    """Performs deep audit of timesheet entries for missing or incomplete data."""
    issues = []
    total_hours = sum(e.get('unit_amount', 0.0) for e in entries)
    
    if len(entries) > 1:
        issues.append(f"Multiple entries found for today ({len(entries)} entries). Standard is 1 single entry of 8.0h.")

    missing_desc = [
        e for e in entries
        if not e.get('name') or e.get('name', '').strip() in ['/', '.', '-', ''] or len(e.get('name', '').strip()) < 5
    ]
    missing_task = [e for e in entries if not e.get('task_id')]
    missing_project = [e for e in entries if not e.get('project_id') or e['project_id'][0] == 1]
    zero_hours = [e for e in entries if e.get('unit_amount', 0.0) <= 0.0]

    if missing_desc:
        issues.append(f"{len(missing_desc)} entry/entries have missing/blank descriptions ('/')")
    if missing_task:
        issues.append(f"{len(missing_task)} entry/entries have no task assigned")
    if missing_project:
        issues.append(f"{len(missing_project)} entry/entries have unassigned or generic projects")
    if zero_hours:
        issues.append(f"{len(zero_hours)} entry/entries have 0.0 logged hours")
    if total_hours < 8.0:
        issues.append(f"Total logged hours: {total_hours}h (Expected full day: 8.0h)")

    return issues, total_hours


def log_single_timesheet_to_odoo(models, uid, target_date: datetime.date, primary_project: dict, all_projects: list, clean_dummy_ids: list = None):
    """Submits exactly ONE clean 8.0h timesheet record to Odoo with a single concise description."""
    if clean_dummy_ids:
        try:
            models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.analytic.line', 'unlink', [clean_dummy_ids])
            logging.info(f"Cleaned up {len(clean_dummy_ids)} dummy/duplicate entries: {clean_dummy_ids}")
        except Exception as e:
            logging.warning(f"Could not unlink dummy entries: {e}")

    repo_name = primary_project["repo_name"]
    desc = primary_project["description"]
    odoo_proj = match_odoo_project(models, uid, repo_name, all_projects)

    if not odoo_proj:
        msg = f"Project '{repo_name}' not found on Odoo!"
        logging.warning(msg)
        notify_user("SenseLive Timesheet Auto-Logger", f"Warning: '{repo_name}' has no matching project on Odoo.", is_warning=True)
        return False

    proj_id = odoo_proj["id"]
    proj_name = odoo_proj["name"]
    task_id, task_name = select_best_task(models, uid, proj_id, desc)

    entry = {
        "name": desc,
        "project_id": proj_id,
        "unit_amount": 8.0,
        "date": target_date.isoformat(),
    }
    if task_id:
        entry["task_id"] = task_id

    entry_id = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'account.analytic.line', 'create', [entry]
    )
    task_info = f" [Task: {task_name}]" if task_name else ""
    logging.info(f"Logged 8.0h on '{proj_name}'{task_info} -> ID: {entry_id}")

    notify_user(
        "SenseLive Timesheet Auto-Logger",
        f"Timesheet Logged for {target_date}:\n* {proj_name} (8.0h){task_info}\n  \"{desc}\"",
        is_warning=False
    )
    return True


def run_daily_timesheet(target_date: datetime.date = None):
    """Main automated timesheet runner."""
    if target_date is None:
        target_date = datetime.date.today()

    logging.info(f"=== Running SenseLive Daily Timesheet Check for {target_date} ===")

    # 1. Connect to Odoo
    try:
        uid, models = connect_odoo()
        logging.info(f"Authenticated to Odoo (UID: {uid})")
    except Exception as e:
        err = f"Odoo Connection Failed: {e}"
        logging.error(err)
        notify_user("SenseLive Timesheet Error", f"Odoo Connection Failed: {e}", is_warning=True)
        return

    all_projects = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'project.project', 'search_read',
        [[]], {'fields': ['id', 'name']}
    )

    # 2. Check if timesheets are ALREADY filled for today
    existing_entries = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'account.analytic.line', 'search_read',
        [[['user_id', '=', uid], ['date', '=', target_date.isoformat()]]],
        {'fields': ['id', 'name', 'project_id', 'task_id', 'unit_amount']}
    )

    # Case A: Timesheets already exist -> Audit
    if existing_entries:
        issues, total_hours = audit_timesheet_entries(existing_entries)
        
        if not issues and len(existing_entries) == 1:
            msg = (
                f"Timesheet for {target_date} is already 100% complete!\n"
                f"Logged: {total_hours}h on {existing_entries[0]['project_id'][1]} with description intact."
            )
            logging.info(msg)
            notify_user("SenseLive Timesheet Verified", msg, is_warning=False)
            return

        # Issues found in existing timesheet -> Notify user to guide
        logging.warning(f"Incomplete timesheet detected on {target_date}: {issues}")
        user_wants_fix = prompt_user_guide_audit(target_date, issues)
        
        if not user_wants_fix:
            logging.info("User chose not to modify incomplete timesheet. Leaving as-is.")
            notify_user("SenseLive Timesheet Guide", f"Incomplete timesheet left as-is per your guidance.\nPlease review on portal.senselive.io.", is_warning=True)
            return

        # User wants to fix! Gather today's work
        repos = get_git_repos(WORKSPACE_ROOT)
        active_projects = []
        for r in repos:
            act = get_daily_activity_for_repo(r, target_date)
            if act:
                active_projects.append(act)

        primary = select_primary_project(active_projects)
        if not primary:
            should_fill, custom_desc, custom_proj = prompt_user_no_work(target_date)
            if not should_fill:
                return
            primary = {
                "repo_name": custom_proj,
                "repo_path": None,
                "commits": [],
                "uncommitted_count": 0,
                "description": custom_desc
            }

        clean_ids = [e['id'] for e in existing_entries]
        log_single_timesheet_to_odoo(models, uid, target_date, primary, all_projects, clean_dummy_ids=clean_ids)
        return

    # Case B: No timesheets exist at all -> Fill from today's work
    logging.info(f"No timesheets found for {target_date}. Gathering git activity...")
    repos = get_git_repos(WORKSPACE_ROOT)
    active_projects = []
    for r in repos:
        act = get_daily_activity_for_repo(r, target_date)
        if act:
            active_projects.append(act)

    primary = select_primary_project(active_projects)
    if not primary:
        logging.info(f"No git commits or active file changes detected for {target_date}.")
        should_fill, custom_desc, custom_proj = prompt_user_no_work(target_date)
        if not should_fill:
            logging.info("User chose not to log timesheet (or prompt timed out). Exiting.")
            notify_user("SenseLive Timesheet", f"Timesheet skipped for {target_date} (No activity recorded).")
            return

        primary = {
            "repo_name": custom_proj,
            "repo_path": None,
            "commits": [],
            "uncommitted_count": 0,
            "description": custom_desc
        }

    log_single_timesheet_to_odoo(models, uid, target_date, primary, all_projects)


if __name__ == "__main__":
    run_daily_timesheet()
