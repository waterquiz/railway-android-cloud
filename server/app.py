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
    devices = adb.get_devices() if is_running else []
    props = adb.get_device_properties() if boot_done else {}
    installed_apps = adb.list_installed_apps() if boot_done else []

    return {
        "status": "online" if boot_done else ("booting" if is_running else "offline"),
        "emulator_running": is_running,
        "boot_completed": boot_done,
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
        install_result = adb.install_apk(target_path)

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
    await websocket.accept(subprotocol="binary")
    
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", VNC_PORT)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Could not connect to VNC server: {str(e)}")
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
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
                data = await reader.read(4096)
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

# ----------------- Static Frontend -----------------

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="web")
