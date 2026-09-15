"""
SCN6 FastAPI server.
This server exposes the SCN6 API to Blender.
Run with: python scn6_server.py
Swagger: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import uvicorn
from fastapi import FastAPI, HTTPException
from scn6_api import SCN6API
from scn6_models import MoveRequest, IncrementalMoveRequest, ArmRequest, WaitRequest
from scn6_dll import SCN6Error, SCN6AxisError, SCN6CommunicationError, SCN6MotionError
app = FastAPI(title="SCN6 Controller API", description="HTTP interface between Blender and the SCN6 controller.", version="4.0.0")
api = SCN6API()
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
@app.get("/")
def root():
    try:
        status = api.status()
        initialized = status.get("initialized", False)
        armed = status.get("armed", False)
    except Exception:
        initialized = False
        armed = False
    return {"name": "SCN6 Controller API", "version": "4.0.0", "running": True, "initialized": initialized, "armed": armed, "docs": "/docs"}
@app.get("/status")
def status():
    try:
        return json_safe(api.status())
    except Exception as exc:
        raise api_error(exc)
@app.post("/initialize")
def initialize():
    try:
        result = api.initialize()
        return {"ok": True, "result": json_safe(result), "status": json_safe(api.status())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/connect")
def connect():
    return initialize()
@app.post("/disconnect")
def disconnect():
    try:
        result = api.disconnect()
        return {"ok": True, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.get("/communication")
def communication():
    try:
        return json_safe(api.communication_info())
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes")
def axes():
    try:
        return {"connected_axes": json_safe(api.connected_axes()), "axis_info": json_safe(api.axis_info())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/axes/refresh")
def refresh_axes():
    try:
        result = api.refresh_connected_axes()
        return {"ok": True, "result": json_safe(result), "connected_axes": json_safe(api.connected_axes()), "axis_info": json_safe(api.axis_info())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/arm")
def set_arm(request: ArmRequest):
    try:
        result = api.arm() if request.armed else api.disarm()
        return {"ok": True, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/disarm")
def disarm():
    try:
        return {"ok": True, "result": json_safe(api.disarm())}
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes/{axis}/status")
def axis_status(axis: int):
    check_axis(axis)
    try:
        return json_safe(api.read_axis_status(axis))
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes/status")
def all_axis_status():
    try:
        return json_safe(api.read_all_axis_status())
    except Exception as exc:
        raise api_error(exc)
@app.get("/axes/{axis}/position")
def axis_position(axis: int):
    check_axis(axis)
    try:
        return json_safe(api.read_controller_position(axis))
    except Exception as exc:
        raise api_error(exc)
@app.get("/position/{axis}")
def position(axis: int):
    return axis_position(axis)
@app.post("/move")
def move(request: MoveRequest):
    check_axis(request.axis)
    try:
        result = api.direct_move_absolute(request.axis, request.position)
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
    check_axis(request.axis)
    try:
        result = api.direct_move_incremental(request.axis, request.distance)
        return {"ok": True, "axis": request.axis, "distance": request.distance, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/axes/move/incremental")
def axes_move_incremental(request: IncrementalMoveRequest):
    return move_incremental(request)
@app.post("/prepare/absolute")
def prepare_absolute(request: MoveRequest):
    check_axis(request.axis)
    try:
        result = api.prepare_absolute_move(request.axis, request.position)
        return {"ok": True, "axis": request.axis, "position": request.position, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/incremental")
def prepare_incremental(request: IncrementalMoveRequest):
    check_axis(request.axis)
    try:
        result = api.prepare_incremental_move(request.axis, request.distance)
        return {"ok": True, "axis": request.axis, "distance": request.distance, "result": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.get("/prepared")
def prepared():
    try:
        return {"axes": json_safe(api.prepared_axes())}
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/clear")
def prepare_clear():
    try:
        return json_safe(api.clear_motion_buffer())
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/start")
def prepare_start():
    try:
        result = api.start_prepared_moves()
        return {"ok": True, "started": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.post("/prepare/wait")
def prepare_wait(request: WaitRequest):
    try:
        result = api.wait_for_prepared_axes(timeout=request.timeout, interval=request.interval)
        return {"ok": True, "finished": json_safe(result)}
    except Exception as exc:
        raise api_error(exc)
@app.on_event("shutdown")
def shutdown():
    try:
        api.disconnect()
    except Exception:
        pass
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
