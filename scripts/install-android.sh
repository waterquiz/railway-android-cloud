#!/usr/bin/env bash
set -e

echo "========================================="
echo " Installing Android SDK & System Images "
echo "========================================="

export ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
mkdir -p "${ANDROID_HOME}/cmdline-tools"

# Download Android command-line tools if not present
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
TMP_ZIP="/tmp/cmdline-tools.zip"

if [ ! -f "${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager" ]; then
    echo "Downloading Android Command Line Tools..."
    curl -fsSL -o "${TMP_ZIP}" "${CMDLINE_TOOLS_URL}"
    mkdir -p /tmp/cmdline-tools
    unzip -q -d /tmp/cmdline-tools "${TMP_ZIP}"
    rm -f "${TMP_ZIP}"
    
    mkdir -p "${ANDROID_HOME}/cmdline-tools/latest"
    cp -r /tmp/cmdline-tools/cmdline-tools/* "${ANDROID_HOME}/cmdline-tools/latest/"
    rm -rf /tmp/cmdline-tools
fi

export PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"

echo "Accepting licenses..."
yes | sdkmanager --licenses > /dev/null 2>&1 || true

echo "Installing platform-tools, emulator, and Android 30 system image..."
sdkmanager --install \
    "platform-tools" \
    "emulator" \
    "system-images;android-30;google_apis;x86_64"

echo "Android SDK installation completed successfully."
