import json
import os
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any

from .config import STATUS_FILE, EMULATOR_PID_FILE, EMULATOR_LOG_FILE, BASE_DIR

def probe_kvm() -> Dict[str, Any]:
    """Inspects /dev/kvm and runs emulator -accel-check."""
    # Check /dev/kvm device node
    kvm_exists = os.path.exists("/dev/kvm")
    
    # Run emulator -accel-check
    accel_supported = False
    accel_output = ""
    try:
        proc = subprocess.run(
            ["emulator", "-accel-check"],
            capture_output=True,
            text=True,
            timeout=10
        )
        accel_output = (proc.stdout or "") + (proc.stderr or "")
        lower = accel_output.lower()
        if "usable" in lower or "available" in lower or "is working" in lower:
            accel_supported = True
    except Exception as e:
        accel_output = f"Error running accel-check: {str(e)}"

    if kvm_exists and accel_supported:
        mode = "hardware"
        message = "KVM hardware acceleration is active and usable."
    else:
        mode = "software"
        message = "KVM is unavailable. Running in fallback software emulation mode (-no-accel)."

    status_data = {
        "kvm_device_exists": kvm_exists,
        "accel_check_supported": accel_supported,
        "mode": mode,
        "message": message,
        "accel_check_raw": accel_output.strip()
    }

    try:
        STATUS_FILE.write_text(json.dumps(status_data, indent=2))
    except Exception:
        pass

    return status_data

def get_kvm_status() -> Dict[str, Any]:
    """Returns cached KVM status or probes if missing."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    return probe_kvm()

def get_emulator_pid() -> int | None:
    """Returns the emulator PID if running, or None."""
    if not EMULATOR_PID_FILE.exists():
        return None
    try:
        pid = int(EMULATOR_PID_FILE.read_text().strip())
        # Check if process is still alive
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None

def is_emulator_running() -> bool:
    return get_emulator_pid() is not None

def stop_emulator() -> bool:
    """Terminates the running emulator process."""
    pid = get_emulator_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            if EMULATOR_PID_FILE.exists():
                EMULATOR_PID_FILE.unlink()
            return True
        except Exception:
            return False
    return False

def start_emulator() -> bool:
    """Starts the emulator via the start-emulator.sh script."""
    if is_emulator_running():
        return True
    
    script_path = BASE_DIR / "scripts" / "start-emulator.sh"
    if not script_path.exists():
        return False

    try:
        subprocess.Popen(
            ["/bin/bash", str(script_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except Exception:
        return False

def restart_emulator() -> bool:
    stop_emulator()
    return start_emulator()

def get_emulator_logs(lines: int = 100) -> str:
    """Reads the last N lines of the emulator log."""
    if not EMULATOR_LOG_FILE.exists():
        return "No emulator logs recorded yet."
    try:
        proc = subprocess.run(
            ["tail", "-n", str(lines), str(EMULATOR_LOG_FILE)],
            capture_output=True,
            text=True,
            timeout=5
        )
        return proc.stdout or "Log is empty."
    except Exception as e:
        return f"Error reading logs: {e}"
