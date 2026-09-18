import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import UPLOADS_DIR, STATIC_DIR, VNC_PORT
from . import adb
from . import emulator

app = FastAPI(title="Railway Android Cloud Device", version="1.0.0")

# Enable CORS for external API consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class KeyRequest(BaseModel):
    key: str

class TextRequest(BaseModel):
    text: str

class LaunchRequest(BaseModel):
    package_name: str
    activity: Optional[str] = None

class InstallRequest(BaseModel):
    filename: str

# ----------------- Status & Diagnostics -----------------

@app.get("/api/status")
def get_status():
    kvm_info = emulator.get_kvm_status()
    is_running = emulator.is_emulator_running()
    boot_done = adb.is_boot_completed() if is_running else False
    boot_phase = adb.get_boot_status() if is_running else {"phase": "offline", "detail": "Emulator offline"}
    devices = adb.get_devices() if is_running else []
    props = adb.get_device_properties() if boot_done else {}
    installed_apps = adb.list_installed_apps() if boot_done else []

    return {
        "status": "online" if boot_done else ("booting" if is_running else "offline"),
        "emulator_running": is_running,
        "boot_completed": boot_done,
        "boot_phase": boot_phase,
        "kvm": kvm_info,
        "devices": devices,
        "device_info": props,
        "installed_apps": installed_apps
    }

@app.get("/api/logs/emulator")
def get_emulator_logs(lines: int = 100):
    return {"logs": emulator.get_emulator_logs(lines)}

@app.get("/api/logs/logcat")
def get_logcat(lines: int = 100):
    return {"logs": adb.get_logcat(lines)}

@app.post("/api/emulator/restart")
def restart_emulator():
    success = emulator.restart_emulator()
    return {"success": success, "message": "Restart command issued"}

# ----------------- APK Upload & Management -----------------

pending_install_results = {}

async def wait_and_install(apk_path: Path):
    """Waits for Android to finish booting, then automatically installs the APK."""
    for _ in range(60): # Poll for up to 5 minutes
        await asyncio.sleep(5)
        if adb.is_boot_completed():
            res = adb.install_apk(apk_path)
            pending_install_results[apk_path.name] = res
            break

@app.post("/api/upload")
async def upload_apk(file: UploadFile = File(...), auto_install: bool = True):
    if not file.filename.endswith(".apk"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an .apk")

    target_path = UPLOADS_DIR / file.filename
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save APK: {str(e)}")

    info = adb.extract_package_info(target_path)
    install_result = None

    if auto_install:
        if adb.is_boot_completed():
            install_result = adb.install_apk(target_path)
        else:
            install_result = {
                "success": False,
                "pending_boot": True,
                "message": "APK uploaded! Android is currently completing startup and will install it automatically when ready."
            }
            asyncio.create_task(wait_and_install(target_path))

    return {
        "filename": file.filename,
        "size_bytes": target_path.stat().st_size,
        "package_info": info,
        "installed": install_result.get("success", False) if install_result else False,
        "install_details": install_result
    }

@app.post("/api/install")
def install_uploaded_apk(req: InstallRequest):
    target_path = UPLOADS_DIR / req.filename
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Specified APK file not found in uploads.")
    
    if not adb.is_boot_completed():
        asyncio.create_task(wait_and_install(target_path))
        return {
            "success": False,
            "pending_boot": True,
            "message": "Android is still completing startup. App queued and will install automatically upon boot."
        }

    result = adb.install_apk(target_path)
    return result

@app.post("/api/launch")
def launch_application(req: LaunchRequest):
    result = adb.launch_app(req.package_name, req.activity)
    return result

# ----------------- Controls & Input -----------------

@app.post("/api/key")
def press_key(req: KeyRequest):
    result = adb.send_key(req.key)
    return result

@app.post("/api/text")
def type_text(req: TextRequest):
    result = adb.send_text(req.text)
    return result

@app.get("/api/screenshot")
def capture_screenshot():
    b64_data = adb.take_screenshot_base64()
    if not b64_data:
        raise HTTPException(status_code=503, detail="Emulator screen is not available.")
    return {"image_base64": b64_data}

# ----------------- WebSocket RFB (noVNC Proxy) -----------------

@app.websocket("/websockify")
async def websocket_vnc_proxy(websocket: WebSocket):
    """
    Bridges browser WebSocket RFB traffic to local VNC server (x11vnc :5900).
    Allows noVNC to work seamlessly through Railway's single exposed HTTPS port.
    """
    subprotocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
    subprotocols = [s.strip() for s in subprotocols if s.strip()]
    selected_subprotocol = "binary" if "binary" in subprotocols else None

    if selected_subprotocol:
        await websocket.accept(subprotocol=selected_subprotocol)
    else:
        await websocket.accept()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", VNC_PORT)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Could not connect to VNC server: {str(e)}")
        return

    async def ws_to_tcp():
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message and message["bytes"]:
                    writer.write(message["bytes"])
                    await writer.drain()
                elif "text" in message and message["text"]:
                    writer.write(message["text"].encode("latin1"))
                    await writer.drain()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            writer.close()

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                await websocket.send_bytes(data)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass

    task_ws = asyncio.create_task(ws_to_tcp())
    task_tcp = asyncio.create_task(tcp_to_ws())

    done, pending = await asyncio.wait(
        [task_ws, task_tcp],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

    try:
        await websocket.close()
    except Exception:
        pass

# ----------------- Static Frontend & noVNC -----------------

novnc_system_path = Path("/usr/share/novnc")
if novnc_system_path.exists():
    app.mount("/novnc", StaticFiles(directory=str(novnc_system_path), html=True), name="novnc")
elif (STATIC_DIR / "novnc").exists():
    app.mount("/novnc", StaticFiles(directory=str(STATIC_DIR / "novnc"), html=True, follow_symlink=True), name="novnc")

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True, follow_symlink=True), name="web")

