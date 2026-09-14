"""
SCN6 FastAPI server.

HTTP/API layer for TmbsController in scn6_dll.py.

Run:
    python scn6_server.py

Then open:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import threading
from typing import Optional

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


# ============================================================================
# FASTAPI
# ============================================================================

app = FastAPI(
    title="SCN6 Controller API",
    description="HTTP interface for the SCN6/TMBSCOM controller",
    version="2.0.0",
)


# ============================================================================
# HARDWARE STATE
# ============================================================================

controller: Optional[TmbsController] = None

# The DLL/controller is hardware state, so don't allow two HTTP requests
# to operate on it simultaneously.
controller_lock = threading.RLock()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class AbsoluteMoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    position: int


class IncrementalMoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    distance: int


class AxisRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)


# ============================================================================
# HELPERS
# ============================================================================

def get_controller() -> TmbsController:
    global controller

    if controller is None:
        raise HTTPException(
            status_code=503,
            detail="SCN6 controller is not initialized",
        )

    if not controller.initialized:
        raise HTTPException(
            status_code=503,
            detail="SCN6 controller is not initialized",
        )

    return controller


def api_error(exc: Exception) -> HTTPException:
    """Convert SCN6 exceptions into useful HTTP errors."""

    if isinstance(exc, SCN6AxisError):
        return HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if isinstance(exc, SCN6CommunicationError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    if isinstance(exc, SCN6MotionError):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )

    if isinstance(exc, SCN6Error):
        return HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return HTTPException(
        status_code=500,
        detail=str(exc),
    )


def json_safe_status(status: dict) -> dict:
    """
    Convert the bytes field returned by read_axis_status()
    into JSON-compatible data.
    """

    result = dict(status)

    raw = result.get("raw")

    if isinstance(raw, bytes):
        result["raw"] = list(raw)

    return result


# ============================================================================
# BASIC
# ============================================================================

@app.get("/")
def root():
    return {
        "name": "SCN6 Controller API",
        "status": "running",
        "initialized": (
            controller is not None
            and controller.initialized
        ),
        "docs": "/docs",
    }


@app.get("/status")
def status():
    global controller

    if controller is None:
        return {
            "initialized": False,
            "communication": None,
            "connected_axes": [],
        }

    try:
        with controller_lock:
            return {
                "initialized": controller.initialized,
                "communication": controller.communication_info()
                if controller.initialized
                else None,
                "connected_axes": (
                    controller.connected_axes()
                    if controller.initialized
                    else []
                ),
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# CONNECTION
# ============================================================================

@app.post("/initialize")
def initialize():
    """
    Create the TmbsController and initialize TMBSCOM.

    The default COM port / baud settings come from scn6_dll.py.
    """

    global controller

    with controller_lock:
        if controller is not None and controller.initialized:
            return {
                "ok": True,
                "initialized": True,
                "message": "Already initialized",
                "connected_axes": controller.connected_axes(),
            }

        try:
            # If an old controller exists but isn't initialized,
            # discard it and create a clean instance.
            controller = TmbsController()

            history = controller.initialize()

            return {
                "ok": True,
                "initialized": True,
                "initialize_history": history,
                "communication": controller.communication_info(),
                "connected_axes": controller.connected_axes(),
            }

        except Exception as exc:
            controller = None
            raise api_error(exc)


# Keep /connect as an alias for compatibility with the old server.
@app.post("/connect")
def connect():
    return initialize()


@app.post("/disconnect")
def disconnect():
    global controller

    with controller_lock:
        if controller is None:
            return {
                "ok": True,
                "initialized": False,
                "message": "Already disconnected",
            }

        try:
            result = controller.disconnect()

            return {
                "ok": True,
                "initialized": False,
                "result": result,
            }

        except Exception as exc:
            raise api_error(exc)

        finally:
            controller = None


# ============================================================================
# COMMUNICATION
# ============================================================================

@app.get("/communication")
def communication():
    scn6 = get_controller()

    try:
        with controller_lock:
            return scn6.communication_info()

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# AXES
# ============================================================================

@app.get("/axes")
def axes():
    """
    Return discovered/connected axes.
    """

    scn6 = get_controller()

    try:
        with controller_lock:
            return {
                "connected_axes": scn6.connected_axes(),
                "axis_info": scn6.axis_info(),
            }

    except Exception as exc:
        raise api_error(exc)


@app.post("/axes/refresh")
def refresh_axes():
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.refresh_connected_axes()

            return {
                "ok": True,
                "result": result,
                "connected_axes": scn6.connected_axes(),
                "axis_info": scn6.axis_info(),
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# AXIS STATUS
# ============================================================================

@app.get("/axes/{axis}/status")
def axis_status(axis: int):
    scn6 = get_controller()

    if axis < 0 or axis > 15:
        raise HTTPException(
            status_code=400,
            detail="Axis must be between 0 and 15 (0..F)",
        )

    try:
        with controller_lock:
            status = scn6.read_axis_status(axis)

            return json_safe_status(status)

    except Exception as exc:
        raise api_error(exc)


@app.get("/axes/status")
def all_axis_status():
    scn6 = get_controller()

    try:
        with controller_lock:
            statuses = scn6.read_all_axis_status()

            return {
                str(axis): json_safe_status(status)
                for axis, status in statuses.items()
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# POSITION
# ============================================================================

@app.get("/axes/{axis}/position")
def axis_position(axis: int):
    scn6 = get_controller()

    if axis < 0 or axis > 15:
        raise HTTPException(
            status_code=400,
            detail="Axis must be between 0 and 15 (0..F)",
        )

    try:
        with controller_lock:
            return scn6.read_controller_position(axis)

    except Exception as exc:
        raise api_error(exc)


# Keep old-style endpoint as well.
@app.get("/position/{axis}")
def position(axis: int):
    return axis_position(axis)


# ============================================================================
# MOTION - ABSOLUTE
# ============================================================================

@app.post("/axes/move/absolute")
def move_absolute(request: AbsoluteMoveRequest):
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.direct_move_absolute(
                request.axis,
                request.position,
            )

            return {
                "ok": True,
                "axis": request.axis,
                "position": request.position,
                "result": result,
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# MOTION - INCREMENTAL
# ============================================================================

@app.post("/axes/move/incremental")
def move_incremental(request: IncrementalMoveRequest):
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.direct_move_incremental(
                request.axis,
                request.distance,
            )

            return {
                "ok": True,
                "axis": request.axis,
                "distance": request.distance,
                "result": result,
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# PREPARED / MULTI-AXIS MOTION
# ============================================================================

@app.post("/axes/prepare/absolute")
def prepare_absolute(request: AbsoluteMoveRequest):
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.prepare_absolute_move(
                request.axis,
                request.position,
            )

            return {
                "ok": True,
                "axis": request.axis,
                "position": request.position,
                "prepared": result,
            }

    except Exception as exc:
        raise api_error(exc)


@app.post("/axes/prepare/incremental")
def prepare_incremental(request: IncrementalMoveRequest):
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.prepare_incremental_move(
                request.axis,
                request.distance,
            )

            return {
                "ok": True,
                "axis": request.axis,
                "distance": request.distance,
                "prepared": result,
            }

    except Exception as exc:
        raise api_error(exc)


@app.get("/axes/prepared")
def prepared_axes():
    scn6 = get_controller()

    try:
        with controller_lock:
            return {
                "axes": scn6.prepared_axes(),
            }

    except Exception as exc:
        raise api_error(exc)


@app.post("/axes/prepare/clear")
def clear_prepared():
    scn6 = get_controller()

    try:
        with controller_lock:
            return scn6.clear_motion_buffer()

    except Exception as exc:
        raise api_error(exc)


@app.post("/axes/prepare/start")
def start_prepared():
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.start_prepared_moves()

            return {
                "ok": True,
                "started": result,
            }

    except Exception as exc:
        raise api_error(exc)


class WaitRequest(BaseModel):
    timeout: float = Field(30.0, gt=0)
    interval: float = Field(0.05, gt=0)


@app.post("/axes/prepare/wait")
def wait_prepared(request: WaitRequest):
    scn6 = get_controller()

    try:
        with controller_lock:
            result = scn6.wait_for_prepared_axes(
                timeout=request.timeout,
                interval=request.interval,
            )

            return {
                "ok": True,
                "finished": result,
            }

    except Exception as exc:
        raise api_error(exc)


# ============================================================================
# SERVER SHUTDOWN
# ============================================================================

@app.on_event("shutdown")
def shutdown():
    global controller

    with controller_lock:
        if controller is not None:
            try:
                if controller.initialized:
                    controller.disconnect()
            except Exception:
                pass
            finally:
                controller = None


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
