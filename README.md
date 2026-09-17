# Railway Android Cloud Device

A cloud-hosted Android Virtual Device container designed for [Railway](https://railway.app), equipped with **intelligent KVM hardware detection + software fallback mode (`-no-accel`)**, in-browser **noVNC live display & touch/mouse control**, and an **APK manager dashboard** with automated ADB installation and application launching.

---

## 📐 Architecture

```
                    Railway HTTPS URL ($PORT)
                               │
                ┌──────────────┴──────────────┐
                │     FastAPI Web Server      │
                │  (Dashboard UI & REST API)  │
                └──────────────┬──────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
      REST API            Web UI / noVNC       ADB Manager
    (/api/upload,      (Live Screen View,   (install, launch,
     /api/status,       Touch/Mouse/Keys,    keyevents, logs)
     /api/emulator)     Drag & Drop APK)           │
           │                   │                   │
           ▼                   ▼                   ▼
    Emulator Manager    Xvfb Display (:0)    Android 11 (API 30)
  (KVM check, fallback,  ▲                         ▲
   -no-accel, health)    │                         │
           │             │ x11vnc (:5900)          │
           │             │ websockify bridge       │
           └─────────────┴─────────────────────────┘
```

---

## ⚡ KVM Hardware Acceleration & Cloud Fallback Mode

Android's official emulator documentation states that accelerated x86/x86_64 emulation relies on Linux KVM (`/dev/kvm`).

### How this project handles Railway & Cloud Environments:
During container startup, the system automatically runs:
1. **Device node test**: `ls -l /dev/kvm`
2. **Acceleration check**: `emulator -accel-check`

- **If KVM is available**: The emulator boots with native hardware acceleration (`-accel on`).
- **If KVM is unavailable** (standard on shared cloud containers like Railway): The emulator cleanly falls back to software emulation (`-no-accel -gpu swiftshader_indirect`).
- **UI Transparency**: The web dashboard highlights the active acceleration mode in real-time (`KVM: Active (Hardware)` or `KVM: Fallback (Software)`) alongside raw diagnostic output.

> [!NOTE]
> Running with `-no-accel` uses pure software CPU emulation. It allows the Android OS and APKs to function, but boot time and interactive frame rates will be slower than on bare-metal or KVM-enabled hosts.

---

## 🚀 One-Click Railway Deployment

### 1. Push to GitHub
Create a GitHub repository and push this codebase:
```bash
git init
git add .
git commit -m "Initial commit of Railway Android Cloud Device"
git branch -M main
git remote add origin https://github.com/<your-user>/railway-android-cloud.git
git push -u origin main
```

### 2. Deploy on Railway
1. Log in to [Railway](https://railway.app).
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your repository.
4. Railway will automatically detect the root `Dockerfile` and `railway.toml`.

### 3. Add Persistent Volume (Optional, Recommended)
To preserve the Android emulator's user state across container restarts:
1. Go to your Railway service **Settings** → **Volumes**.
2. Click **Add Volume**.
3. Set the Mount Path to:
   ```text
   /data
   ```

### 4. Expose Public Networking
1. Go to your service **Settings** → **Networking**.
2. Click **Generate Domain**.
3. Visit the generated HTTPS domain in your browser!

---

## 🖥️ Web Dashboard & Features

### 📦 APK Management
- **Drag & Drop**: Drag any `.apk` file into the upload area or click to select.
- **Auto-Inspection**: Automatically parses the package name and launchable activity via `aapt`.
- **1-Click Install**: Installs to the emulator using `adb install -r -g`.
- **1-Click Launch**: Launches the installed app using `adb shell monkey` or `am start`.

### 📱 Live Android Screen (noVNC)
- Interactive live display directly in the browser.
- Supports mouse clicks, touch dragging, and keyboard input.
- Automatically routed through the single exposed Railway HTTPS port via an asynchronous WebSocket RFB proxy.

### 🎮 Virtual Navigation Controls
- Hardware keys: **Back**, **Home**, **Recents**, **Volume Down**, **Volume Up**, **Power**.
- Real-time text injection into focused Android text fields.

### 📋 Live Logs
- Switch between **Emulator Logs** (boot messages, QEMU output) and **Logcat** (Android OS runtime logs).

---

## 🛠️ Local Docker Testing

You can build and test this container locally with or without KVM hardware acceleration:

### Run with KVM Acceleration (Linux host with KVM enabled):
```bash
docker build -t railway-android-cloud .
docker run -it --rm \
    --device /dev/kvm \
    -p 8000:8000 \
    -v $(pwd)/data:/data \
    railway-android-cloud
```

### Run in Fallback Mode (Windows / Mac / Cloud without KVM):
```bash
docker build -t railway-android-cloud .
docker run -it --rm \
    -p 8000:8000 \
    -v $(pwd)/data:/data \
    railway-android-cloud
```
Then open `http://localhost:8000` in your web browser.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/status` | `GET` | Device boot state, KVM status, system info, installed apps |
| `/api/upload` | `POST` | Upload APK and optionally auto-install (`?auto_install=true`) |
| `/api/install` | `POST` | Install an uploaded APK (`{"filename": "app.apk"}`) |
| `/api/launch` | `POST` | Launch an application (`{"package_name": "com.example.app"}`) |
| `/api/key` | `POST` | Send keyevent (`{"key": "HOME"}`) |
| `/api/text` | `POST` | Inject text into active Android input field (`{"text": "hello"}`) |
| `/api/screenshot`| `GET` | Capture raw screenshot encoded as base64 |
| `/api/logs/emulator` | `GET` | Stream recent emulator startup logs |
| `/api/logs/logcat` | `GET` | Stream recent Android OS logcat output |
| `/websockify` | `WebSocket` | Binary RFB WebSocket bridge to internal VNC display |

---

## 📁 Repository Structure

```
.
├── Dockerfile                  # Ubuntu 22.04 container with Android SDK & noVNC
├── railway.toml                # Railway deployment & healthcheck config
├── start.sh                    # Container entrypoint (Xvfb, x11vnc, emulator, FastAPI)
├── requirements.txt            # Python dependencies (FastAPI, uvicorn, websockets)
├── README.md                   # Documentation & setup guide
│
├── server/                     # FastAPI backend application
│   ├── app.py                  # API endpoints, static mount & WebSocket proxy
│   ├── emulator.py             # KVM probe and emulator lifecycle supervisor
│   ├── adb.py                  # ADB shell commands, APK inspection, key injection
│   └── config.py               # Environment configuration & directory paths
│
├── web/                        # Responsive frontend dashboard
│   ├── index.html              # Dashboard UI & embedded noVNC canvas
│   ├── app.js                  # Frontend controllers, status poller & handlers
│   └── style.css               # Modern dark-mode styling
│
├── scripts/                    # Automation scripts
│   ├── install-android.sh      # Downloads Android SDK & system images
│   ├── create-avd.sh           # Creates and tunes the Android Virtual Device
│   └── start-emulator.sh       # KVM probe & startup with software fallback
│
├── uploads/                    # Directory for uploaded APK files
└── data/                       # Directory for persistent AVD userdata & logs
```
