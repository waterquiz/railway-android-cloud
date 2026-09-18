#!/usr/bin/env bash
set -e

echo "=========================================="
echo " Starting Railway Android Cloud Container "
echo "=========================================="

PORT="${PORT:-8000}"
export PORT
export DATA_DIR="${DATA_DIR:-/data}"
export UPLOADS_DIR="${UPLOADS_DIR:-/uploads}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
export ANDROID_AVD_HOME="${DATA_DIR}/avd"
export PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"
export DISPLAY="${DISPLAY:-:0}"

# Ensure directories exist
mkdir -p "${DATA_DIR}/avd" "${UPLOADS_DIR}"

# 1. Start virtual display (Xvfb) and Window Manager (fluxbox)
echo "[1/4] Starting Xvfb on display :0 (800x1400x24)..."
Xvfb :0 -screen 0 800x1400x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2
fluxbox -display :0 > /dev/null 2>&1 &
sleep 1

# 2. Start VNC server (x11vnc on :5900 with auto-restart supervisor)
echo "[2/4] Starting x11vnc server on port 5900 with auto-restart..."
while true; do
    x11vnc -display :0 -forever -shared -nopw -rfbport 5900 -repeat -noxdamage -wait 50 -defer 50 -quiet
    sleep 1
done > /dev/null 2>&1 &
sleep 1

# Start ADB server so emulator connects immediately
echo "[ADB] Starting ADB server on port 5037..."
adb start-server

# 3. Create AVD if needed & Launch Emulator
echo "[3/4] Preparing AVD and starting Android Emulator..."
/bin/bash /app/scripts/create-avd.sh
/bin/bash /app/scripts/start-emulator.sh

# 4. Start FastAPI server (serving Web UI, REST API, and noVNC WebSocket bridge)
echo "[4/4] Starting FastAPI server on port ${PORT}..."
exec uvicorn server.app:app --host 0.0.0.0 --port "${PORT}"
