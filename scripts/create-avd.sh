#!/usr/bin/env bash
set -e

AVD_NAME="cloud_device"
DATA_DIR="${DATA_DIR:-/data}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
export ANDROID_AVD_HOME="${DATA_DIR}/avd"
export PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"

mkdir -p "${ANDROID_AVD_HOME}"

# Check if AVD already exists
if avdmanager list avd | grep -q "${AVD_NAME}"; then
    echo "AVD '${AVD_NAME}' already exists. Skipping creation."
    exit 0
fi

echo "Creating AVD '${AVD_NAME}' with system image system-images;android-30;google_apis;x86_64..."
echo "no" | avdmanager create avd \
    --name "${AVD_NAME}" \
    --package "system-images;android-30;google_apis;x86_64" \
    --force

AVD_CONFIG_FILE="${ANDROID_AVD_HOME}/${AVD_NAME}.avd/config.ini"

if [ -f "${AVD_CONFIG_FILE}" ]; then
    echo "Tuning AVD configuration in ${AVD_CONFIG_FILE}..."
    cat <<EOT >> "${AVD_CONFIG_FILE}"
hw.cpu.ncore=2
hw.ramSize=2048
vm.heapSize=256
hw.lcd.density=240
hw.lcd.width=720
hw.lcd.height=1280
hw.keyboard=yes
hw.mainKeys=no
hw.dPad=no
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
fastboot.forceColdBoot=no
disk.dataPartition.size=4096M
EOT
fi

echo "AVD '${AVD_NAME}' successfully configured in ${ANDROID_AVD_HOME}."
