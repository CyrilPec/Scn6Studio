"""
SCN6 FastAPI server.

This is the HTTP/API layer.
Hardware-specific implementation stays in scn6_dll.py.

Run:
    python scn6_server.py

Then open:
    http://127.0.0.1:8000/docs
"""

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Keep your existing SCN6 hardware implementation here.
# Adjust this import to match the actual class/functions in scn6_dll.py.
from scn6_dll import SCN6


app = FastAPI(
    title="SCN6 Controller API",
    description="HTTP interface for the SCN6 controller",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class MoveRequest(BaseModel):
    axis: int = Field(..., ge=1)
    position: float
    speed: Optional[float] = None


class AxisRequest(BaseModel):
    axis: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Hardware instance
# ---------------------------------------------------------------------------

controller: Optional[SCN6] = None


def get_controller() -> SCN6:
    global controller

    if controller is None:
        raise HTTPException(
            status_code=503,
            detail="SCN6 controller is not connected",
        )

    return controller


# ---------------------------------------------------------------------------
# Basic API
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "SCN6 Controller API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/status")
def status():
    if controller is None:
        return {
            "connected": False,
        }

    try:
        # Adapt this to the actual status method.
        return {
            "connected": True,
            "status": controller.status(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@app.post("/connect")
def connect():
    global controller

    if controller is not None:
        return {
            "ok": True,
            "connected": True,
            "message": "Already connected",
        }

    try:
        controller = SCN6()

        # Adapt this to the actual connection method.
        controller.connect()

        return {
            "ok": True,
            "connected": True,
        }

    except Exception as exc:
        controller = None

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/disconnect")
def disconnect():
    global controller

    if controller is None:
        return {
            "ok": True,
            "connected": False,
        }

    try:
        controller.disconnect()

    finally:
        controller = None

    return {
        "ok": True,
        "connected": False,
    }


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

@app.post("/move")
def move(request: MoveRequest):
    scn6 = get_controller()

    try:
        if request.speed is None:
            result = scn6.move(
                request.axis,
                request.position,
            )
        else:
            result = scn6.move(
                request.axis,
                request.position,
                request.speed,
            )

        return {
            "ok": True,
            "axis": request.axis,
            "position": request.position,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/stop")
def stop():
    scn6 = get_controller()

    try:
        result = scn6.stop()

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

@app.get("/position/{axis}")
def position(axis: int):
    scn6 = get_controller()

    try:
        result = scn6.position(axis)

        return {
            "ok": True,
            "axis": axis,
            "position": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
