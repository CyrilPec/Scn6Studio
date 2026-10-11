"""
scn6_server_fastApi.py
FastAPI server for SCN6 hardware.
Calls scn6_dll.TmbsController directly.
Requires Windows and 32-bit Python.
Run:
    py -3.12-32 scn6_server_fastApi.py
Swagger:
    http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import logging
import threading
from contextlib import asynccontextmanager
from typing import Any
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from scn6_dll import (
    TmbsController,
    SCN6Error,
    SCN6AxisError,
    SCN6CommunicationError,
    SCN6MotionError,
)
# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scn6_server")
# A single controller instance owns the DLL connection.
controller: TmbsController | None = None
# Serialize DLL calls. Do not call a non-thread-safe DLL concurrently.
dll_lock = threading.RLock()
# ---------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------
class MoveRequest(BaseModel):
    axis: int = Field(ge=0, le=15)
    position: int
class IncrementalMoveRequest(BaseModel):
    axis: int = Field(ge=0, le=15)
    distance: int
class ArmRequest(BaseModel):
    armed: bool
class WaitRequest(BaseModel):
    timeout: float = Field(default=30.0, gt=0, le=300)
    interval: float = Field(default=0.05, gt=0, le=5)
# ---------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global controller
    logger.info("Creating SCN6 controller wrapper")
    # This loads the DLL. It does not initialize the hardware connection.
    with dll_lock:
        controller = TmbsController()
    logger.info("SCN6 server ready; call POST /initialize to connect")
    try:
        yield
    finally:
        if controller is not None:
            try:
                with dll_lock:
                    controller.disconnect()
                logger.info("SCN6 disconnected")
            except Exception:
                logger.exception("Error disconnecting SCN6")
            controller = None
app = FastAPI(
    title="SCN6 Controller API",
    description=(
        "FastAPI HTTP interface for Blender and SCN6 hardware. "
        "Uses scn6_dll.TmbsController directly."
    ),
    version="5.0.0",
    lifespan=lifespan,
)
# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def get_controller() -> TmbsController:
    if controller is None:
        raise HTTPException(
            status_code=503,
            detail="Controller DLL has not been loaded.",
        )
    return controller
def check_axis(axis: int) -> None:
    if not 0 <= axis <= 15:
        raise HTTPException(
            status_code=400,
            detail="Axis must be between 0 and 15 (0..F).",
        )
def api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SCN6AxisError):
        code = 400
    elif isinstance(exc, SCN6CommunicationError):
        code = 503
    elif isinstance(exc, SCN6MotionError):
        code = 409
    elif isinstance(exc, SCN6Error):
        code = 500
    elif isinstance(exc, (ValueError, TypeError)):
        code = 400
    else:
        logger.exception("Unexpected SCN6 error", exc_info=exc)
        code = 500
    return HTTPException(status_code=code, detail=str(exc))
def json_safe(value: Any) -> Any:
    """Convert DLL wrapper values into JSON-compatible values."""
    if isinstance(value, bytes):
        return list(value)
    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
def require_initialized(c: TmbsController) -> None:
    if not c.initialized:
        raise HTTPException(
            status_code=409,
            detail="SCN6 is not initialized. Call POST /initialize first.",
        )
def status_snapshot(c: TmbsController) -> dict:
    return {
        "initialized": bool(c.initialized),
        "connected_axes": (
            c.connected_axes() if c.initialized else []
        ),
        "communication": (
            c.communication_info() if c.initialized else None
        ),
    }
# ---------------------------------------------------------------------
# Root and status
# ---------------------------------------------------------------------
@app.get("/")
def root():
    c = get_controller()
    return {
        "name": "SCN6 Controller API",
        "version": app.version,
        "running": True,
        "initialized": c.initialized,
        "connected_axes": (
            c.connected_axes() if c.initialized else []
        ),
        "docs": "/docs",
    }
@app.get("/status")
def status():
    c = get_controller()
    try:
        with dll_lock:
            return json_safe(status_snapshot(c))
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(exc) from exc
# ---------------------------------------------------------------------
# Connect / disconnect
# ---------------------------------------------------------------------
@app.post("/initialize")
def initialize():
    c = get_controller()
    try:
        with dll_lock:
            result = c.initialize()
            current_status = status_snapshot(c)
        return {
            "ok": True,
            "result": json_safe(result),
            "status": json_safe(current_status),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/connect")
def connect():
    return initialize()
@app.post("/disconnect")
def disconnect():
    c = get_controller()
    try:
        with dll_lock:
            result = c.disconnect()
        return {
            "ok": True,
            "result": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.get("/communication")
def communication():
    c = get_controller()
    try:
        with dll_lock:
            require_initialized(c)
            result = c.communication_info()
        return json_safe(result)
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(exc) from exc
# ---------------------------------------------------------------------
# Axis discovery
# ---------------------------------------------------------------------
@app.get("/axes")
def axes():
    c = get_controller()
    try:
        with dll_lock:
            require_initialized(c)
            return {
                "connected_axes": json_safe(c.connected_axes()),
                "axis_info": json_safe(c.axis_info()),
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/axes/refresh")
def refresh_axes():
    c = get_controller()
    try:
        with dll_lock:
            result = c.refresh_connected_axes()
            response = {
                "ok": True,
                "result": json_safe(result),
                "connected_axes": json_safe(c.connected_axes()),
                "axis_info": json_safe(c.axis_info()),
            }
        return response
    except Exception as exc:
        raise api_error(exc) from exc
# ---------------------------------------------------------------------
# Servo control
# ---------------------------------------------------------------------
@app.post("/arm")
def set_arm(request: ArmRequest):
    """
    Enable or disable the servo on all discovered axes.
    This calls the wrapper's set_son/set_soff methods directly.
    """
    c = get_controller()
    try:
        with dll_lock:
            require_initialized(c)
            connected = c.connected_axes()
            if not connected:
                raise SCN6AxisError("No connected axes found.")
            results = []
            for axis in connected:
                if request.armed:
                    if c.set_son is None:
                        raise SCN6MotionError(
                            "set_son DLL export is unavailable."
                        )
                    result = c.set_son(axis)
                else:
                    if c.set_soff is None:
                        raise SCN6MotionError(
                            "set_soff DLL export is unavailable."
                        )
                    result = c.set_soff(axis)
                results.append({
                    "axis": axis,
                    "result": json_safe(result),
                })
        return {
            "ok": True,
            "armed": request.armed,
            "results": results,
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/disarm")
def disarm():
    return set_arm(ArmRequest(armed=False))
# ---------------------------------------------------------------------
# Axis status and position
# ---------------------------------------------------------------------
@app.get("/axes/status")
def all_axis_status():
    c = get_controller()
    try:
        with dll_lock:
            result = c.read_all_axis_status()
        return json_safe(result)
    except Exception as exc:
        raise api_error(exc) from exc
@app.get("/axes/{axis}/status")
def axis_status(axis: int):
    check_axis(axis)
    c = get_controller()
    try:
        with dll_lock:
            result = c.read_axis_status(axis)
        return json_safe(result)
    except Exception as exc:
        raise api_error(exc) from exc
@app.get("/axes/{axis}/position")
def axis_position(axis: int):
    check_axis(axis)
    c = get_controller()
    try:
        with dll_lock:
            result = c.read_controller_position(axis)
        return json_safe(result)
    except Exception as exc:
        raise api_error(exc) from exc
@app.get("/position/{axis}")
def position(axis: int):
    return axis_position(axis)
# ---------------------------------------------------------------------
# Direct motion
# ---------------------------------------------------------------------
@app.post("/move")
def move(request: MoveRequest):
    c = get_controller()
    try:
        with dll_lock:
            result = c.direct_move_absolute(
                request.axis,
                request.position,
            )
        return {
            "ok": True,
            "axis": request.axis,
            "position": request.position,
            "result": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/move/absolute")
def move_absolute(request: MoveRequest):
    return move(request)
@app.post("/axes/move/absolute")
def axes_move_absolute(request: MoveRequest):
    return move(request)
@app.post("/move/incremental")
def move_incremental(request: IncrementalMoveRequest):
    c = get_controller()
    try:
        with dll_lock:
            result = c.direct_move_incremental(
                request.axis,
                request.distance,
            )
        return {
            "ok": True,
            "axis": request.axis,
            "distance": request.distance,
            "result": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/axes/move/incremental")
def axes_move_incremental(request: IncrementalMoveRequest):
    return move_incremental(request)
# ---------------------------------------------------------------------
# Prepared motion
# ---------------------------------------------------------------------
@app.post("/prepare/absolute")
def prepare_absolute(request: MoveRequest):
    c = get_controller()
    try:
        with dll_lock:
            result = c.prepare_absolute_move(
                request.axis,
                request.position,
            )
        return {
            "ok": True,
            "axis": request.axis,
            "position": request.position,
            "result": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/prepare/incremental")
def prepare_incremental(request: IncrementalMoveRequest):
    c = get_controller()
    try:
        with dll_lock:
            result = c.prepare_incremental_move(
                request.axis,
                request.distance,
            )
        return {
            "ok": True,
            "axis": request.axis,
            "distance": request.distance,
            "result": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.get("/prepared")
def prepared():
    c = get_controller()
    try:
        with dll_lock:
            result = c.prepared_axes()
        return {"axes": json_safe(result)}
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/prepare/clear")
def prepare_clear():
    c = get_controller()
    try:
        with dll_lock:
            result = c.clear_motion_buffer()
        return json_safe(result)
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/prepare/start")
def prepare_start():
    c = get_controller()
    try:
        with dll_lock:
            result = c.start_prepared_moves()
        return {
            "ok": True,
            "started": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
@app.post("/prepare/wait")
def prepare_wait(request: WaitRequest):
    c = get_controller()
    try:
        with dll_lock:
            result = c.wait_for_prepared_axes(
                timeout=request.timeout,
                interval=request.interval,
            )
        return {
            "ok": True,
            "finished": json_safe(result),
        }
    except Exception as exc:
        raise api_error(exc) from exc
# ---------------------------------------------------------------------
# Shutdown / entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
