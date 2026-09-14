from __future__ import annotations
import threading
from typing import Any
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from scn6_dll import TmbsController

app = FastAPI(title="SCN6 Controller API", version="1.0.0")
_controller: TmbsController | None = None
_lock = threading.RLock()

class CommandRequest(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)

def require_controller() -> TmbsController:
    if _controller is None or not _controller.initialized:
        raise HTTPException(503, "SCN6 controller is not initialized")
    return _controller

def ok(result: Any = None) -> dict:
    response = {"ok": True}
    if result is not None:
        response["result"] = result
    return response

@app.get("/")
def root():
    return {"name": "SCN6 Controller API", "status": "running", "docs": "/docs"}

@app.get("/health")
def health():
    return {"ok": True, "connected": _controller is not None and _controller.initialized}

@app.post("/command")
def command(request: CommandRequest):
    global _controller
    name = request.name
    args = request.args
    try:
        with _lock:
            if name == "ping":
                return ok("pong")
            if name == "connect":
                if _controller is not None and _controller.initialized:
                    return ok({"connected": True, "already_connected": True})
                _controller = TmbsController()
                history = _controller.initialize()
                return ok({
                    "connected": True,
                    "initialization_history": history,
                    "communication": _controller.communication_info(),
                    "axes": _controller.connected_axes(),
                })
            if name == "disconnect":
                if _controller is None:
                    return ok({"connected": False})
                result = _controller.disconnect()
                _controller = None
                return ok({"connected": False, "result": result})
            c = require_controller()
            if name == "axes":
                return ok(c.connected_axes())
            if name == "axis_info":
                return ok(c.axis_info())
            if name == "communication":
                return ok(c.communication_info())
            if name == "status":
                axis = args.get("axis")
                return ok(c.read_all_axis_status() if axis is None else c.read_axis_status(int(axis)))
            if name == "position":
                return ok(c.read_controller_position(int(args["axis"])))
            if name == "move":
                return ok(c.direct_move_absolute(int(args["axis"]), int(args["position"])))
            if name == "move_inc":
                return ok(c.direct_move_incremental(int(args["axis"]), int(args["distance"])))
            if name == "clear":
                return ok(c.clear_motion_buffer())
            if name == "prepare_abs":
                return ok(c.prepare_absolute_move(int(args["axis"]), int(args["position"])))
            if name == "prepare_inc":
                return ok(c.prepare_incremental_move(int(args["axis"]), int(args["distance"])))
            if name == "prepared_axes":
                return ok(c.prepared_axes())
            if name == "execute":
                return ok(c.start_prepared_moves())
            if name == "wait":
                return ok(c.wait_for_prepared_axes(float(args.get("timeout", 30.0)), float(args.get("interval", 0.05))))
            if name == "memory_read":
                return ok(c.read_virtual_memory(int(args["axis"]), int(args["address"])))
            if name == "memory_write":
                return ok(c.write_virtual_memory(int(args["axis"]), int(args["address"]), int(args["value"])))
            raise HTTPException(400, f"Unknown command: {name}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}")

@app.on_event("shutdown")
def shutdown():
    global _controller
    with _lock:
        if _controller is not None:
            try:
                _controller.disconnect()
            except Exception:
                pass
            _controller = None

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
