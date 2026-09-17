import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))
STATIC_DIR = BASE_DIR / "web"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Port & Network
PORT = int(os.getenv("PORT", "8000"))
VNC_PORT = int(os.getenv("VNC_PORT", "5900"))
WEBSOCKIFY_PORT = int(os.getenv("WEBSOCKIFY_PORT", "6080"))

# Android SDK
ANDROID_HOME = os.getenv("ANDROID_HOME", "/opt/android-sdk")
ANDROID_AVD_HOME = str(DATA_DIR / "avd")

# Status files
STATUS_FILE = Path("/tmp/kvm_status.json")
EMULATOR_PID_FILE = Path("/tmp/emulator.pid")
EMULATOR_LOG_FILE = DATA_DIR / "emulator.log"
