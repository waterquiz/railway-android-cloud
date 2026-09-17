// Android Cloud Device - Frontend Logic

let currentSelectedFile = null;
let activeLogTab = "emulator"; // "emulator" or "logcat"
let lastPackageName = null;
let lastActivityName = null;

// DOM Elements
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const kvmBadge = document.getElementById("kvm-badge");
const kvmText = document.getElementById("kvm-text");

const diagKvmNode = document.getElementById("diag-kvm-node");
const diagAccelCheck = document.getElementById("diag-accel-check");
const diagMode = document.getElementById("diag-mode");
const diagOs = document.getElementById("diag-os");
const kvmExplanationText = document.getElementById("kvm-explanation-text");

const dropZone = document.getElementById("upload-form");
const fileInput = document.getElementById("apk-file-input");
const dropZonePrompt = document.getElementById("drop-zone-prompt");
const selectedFileInfo = document.getElementById("selected-file-info");
const selectedFilename = document.getElementById("selected-filename");
const selectedFilesize = document.getElementById("selected-filesize");
const uploadBtn = document.getElementById("upload-btn");
const progressContainer = document.getElementById("upload-progress-container");
const progressBar = document.getElementById("upload-progress-bar");
const progressText = document.getElementById("upload-progress-text");

const apkResultCard = document.getElementById("apk-result-card");
const resPackageName = document.getElementById("res-package-name");
const resActivity = document.getElementById("res-activity");
const resInstallStatus = document.getElementById("res-install-status");
const installBtn = document.getElementById("install-btn");
const launchBtn = document.getElementById("launch-btn");

const deviceTextInput = document.getElementById("device-text-input");
const sendTextBtn = document.getElementById("send-text-btn");

const novncFrame = document.getElementById("novnc-frame");
const screenOverlay = document.getElementById("screen-overlay");
const overlayTitle = document.getElementById("overlay-title");
const overlayDesc = document.getElementById("overlay-desc");
const overlayKvmNote = document.getElementById("overlay-kvm-note");
const refreshScreenBtn = document.getElementById("refresh-screen-btn");
const fullscreenBtn = document.getElementById("fullscreen-btn");

const tabEmulatorLogs = document.getElementById("tab-emulator-logs");
const tabLogcat = document.getElementById("tab-logcat");
const fetchLogsBtn = document.getElementById("fetch-logs-btn");
const logOutput = document.getElementById("log-output");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initDropZone();
    initControls();
    initLogs();
    pollStatus();
    setInterval(pollStatus, 4000);
});

// --- Status Poller ---
async function pollStatus() {
    try {
        const res = await fetch("/api/status");
        if (!res.ok) throw new Error("Status endpoint error");
        const data = await res.json();
        updateUI(data);
    } catch (err) {
        statusBadge.className = "badge badge-offline";
        statusText.textContent = "Server Offline";
    }
}

let overlayDismissedByUser = false;

function updateUI(data) {
    const isOnline = data.boot_completed;
    const isBooting = data.emulator_running && !data.boot_completed;

    // Status Badge
    if (isOnline) {
        statusBadge.className = "badge badge-online";
        statusText.textContent = "Emulator Online";
        screenOverlay.classList.add("hidden");
    } else if (isBooting) {
        statusBadge.className = "badge badge-booting";
        statusText.textContent = "Android Booting...";
        if (!overlayDismissedByUser) {
            screenOverlay.classList.remove("hidden");
        }
        overlayTitle.textContent = "Android OS is Booting...";
        overlayDesc.textContent = "Initial boot can take 1-3 minutes in software mode. Click below to view the live boot screen.";
    } else {
        statusBadge.className = "badge badge-offline";
        statusText.textContent = "Emulator Stopped";
        if (!overlayDismissedByUser) {
            screenOverlay.classList.remove("hidden");
        }
        overlayTitle.textContent = "Emulator is Offline";
        overlayDesc.textContent = "Waiting for emulator process to initialize.";
    }

    // KVM Diagnostics
    if (data.kvm) {
        const kvm = data.kvm;
        diagKvmNode.textContent = kvm.kvm_device_exists ? "Present (/dev/kvm)" : "Not Found";
        diagAccelCheck.textContent = kvm.accel_check_supported ? "Acceleration Usable" : "Unavailable";
        diagMode.textContent = kvm.mode === "hardware" ? "Hardware (KVM)" : "Software Fallback (-no-accel)";

        if (kvm.mode === "hardware") {
            kvmBadge.className = "badge badge-hardware";
            kvmText.textContent = "KVM: Active (Hardware)";
            kvmExplanationText.textContent = "🚀 KVM hardware acceleration is active. Android emulation runs at native speed.";
            overlayKvmNote.textContent = "KVM Acceleration: Hardware Enabled";
        } else {
            kvmBadge.className = "badge badge-warning";
            kvmText.textContent = "KVM: Fallback (Software)";
            kvmExplanationText.textContent = "⚠️ KVM not available on this host. Using software fallback mode (-no-accel). Booting and apps will run at reduced speed.";
            overlayKvmNote.textContent = "Running in software fallback mode (-no-accel). Booting may be slower.";
        }
    }

    // OS Properties
    if (data.device_info && data.device_info.android_version) {
        diagOs.textContent = `Android ${data.device_info.android_version} (API ${data.device_info.sdk_version || 30})`;
    } else {
        diagOs.textContent = isOnline ? "Android 11 (API 30)" : "Waiting for boot...";
    }
}

// --- Drag & Drop / File Selection ---
function initDropZone() {
    dropZone.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    uploadBtn.addEventListener("click", uploadSelectedAPK);
    installBtn.addEventListener("click", triggerInstall);
    launchBtn.addEventListener("click", triggerLaunch);
}

function handleFileSelect(file) {
    if (!file.name.endsWith(".apk")) {
        alert("Please select a valid .apk file.");
        return;
    }
    currentSelectedFile = file;
    selectedFilename.textContent = file.name;
    selectedFilesize.textContent = (file.size / (1024 * 1024)).toFixed(2) + " MB";
    dropZonePrompt.classList.add("hidden");
    selectedFileInfo.classList.remove("hidden");
    uploadBtn.disabled = false;
}

async function uploadSelectedAPK() {
    if (!currentSelectedFile) return;

    uploadBtn.disabled = true;
    progressContainer.classList.remove("hidden");
    progressBar.style.width = "20%";
    progressText.textContent = "Uploading APK to server...";

    const formData = new FormData();
    formData.append("file", currentSelectedFile);

    try {
        progressBar.style.width = "60%";
        const res = await fetch("/api/upload?auto_install=true", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        progressBar.style.width = "100%";

        if (!res.ok) {
            progressText.textContent = `Upload failed: ${data.detail || "Unknown error"}`;
            uploadBtn.disabled = false;
            return;
        }

        progressText.textContent = "Upload complete!";
        showApkResult(data);
    } catch (err) {
        progressText.textContent = "Network error during upload.";
        uploadBtn.disabled = false;
    }
}

function showApkResult(data) {
    apkResultCard.classList.remove("hidden");
    const pkg = data.package_info?.package_name || "Unknown Package";
    const act = data.package_info?.main_activity || "Default Launcher";

    lastPackageName = pkg;
    lastActivityName = act;

    resPackageName.textContent = pkg;
    resActivity.textContent = act;

    if (data.installed) {
        resInstallStatus.textContent = "Installed ✅";
        resInstallStatus.style.color = "var(--success)";
        installBtn.textContent = "Reinstall";
    } else {
        resInstallStatus.textContent = "Not Installed";
        resInstallStatus.style.color = "var(--warning)";
        installBtn.textContent = "Install APK";
    }
}

async function triggerInstall() {
    if (!currentSelectedFile) return;
    installBtn.disabled = true;
    installBtn.textContent = "Installing...";

    try {
        const res = await fetch("/api/install", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: currentSelectedFile.name })
        });
        const data = await res.json();
        if (data.success) {
            resInstallStatus.textContent = "Installed ✅";
            resInstallStatus.style.color = "var(--success)";
            alert("App successfully installed on Android emulator!");
        } else {
            alert(`Installation failed: ${data.message}`);
        }
    } catch (e) {
        alert(`Error installing APK: ${e.message}`);
    } finally {
        installBtn.disabled = false;
        installBtn.textContent = "Install APK";
    }
}

async function triggerLaunch() {
    if (!lastPackageName) {
        alert("No package available to launch.");
        return;
    }
    launchBtn.disabled = true;
    launchBtn.textContent = "Launching...";

    try {
        const res = await fetch("/api/launch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                package_name: lastPackageName,
                activity: lastActivityName !== "Default Launcher" ? lastActivityName : null
            })
        });
        const data = await res.json();
        if (!data.success) {
            alert(`Launch notice: ${data.message}`);
        }
    } catch (e) {
        alert(`Error launching app: ${e.message}`);
    } finally {
        launchBtn.disabled = false;
        launchBtn.textContent = "Launch App";
    }
}

// --- Virtual Controls ---
function initControls() {
    document.querySelectorAll(".key-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const key = btn.getAttribute("data-key");
            try {
                await fetch("/api/key", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ key })
                });
            } catch (err) {
                console.error("Key error:", err);
            }
        });
    });

    sendTextBtn.addEventListener("click", async () => {
        const text = deviceTextInput.value.trim();
        if (!text) return;
        try {
            await fetch("/api/text", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            deviceTextInput.value = "";
        } catch (err) {
            console.error("Text error:", err);
        }
    });

    deviceTextInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            sendTextBtn.click();
        }
    });

    refreshScreenBtn.addEventListener("click", () => {
        novncFrame.src = novncFrame.src;
    });

    fullscreenBtn.addEventListener("click", () => {
        if (novncFrame.requestFullscreen) {
            novncFrame.requestFullscreen();
        }
    });

    const dismissOverlayBtn = document.getElementById("dismiss-overlay-btn");
    if (dismissOverlayBtn) {
        dismissOverlayBtn.addEventListener("click", () => {
            overlayDismissedByUser = true;
            screenOverlay.classList.add("hidden");
        });
    }

    const toggleOverlayBtn = document.getElementById("toggle-overlay-btn");
    if (toggleOverlayBtn) {
        toggleOverlayBtn.addEventListener("click", () => {
            if (screenOverlay.classList.contains("hidden")) {
                overlayDismissedByUser = false;
                screenOverlay.classList.remove("hidden");
            } else {
                overlayDismissedByUser = true;
                screenOverlay.classList.add("hidden");
            }
        });
    }
}

// --- Logs Handling ---
function initLogs() {
    tabEmulatorLogs.addEventListener("click", () => {
        activeLogTab = "emulator";
        tabEmulatorLogs.classList.add("active");
        tabLogcat.classList.remove("active");
        fetchActiveLogs();
    });

    tabLogcat.addEventListener("click", () => {
        activeLogTab = "logcat";
        tabLogcat.classList.add("active");
        tabEmulatorLogs.classList.remove("active");
        fetchActiveLogs();
    });

    fetchLogsBtn.addEventListener("click", fetchActiveLogs);
    fetchActiveLogs();
}

async function fetchActiveLogs() {
    const endpoint = activeLogTab === "emulator" ? "/api/logs/emulator" : "/api/logs/logcat";
    try {
        const res = await fetch(endpoint);
        if (res.ok) {
            const data = await res.json();
            logOutput.textContent = data.logs || "No log content.";
            logOutput.scrollTop = logOutput.scrollHeight;
        }
    } catch (e) {
        logOutput.textContent = "Failed to fetch logs.";
    }
}
