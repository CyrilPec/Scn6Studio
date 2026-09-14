from __future__ import annotations
import threading
from typing import Any
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from scn6_dll import TmbsController

app = FastAPI(
    title="SCN6 Controller API",
    description="HTTP API for SCN6/TMBSCOM controller",
    version="1.0.0",
)

controller: TmbsController | None = None
lock = threading.RLock()


class MoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    position: int


class MoveIncrementRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    distance: int


class PrepareAbsoluteRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    position: int


class PrepareIncrementRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    distance: int


class WaitRequest(BaseModel):
    timeout: float = Field(30.0, gt=0)
    interval: float = Field(0.05, gt=0)


class VirtualMemoryRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    address: int


def get_controller() -> TmbsController:
    if controller is None or not controller.initialized:
        raise HTTPException(
            status_code=503,
            detail="SCN6 controller is not initialized",
        )
    return controller


@app.get("/")
def root():
    return {
        "name": "SCN6 Controller API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    connected = (
        controller is not None
        and controller.initialized
    )
    return {
        "ok": True,
        "connected": connected,
    }


@app.post("/connect")
def connect():
    global controller
    with lock:
        if controller is not None and controller.initialized:
            return {
                "ok": True,
                "connected": True,
                "already_connected": True,
            }
        try:
            controller = TmbsController()
            history = controller.initialize()
            return {
                "ok": True,
                "connected": controller.initialized,
                "initialization_history": history,
                "communication": controller.communication_info(),
                "axes": controller.connected_axes(),
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
    with lock:
        if controller is None:
            return {
                "ok": True,
                "connected": False,
            }
        try:
            result = controller.disconnect()
            return {
                "ok": True,
                "connected": False,
                "result": result,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )
        finally:
            controller = None


@app.get("/communication")
def communication():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "result": c.communication_info(),
        }


@app.get("/axes")
def axes():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "axes": c.connected_axes(),
        }


@app.get("/axes/info")
def axes_info():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "axes": c.axis_info(),
        }


@app.get("/status")
def status():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "status": c.read_all_axis_status(),
        }


@app.get("/status/{axis}")
def axis_status(axis: int):
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "status": c.read_axis_status(axis),
        }


@app.get("/position/{axis}")
def position(axis: int):
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "position": c.read_controller_position(axis),
        }


@app.post("/move")
def move(request: MoveRequest):
    with lock:
        c = get_controller()
        try:
            result = c.direct_move_absolute(
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
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.post("/move/incremental")
def move_incremental(
    request: MoveIncrementRequest,
):
    with lock:
        c = get_controller()
        try:
            result = c.direct_move_incremental(
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
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.post("/motion/clear")
def motion_clear():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "result": c.clear_motion_buffer(),
        }


@app.post("/motion/prepare/absolute")
def motion_prepare_absolute(
    request: PrepareAbsoluteRequest,
):
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "result": c.prepare_absolute_move(
                request.axis,
                request.position,
            ),
        }


@app.post("/motion/prepare/incremental")
def motion_prepare_incremental(
    request: PrepareIncrementRequest,
):
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "result": c.prepare_incremental_move(
                request.axis,
                request.distance,
            ),
        }


@app.get("/motion/prepared")
def motion_prepared():
    with lock:
        c = get_controller()
        return {
            "ok": True,
            "axes": c.prepared_axes(),
        }


@app.post("/motion/execute")
def motion_execute():
    with lock:
        c = get_controller()
        try:
            result = c.start_prepared_moves()
            return {
                "ok": True,
                "result": result,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.post("/motion/wait")
def motion_wait(request: WaitRequest):
    with lock:
        c = get_controller()
        try:
            result = c.wait_for_prepared_axes(
                timeout=request.timeout,
                interval=request.interval,
            )
            return {
                "ok": True,
                "completed": result,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.get("/memory")
def read_memory(
    axis: int,
    address: int,
):
    with lock:
        c = get_controller()
        try:
            result = c.read_virtual_memory(
                axis,
                address,
            )
            return {
                "ok": True,
                "axis": axis,
                "address": address,
                "value": result,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.post("/command")
def command(
    name: str,
    args: dict[str, Any] | None = None,
):
    args = args or {}

    commands = {
        "ping": lambda c: {"result": "pong"},
        "connect": lambda c: connect(),
        "disconnect": lambda c: disconnect(),
        "axes": lambda c: {
            "axes": c.connected_axes()
        },
        "axis_info": lambda c: {
            "axes": c.axis_info()
        },
        "status": lambda c: {
            "status": (
                c.read_all_axis_status()
                if "axis" not in args
                else c.read_axis_status(args["axis"])
            )
        },
        "position": lambda c: {
            "position": c.read_controller_position(
                args["axis"]
            )
        },
        "move": lambda c: {
            "result": c.direct_move_absolute(
                args["axis"],
                args["position"],
            )
        },
        "move_inc": lambda c: {
            "result": c.direct_move_incremental(
                args["axis"],
                args["distance"],
            )
        },
        "clear": lambda c: {
            "result": c.clear_motion_buffer()
        },
        "prepare_abs": lambda c: {
            "result": c.prepare_absolute_move(
                args["axis"],
                args["position"],
            )
        },
        "prepare_inc": lambda c: {
            "result": c.prepare_incremental_move(
                args["axis"],
                args["distance"],
            )
        },
        "prepared_axes": lambda c: {
            "axes": c.prepared_axes()
        },
        "execute": lambda c: {
            "result": c.start_prepared_moves()
        },
        "wait": lambda c: {
            "completed": c.wait_for_prepared_axes(
                args.get("timeout", 30.0),
                args.get("interval", 0.05),
            )
        },
        "communication": lambda c: {
            "result": c.communication_info()
        },
        "read_svmem": lambda c: {
            "value": c.read_virtual_memory(
                args["axis"],
                args["address"],
            )
        },
    }

    if name == "ping":
        return {"ok": True, "result": "pong"}

    if name == "connect":
        return connect()

    if name == "disconnect":
        return disconnect()

    if name not in commands:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown command: {name}",
        )

    with lock:
        c = get_controller()
        try:
            return {
                "ok": True,
                **commands[name](c),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


@app.on_event("shutdown")
def shutdown():
    global controller
    with lock:
        if controller is not None:
            try:
                controller.disconnect()
            except Exception:
                pass
            controller = None


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
