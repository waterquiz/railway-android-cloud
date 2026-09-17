#!/usr/bin/env bash
set -e

AVD_NAME="cloud_device"
DATA_DIR="${DATA_DIR:-/data}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
export ANDROID_AVD_HOME="${DATA_DIR}/avd"
export PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"
export DISPLAY="${DISPLAY:-:0}"

STATUS_FILE="/tmp/kvm_status.json"
EMULATOR_LOG="${DATA_DIR}/emulator.log"

echo "========================================="
echo " Android Emulator Acceleration & KVM Check"
echo "========================================="

KVM_EXISTS=false
KVM_ACCEL=false
ACCEL_CHECK_OUTPUT=""

echo "[CHECK] Inspecting /dev/kvm device..."
if [ -e /dev/kvm ]; then
    ls -l /dev/kvm
    KVM_EXISTS=true
    echo "[INFO] /dev/kvm node exists."
else
    echo "[WARN] /dev/kvm does NOT exist."
fi

echo "[CHECK] Running emulator -accel-check..."
ACCEL_CHECK_OUTPUT=$(emulator -accel-check 2>&1 || true)
echo "${ACCEL_CHECK_OUTPUT}"

if echo "${ACCEL_CHECK_OUTPUT}" | grep -iq "accel.*usable\|acceleration.*available\|KVM is working"; then
    KVM_ACCEL=true
fi

EXTRA_FLAGS=""
MODE="hardware"
MESSAGE=""

if [ "$KVM_EXISTS" = true ] && [ "$KVM_ACCEL" = true ]; then
    echo "========================================="
    echo " >>> KVM ACCELERATION AVAILABLE <<<      "
    echo " Launching emulator with KVM acceleration"
    echo "========================================="
    EXTRA_FLAGS="-accel on"
    MODE="hardware"
    MESSAGE="KVM hardware acceleration is active and usable."
else
    echo "========================================="
    echo " >>> KVM ACCELERATION UNAVAILABLE <<<    "
    echo " Fallback: Launching with -no-accel      "
    echo " (Performance will be slower on cloud)   "
    echo "========================================="
    EXTRA_FLAGS="-no-accel"
    MODE="software"
    MESSAGE="KVM unavailable. Running in fallback software emulation mode (-no-accel)."
fi

# Write status JSON for API & UI
cat <<EOF > "${STATUS_FILE}"
{
  "kvm_device_exists": ${KVM_EXISTS},
  "accel_check_supported": ${KVM_ACCEL},
  "mode": "${MODE}",
  "message": "${MESSAGE}",
  "accel_check_raw": $(echo "${ACCEL_CHECK_OUTPUT}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
}
EOF

echo "Starting emulator '${AVD_NAME}' (Output -> ${EMULATOR_LOG})..."

# Launch Android emulator in background
# -gpu swiftshader_indirect renders OpenGL in software to Xvfb
# -no-snapshot prevents corrupted state on container restart
# -no-audio and -no-boot-anim save CPU cycles
nohup emulator \
    -avd "${AVD_NAME}" \
    -gpu swiftshader_indirect \
    -no-audio \
    -no-boot-anim \
    -no-snapshot \
    -camera-back none \
    -camera-front none \
    -timezone UTC \
    ${EXTRA_FLAGS} > "${EMULATOR_LOG}" 2>&1 &

EMULATOR_PID=$!
echo "${EMULATOR_PID}" > /tmp/emulator.pid
echo "Emulator started with PID ${EMULATOR_PID}."
