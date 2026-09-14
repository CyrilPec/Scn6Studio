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
def get_controller() -> TmbsController:
    if _controller is None or not _controller.initialized:
        raise HTTPException(503, "SCN6 controller is not initialized")
    return _controller
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
                return {"ok": True, "result": "pong"}
            if name == "connect":
                if _controller is not None and _controller.initialized:
                    return {"ok": True, "result": {"connected": True, "already_connected": True}}
                _controller = TmbsController()
                history = _controller.initialize()
                return {"ok": True, "result": {"connected": True, "initialization_history": history, "communication": _controller.communication_info(), "axes": _controller.connected_axes()}}
            if name == "disconnect":
                if _controller is None:
                    return {"ok": True, "result": {"connected": False}}
                result = _controller.disconnect()
                _controller = None
                return {"ok": True, "result": {"connected": False, "result": result}}
            c = get_controller()
            if name == "axes":
                return {"ok": True, "result": c.connected_axes()}
            if name == "axis_info":
                return {"ok": True, "result": c.axis_info()}
            if name == "communication":
                return {"ok": True, "result": c.communication_info()}
            if name == "status":
                axis = args.get("axis")
                return {"ok": True, "result": c.read_all_axis_status() if axis is None else c.read_axis_status(int(axis))}
            if name == "position":
                return {"ok": True, "result": c.read_controller_position(int(args["axis"]))}
            if name == "move":
                return {"ok": True, "result": c.direct_move_absolute(int(args["axis"]), int(args["position"]))}
            if name == "move_inc":
                return {"ok": True, "result": c.direct_move_incremental(int(args["axis"]), int(args["distance"]))}
            if name == "clear":
                return {"ok": True, "result": c.clear_motion_buffer()}
            if name == "prepare_abs":
                return {"ok": True, "result": c.prepare_absolute_move(int(args["axis"]), int(args["position"]))}
            if name == "prepare_inc":
                return {"ok": True, "result": c.prepare_incremental_move(int(args["axis"]), int(args["distance"]))}
            if name == "prepared_axes":
                return {"ok": True, "result": c.prepared_axes()}
            if name == "execute":
                return {"ok": True, "result": c.start_prepared_moves()}
            if name == "wait":
                return {"ok": True, "result": c.wait_for_prepared_axes(timeout=float(args.get("timeout", 30.0)), interval=float(args.get("interval", 0.05)))}
            if name == "memory_read":
                return {"ok": True, "result": c.read_virtual_memory(int(args["axis"]), int(args["address"]))}
            if name == "memory_write":
                return {"ok": True, "result": c.write_virtual_memory(int(args["axis"]), int(args["address"]), int(args["value"]))}
            if name == "servo_on":
                axis = int(args["axis"])
                if c.set_son is None:
                    raise RuntimeError("set_son export not present.")
                result = c.set_son(axis)
                return {"ok": True, "result": {"axis": axis, "result": result}}
            if name == "servo_off":
                axis = int(args["axis"])
                if c.set_soff is None:
                    raise RuntimeError("set_soff export not present.")
                result = c.set_soff(axis)
                return {"ok": True, "result": {"axis": axis, "result": result}}
            if name == "alarm_reset":
                axis = int(args["axis"])
                if c.reset_alarm is None:
                    raise RuntimeError("reset_alarm export not present.")
                result = c.reset_alarm(axis)
                return {"ok": True, "result": {"axis": axis, "result": result}}
            if name == "stop":
                axis = int(args["axis"])
                if c.move_jog is None:
                    raise RuntimeError("move_jog export not present.")
                result = c.move_jog(axis, 0)
                return {"ok": True, "result": {"axis": axis, "result": result}}
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
