import os
import sys
import time
import subprocess
import shutil
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from app.core.logger import logger
from app.tools.permissions import PermissionLevel

# Map of standard approved applications
SAFE_APPS = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "terminal": "wt.exe",
    "edge": "msedge.exe",
    "browser": "msedge.exe",
}


def tool_get_system_info(**kwargs) -> Dict[str, Any]:
    import platform
    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "free_ram_gb": round(psutil.virtual_memory().available / (1024**3), 2),
    }


def tool_get_time(**kwargs) -> Dict[str, Any]:
    now = datetime.now()
    return {
        "current_time": now.strftime("%I:%M %p"),
        "current_date": now.strftime("%A, %B %d, %Y"),
        "iso": now.isoformat(),
    }


def tool_get_cpu_usage(**kwargs) -> Dict[str, Any]:
    cpu_pct = psutil.cpu_percent(interval=0.2)
    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
    return {
        "cpu_usage_percent": cpu_pct,
        "cores_usage": per_cpu,
        "logical_cores": len(per_cpu),
    }


def tool_get_memory_usage(**kwargs) -> Dict[str, Any]:
    mem = psutil.virtual_memory()
    return {
        "usage_percent": mem.percent,
        "used_gb": round(mem.used / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "total_gb": round(mem.total / (1024**3), 2),
    }


def tool_get_disk_usage(path: str = "C:\\", **kwargs) -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 1),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_running_processes(limit: int = 15, **kwargs) -> Dict[str, Any]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "memory_percent": round(p.info["memory_percent"] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs = sorted(procs, key=lambda x: x["memory_percent"], reverse=True)[:limit]
    return {"top_processes": procs}


def tool_open_application(app_name: str, **kwargs) -> Dict[str, Any]:
    key = app_name.strip().lower()
    target_exe = SAFE_APPS.get(key, None)

    try:
        if target_exe:
            subprocess.Popen([target_exe], shell=False)
            return {"status": "success", "message": f"Successfully launched {app_name}."}
        else:
            # Fallback: check if executable exists or use os.startfile for Windows registered protocol
            # Disallow execution of scripts (.bat, .vbs, .ps1) here for safety
            if any(key.endswith(ext) for ext in [".bat", ".ps1", ".vbs", ".cmd", ".scr"]):
                return {"status": "blocked", "message": "Direct script launching via open_application is restricted."}
            os.startfile(app_name)
            return {"status": "success", "message": f"Opened {app_name}."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to launch {app_name}: {str(e)}"}


def tool_open_folder(folder_path: str, **kwargs) -> Dict[str, Any]:
    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        return {"status": "error", "message": f"Folder does not exist: {folder_path}"}
    try:
        os.startfile(str(p.resolve()))
        return {"status": "success", "message": f"Opened folder: {folder_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_read_file(file_path: str, max_lines: int = 50, **kwargs) -> Dict[str, Any]:
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {"status": "error", "message": f"File does not exist: {file_path}"}
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return {"status": "success", "lines_read": len(lines), "content": "".join(lines)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_search_local_files(directory: str, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return {"status": "error", "message": f"Directory does not exist: {directory}"}
    matches = []
    try:
        for root, dirs, files in os.walk(p):
            for file in files:
                if query.lower() in file.lower():
                    matches.append(os.path.join(root, file))
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        return {"status": "success", "matches": matches}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Medium/High Impact tools requiring confirmation:
def tool_close_program(process_name_or_pid: str, **kwargs) -> Dict[str, Any]:
    closed = 0
    try:
        if str(process_name_or_pid).isdigit():
            p = psutil.Process(int(process_name_or_pid))
            p.terminate()
            return {"status": "success", "message": f"Terminated PID {process_name_or_pid} ({p.name()})."}

        for p in psutil.process_iter(["name"]):
            if p.info["name"] and p.info["name"].lower() == process_name_or_pid.lower():
                p.terminate()
                closed += 1
        return {"status": "success", "message": f"Terminated {closed} instances of {process_name_or_pid}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_delete_file(file_path: str, **kwargs) -> Dict[str, Any]:
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {"status": "error", "message": f"File not found: {file_path}"}
    try:
        p.unlink()
        return {"status": "success", "message": f"File deleted: {file_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_system_shutdown_pc(delay_seconds: int = 30, **kwargs) -> Dict[str, Any]:
    try:
        subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], check=True)
        return {"status": "success", "message": f"System shutdown initiated in {delay_seconds} seconds."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_system_restart_pc(delay_seconds: int = 30, **kwargs) -> Dict[str, Any]:
    try:
        subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], check=True)
        return {"status": "success", "message": f"System restart scheduled in {delay_seconds} seconds."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


ALL_TOOLS = {
    "get_system_info": {
        "name": "get_system_info",
        "description": "Get operating system, CPU cores, and RAM specifications.",
        "parameters": {},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_system_info,
    },
    "get_time": {
        "name": "get_time",
        "description": "Get the current time, day of the week, and date.",
        "parameters": {},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_time,
    },
    "get_cpu_usage": {
        "name": "get_cpu_usage",
        "description": "Get current CPU utilization percentage and per-core usage.",
        "parameters": {},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_cpu_usage,
    },
    "get_memory_usage": {
        "name": "get_memory_usage",
        "description": "Get current system RAM usage and available memory.",
        "parameters": {},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_memory_usage,
    },
    "get_disk_usage": {
        "name": "get_disk_usage",
        "description": "Get hard disk drive capacity and free space.",
        "parameters": {"path": "Optional disk drive letter (default C:\\)"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_disk_usage,
    },
    "get_running_processes": {
        "name": "get_running_processes",
        "description": "Get top active processes consuming system memory.",
        "parameters": {"limit": "Number of processes to return (default 15)"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_get_running_processes,
    },
    "open_application": {
        "name": "open_application",
        "description": "Open a standard PC application like calculator, notepad, explorer, paint, browser.",
        "parameters": {"app_name": "Name of the application to launch"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_open_application,
    },
    "open_folder": {
        "name": "open_folder",
        "description": "Open a local folder in Windows File Explorer.",
        "parameters": {"folder_path": "Absolute path to folder"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_open_folder,
    },
    "read_file": {
        "name": "read_file",
        "description": "Read the top lines of a text or code file.",
        "parameters": {"file_path": "Path to file", "max_lines": "Max lines to read"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_read_file,
    },
    "search_local_files": {
        "name": "search_local_files",
        "description": "Search a local directory for files matching a keyword.",
        "parameters": {"directory": "Directory to search", "query": "Filename substring"},
        "permission": PermissionLevel.SAFE,
        "handler": tool_search_local_files,
    },
    "close_program": {
        "name": "close_program",
        "description": "Terminate a running application or process.",
        "parameters": {"process_name_or_pid": "Name of executable (e.g. notepad.exe) or PID"},
        "permission": PermissionLevel.CONFIRM,
        "handler": tool_close_program,
    },
    "delete_file": {
        "name": "delete_file",
        "description": "Permanently delete a specified file.",
        "parameters": {"file_path": "Path to file to delete"},
        "permission": PermissionLevel.CONFIRM,
        "handler": tool_delete_file,
    },
    "system_shutdown_pc": {
        "name": "system_shutdown_pc",
        "description": "Shut down the Windows computer.",
        "parameters": {"delay_seconds": "Delay before shutdown"},
        "permission": PermissionLevel.CONFIRM,
        "handler": tool_system_shutdown_pc,
    },
    "system_restart_pc": {
        "name": "system_restart_pc",
        "description": "Restart the Windows computer.",
        "parameters": {"delay_seconds": "Delay before restart"},
        "permission": PermissionLevel.CONFIRM,
        "handler": tool_system_restart_pc,
    },
}
