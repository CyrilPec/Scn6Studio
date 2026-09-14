"""
SCN6 FastAPI server.
This server owns the TmbsController and exposes a small HTTP API for Blender.
Run with: python scn6_server.py
Swagger: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import threading
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from scn6_dll import TmbsController, SCN6Error, SCN6AxisError, SCN6CommunicationError, SCN6MotionError
app = FastAPI(title="SCN6 Controller API", description="HTTP interface between Blender and the SCN6 controller.", version="3.0.0")
controller: Optional[TmbsController] = None
controller_lock = threading.RLock()
armed = False
class MoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    position: int
class IncrementalMoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    distance: int
class AxisRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
class ArmRequest(BaseModel):
    armed: bool
def get_controller() -> TmbsController:
    if controller is None:
        raise HTTPException(status_code=503, detail="SCN6 controller is not initialized")
    if not controller.initialized:
        raise HTTPException(status_code=503, detail="SCN6 controller is not initialized")
    return controller
def check_axis(axis: int) -> None:
    if axis < 0 or axis > 15:
        raise HTTPException(status_code=400, detail="Axis must be between 0 and 15 (0..F)")
def api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SCN6AxisError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SCN6CommunicationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SCN6MotionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, SCN6Error):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))
def json_safe(value):
    if isinstance(value, bytes):
        return list(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value
def require_armed() -> None:
    if not armed:
        raise HTTPException(status_code=409, detail="Controller is disarmed")
@app.get("/")
def root():
    return {"name": "SCN6 Controller API", "version": "3.0.0", "running": True, "initialized": controller is not None and controller.initialized, "armed": armed, "docs": "/docs"}
@app.get("/status")
def status():
    global controller
    try:
        with controller_lock:
            if controller is None or not controller.initialized:
                return {"initialized": False, "armed": armed, "communication": None, "connected_axes": []}
            return {"initialized": True, "armed": armed, "communication": json_safe(controller.communication_info()), "connected_axes": json_safe(controller.connected_axes()), "axis_info": json_safe(controller.axis_info())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/initialize")
def initialize():
    global controller, armed
    with controller_lock:
        if controller is not None and controller.initialized:
            return {"ok": True, "initialized": True, "armed": armed, "message": "Already initialized", "connected_axes": json_safe(controller.connected_axes())}
        try:
            controller = TmbsController()
            history = controller.initialize()
            armed = False
            return {"ok": True, "initialized": True, "armed": False, "initialize_history": json_safe(history), "communication": json_safe(controller.communication_info()), "connected_axes": json_safe(controller.connected_axes()), "axis_info": json_safe(controller.axis_info())}
        except Exception as exc:
            controller = None
            armed = False
            raise api_error(exc)
@app.post("/connect")
def connect():
    return initialize()
@app.post("/disconnect")
def disconnect():
    global controller, armed
    with controller_lock:
        armed = False
        if controller is None:
            return {"ok": True, "initialized": False, "armed": False, "message": "Already disconnected"}
        try:
            result = controller.disconnect()
            return {"ok": True, "initialized": False, "armed": False, "result": json_safe(result)}
        except Exception as exc:
            raise api_error(exc)
        finally:
            controller = None
@app.get("/communication")
def communication():
    scn6 = get_controller()
    try:
        with controller_lock:
            return json_safe(scn6.communication_info())
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes")
def axes():
    scn6 = get_controller()
    try:
        with controller_lock:
            return {"connected_axes": json_safe(scn6.connected_axes()), "axis_info": json_safe(scn6.axis_info())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/axes/refresh")
def refresh_axes():
    scn6 = get_controller()
    try:
        with controller_lock:
            result = scn6.refresh_connected_axes()
            return {"ok": True, "result": json_safe(result), "connected_axes": json_safe(scn6.connected_axes()), "axis_info": json_safe(scn6.axis_info())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/arm")
def set_arm(request: ArmRequest):
    global armed
    get_controller()
    with controller_lock:
        armed = bool(request.armed)
        return {"ok": True, "armed": armed}
@app.post("/disarm")
def disarm():
    global armed
    with controller_lock:
        armed = False
        return {"ok": True, "armed": False}
@app.get("/axes/{axis}/status")
def axis_status(axis: int):
    scn6 = get_controller()
    check_axis(axis)
    try:
        with controller_lock:
            return json_safe(scn6.read_axis_status(axis))
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes/status")
def all_axis_status():
    scn6 = get_controller()
    try:
        with controller_lock:
            return json_safe(scn6.read_all_axis_status())
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes/{axis}/position")
def axis_position(axis: int):
    scn6 = get_controller()
    check_axis(axis)
    try:
        with controller_lock:
            return json_safe(scn6.read_controller_position(axis))
    except Exception as exc:
        raise api_error(exc)
@app.get("/position/{axis}")
def position(axis: int):
    return axis_position(axis)
@app.post("/move")
def move(request: MoveRequest):
    scn6 = get_controller()
    require_armed()
    check_axis(request.axis)
    try:
        with controller_lock:
            result = scn6.direct_move_absolute(request.axis, request.position)
            return {"ok": True, "axis": request.axis, "position": request.position, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/move/absolute")
def move_absolute(request: MoveRequest):
    return move(request)
@app.post("/axes/move/absolute")
def axes_move_absolute(request: MoveRequest):
    return move(request)
@app.post("/move/incremental")
def move_incremental(request: IncrementalMoveRequest):
    scn6 = get_controller()
    require_armed()
    check_axis(request.axis)
    try:
        with controller_lock:
            result = scn6.direct_move_incremental(request.axis, request.distance)
            return {"ok": True, "axis": request.axis, "distance": request.distance, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/axes/move/incremental")
def axes_move_incremental(request: IncrementalMoveRequest):
    return move_incremental(request)
@app.post("/prepare/absolute")
def prepare_absolute(request: MoveRequest):
    scn6 = get_controller()
    require_armed()
    check_axis(request.axis)
    try:
        with controller_lock:
            result = scn6.prepare_absolute_move(request.axis, request.position)
            return {"ok": True, "axis": request.axis, "position": request.position, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/incremental")
def prepare_incremental(request: IncrementalMoveRequest):
    scn6 = get_controller()
    require_armed()
    check_axis(request.axis)
    try:
        with controller_lock:
            result = scn6.prepare_incremental_move(request.axis, request.distance)
            return {"ok": True, "axis": request.axis, "distance": request.distance, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.get("/prepared")
def prepared():
    scn6 = get_controller()
    try:
        with controller_lock:
            return {"axes": json_safe(scn6.prepared_axes())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/clear")
def prepare_clear():
    scn6 = get_controller()
    try:
        with controller_lock:
            return json_safe(scn6.clear_motion_buffer())
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/start")
def prepare_start():
    scn6 = get_controller()
    require_armed()
    try:
        with controller_lock:
            result = scn6.start_prepared_moves()
            return {"ok": True, "started": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
class WaitRequest(BaseModel):
    timeout: float = Field(30.0, gt=0)
    interval: float = Field(0.05, gt=0)
@app.post("/prepare/wait")
def prepare_wait(request: WaitRequest):
    scn6 = get_controller()
    try:
        with controller_lock:
            result = scn6.wait_for_prepared_axes(timeout=request.timeout, interval=request.interval)
            return {"ok": True, "finished": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.on_event("shutdown")
def shutdown():
    global controller, armed
    with controller_lock:
        armed = False
        if controller is not None:
            try:
                if controller.initialized:
                    controller.disconnect()
            except Exception:
                pass
            controller = None
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
