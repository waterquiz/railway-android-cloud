import subprocess
import shutil
import base64
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional

KEY_MAP = {
    "HOME": 3,
    "BACK": 4,
    "CALL": 5,
    "ENDCALL": 6,
    "UP": 19,
    "DOWN": 20,
    "LEFT": 21,
    "RIGHT": 22,
    "ENTER": 66,
    "DEL": 67,
    "VOLUME_UP": 24,
    "VOLUME_DOWN": 25,
    "POWER": 26,
    "MENU": 82,
    "APP_SWITCH": 187,
    "WAKEUP": 224,
}

def run_cmd(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

def is_adb_available() -> bool:
    return shutil.which("adb") is not None

def get_devices() -> List[Dict[str, str]]:
    """Returns list of connected adb devices."""
    if not is_adb_available():
        return []
    try:
        res = run_cmd(["adb", "devices"], timeout=5)
        lines = res.stdout.strip().splitlines()
        devices = []
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                devices.append({"serial": parts[0], "state": parts[1]})
        return devices
    except Exception:
        return []

def is_boot_completed() -> bool:
    """Checks if Android has completed booting."""
    if not is_adb_available():
        return False
    try:
        res = run_cmd(["adb", "shell", "getprop", "sys.boot_completed"], timeout=5)
        return res.stdout.strip() == "1"
    except Exception:
        return False

def get_boot_status() -> Dict[str, Any]:
    """Returns detailed boot phase properties."""
    if not is_adb_available():
        return {"phase": "offline", "detail": "ADB not available"}

    devices = get_devices()
    if not devices:
        return {"phase": "starting", "detail": "Emulator process starting..."}

    dev_state = devices[0].get("state", "")
    if dev_state == "offline":
        return {"phase": "connecting", "detail": "Emulator connecting to ADB..."}

    try:
        boot_completed = run_cmd(["adb", "shell", "getprop", "sys.boot_completed"], timeout=3).stdout.strip()
        if boot_completed == "1":
            return {"phase": "ready", "detail": "Android OS Ready"}

        bootanim = run_cmd(["adb", "shell", "getprop", "init.svc.bootanim"], timeout=3).stdout.strip()
        if bootanim == "running":
            return {"phase": "bootanim", "detail": "Android Boot Animation Running..."}

        zygote = run_cmd(["adb", "shell", "getprop", "init.svc.zygote"], timeout=3).stdout.strip()
        if zygote == "running":
            return {"phase": "zygote", "detail": "System services starting up..."}

        return {"phase": "kernel", "detail": "Linux kernel initializing..."}
    except Exception:
        return {"phase": "booting", "detail": "Android booting..."}

def get_device_properties() -> Dict[str, str]:
    """Fetches key Android system properties."""
    props = {}
    if not is_boot_completed():
        return props
    try:
        keys = [
            ("ro.build.version.release", "android_version"),
            ("ro.build.version.sdk", "sdk_version"),
            ("ro.product.model", "model"),
            ("ro.product.manufacturer", "manufacturer"),
        ]
        for prop, label in keys:
            res = run_cmd(["adb", "shell", "getprop", prop], timeout=5)
            props[label] = res.stdout.strip()
    except Exception:
        pass
    return props

def extract_package_info(apk_path: Path) -> Dict[str, Any]:
    """Extracts package name and main activity from an APK file using aapt or zip analysis."""
    info = {"package_name": None, "main_activity": None, "app_name": None}

    # Attempt 1: aapt dump badging
    if shutil.which("aapt"):
        try:
            res = run_cmd(["aapt", "dump", "badging", str(apk_path)], timeout=10)
            if res.returncode == 0:
                pkg_match = re.search(r"package:\s*name='([^']+)'", res.stdout)
                if pkg_match:
                    info["package_name"] = pkg_match.group(1)

                act_match = re.search(r"launchable-activity:\s*name='([^']+)'", res.stdout)
                if act_match:
                    info["main_activity"] = act_match.group(1)

                label_match = re.search(r"application-label:'([^']+)'", res.stdout)
                if label_match:
                    info["app_name"] = label_match.group(1)
                return info
        except Exception:
            pass

    # Attempt 2: zipfile inspection for fallback heuristic
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            manifest_data = z.read("AndroidManifest.xml")
            # Extract UTF-8 or ASCII string patterns in binary manifest
            matches = re.findall(rb'[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+){2,}', manifest_data)
            for m in matches:
                decoded = m.decode('latin-1', errors='ignore')
                if not decoded.startswith("android.") and not decoded.startswith("com.android."):
                    info["package_name"] = decoded
                    break
    except Exception:
        pass

    return info

def install_apk(apk_path: Path) -> Dict[str, Any]:
    """Installs an APK on the emulator using adb install -r."""
    if not is_adb_available():
        return {"success": False, "message": "ADB is not available on this host."}
    
    if not is_boot_completed():
        return {"success": False, "message": "Emulator has not finished booting yet. Please wait."}

    info = extract_package_info(apk_path)

    try:
        res = run_cmd(["adb", "install", "-r", "-g", str(apk_path)], timeout=120)
        output = (res.stdout or "") + (res.stderr or "")
        success = "Success" in output
        return {
            "success": success,
            "message": output.strip(),
            "package_name": info.get("package_name"),
            "main_activity": info.get("main_activity"),
            "app_name": info.get("app_name")
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Installation timed out after 120 seconds."}
    except Exception as e:
        return {"success": False, "message": f"Error during installation: {str(e)}"}

def launch_app(package_name: str, activity: Optional[str] = None) -> Dict[str, Any]:
    """Launches an installed application via monkey or am start."""
    if not is_boot_completed():
        return {"success": False, "message": "Emulator is not ready."}

    try:
        if activity:
            cmd = ["adb", "shell", "am", "start", "-n", f"{package_name}/{activity}"]
        else:
            cmd = ["adb", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"]
        
        res = run_cmd(cmd, timeout=10)
        output = (res.stdout or "") + (res.stderr or "")
        return {"success": res.returncode == 0, "message": output.strip()}
    except Exception as e:
        return {"success": False, "message": f"Launch failed: {str(e)}"}

def send_key(key: str) -> Dict[str, Any]:
    """Sends a keycode to the Android device."""
    if not is_boot_completed():
        return {"success": False, "message": "Emulator is not ready."}

    keycode = KEY_MAP.get(key.upper())
    if keycode is None:
        try:
            keycode = int(key)
        except ValueError:
            return {"success": False, "message": f"Unknown keycode or name: {key}"}

    try:
        res = run_cmd(["adb", "shell", "input", "keyevent", str(keycode)], timeout=5)
        return {"success": res.returncode == 0, "keycode": keycode}
    except Exception as e:
        return {"success": False, "message": str(e)}

def send_text(text: str) -> Dict[str, Any]:
    """Types text into the focused Android element."""
    if not is_boot_completed():
        return {"success": False, "message": "Emulator is not ready."}

    # Escape spaces and shell metacharacters
    escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
    try:
        res = run_cmd(["adb", "shell", "input", "text", escaped], timeout=5)
        return {"success": res.returncode == 0}
    except Exception as e:
        return {"success": False, "message": str(e)}

def take_screenshot_base64() -> Optional[str]:
    """Captures a screenshot directly via adb."""
    if not is_boot_completed():
        return None
    try:
        res = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=10
        )
        if res.returncode == 0 and res.stdout:
            return base64.b64encode(res.stdout).decode("utf-8")
    except Exception:
        pass
    return None

def get_logcat(lines: int = 100) -> str:
    """Fetches the latest logcat lines."""
    if not is_adb_available():
        return "ADB is not available."
    try:
        res = run_cmd(["adb", "logcat", "-d", "-t", str(lines)], timeout=10)
        return res.stdout or "Logcat is empty."
    except Exception as e:
        return f"Error reading logcat: {str(e)}"

def list_installed_apps() -> List[str]:
    """Lists installed 3rd-party packages."""
    if not is_boot_completed():
        return []
    try:
        res = run_cmd(["adb", "shell", "pm", "list", "packages", "-3"], timeout=5)
        packages = []
        for line in res.stdout.splitlines():
            if line.startswith("package:"):
                packages.append(line.replace("package:", "").strip())
        return packages
    except Exception:
        return []
