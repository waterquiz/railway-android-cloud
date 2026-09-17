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

# 1. Start virtual display (Xvfb)
echo "[1/4] Starting Xvfb on display :0 (720x1280x24)..."
Xvfb :0 -screen 0 720x1280x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. Start VNC server (x11vnc on :5900)
echo "[2/4] Starting x11vnc server on port 5900..."
x11vnc -display :0 -forever -shared -nopw -rfbport 5900 -quiet > /dev/null 2>&1 &
X11VNC_PID=$!
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
