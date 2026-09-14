"""
scn6_server.py

FastAPI server for the 32-bit SCN6/TMBSCOM API.

Architecture:

    Blender (64-bit)
          |
          | HTTP / JSON
          v
    scn6_server.py (32-bit Python + FastAPI)
          |
          v
    scn6_dll.py
          |
          v
    Tmbscom.DLL
          |
          v
    SCN6 controller

Hardware behavior remains in scn6_dll.py.
This file is only the API/server layer.
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from scn6_dll import TmbsController
except Exception as exc:
    TmbsController = None
    IMPORT_ERROR = str(exc)


# ============================================================================
# FASTAPI
# ============================================================================

app = FastAPI(
    title="SCN6 Controller API",
    description=(
        "HTTP API for the SCN6/TMBSCOM controller. "
        "Hardware implementation remains in scn6_dll.py."
    ),
    version="1.0.0",
)


# ============================================================================
# REQUEST MODEL
# ============================================================================

class CommandRequest(BaseModel):
    """
    Generic SCN6 command.

    This deliberately keeps the existing command vocabulary so that
    bridge_node.py does not need to understand hardware implementation.
    """

    cmd: str = Field(..., min_length=1)

    # Command arguments.
    # Examples:
    # {"axis": 0, "position": 10000}
    # {"axis": 0}
    # {"timeout": 30}
    args: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# SERVER
# ============================================================================

class SCN6Server:

    def __init__(self):
        self.controller: Optional[TmbsController] = None

        # Hardware calls should not run concurrently.
        self.lock = threading.RLock()

    # ------------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------------

    @staticmethod
    def log(message):
        sys.stderr.write(
            "[SCN6_SERVER] "
            + str(message)
            + "\n"
        )
        sys.stderr.flush()

    # ------------------------------------------------------------------------
    # Controller access
    # ------------------------------------------------------------------------

    def require_controller(self):
        if self.controller is None:
            raise RuntimeError(
                "SCN6 controller is not connected."
            )

        if not getattr(
            self.controller,
            "initialized",
            False,
        ):
            raise RuntimeError(
                "SCN6 controller is not initialized."
            )

        return self.controller

    # ------------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------------

    def connect(self):

        with self.lock:

            if self.controller is not None:

                if getattr(
                    self.controller,
                    "initialized",
                    False,
                ):
                    return {
                        "connected": True,
                        "already_connected": True,
                    }

            if TmbsController is None:
                raise RuntimeError(
                    "Could not import scn6_dll.py: "
                    + IMPORT_ERROR
                )

            self.controller = TmbsController()

            history = self.controller.initialize()

            initialized = bool(
                getattr(
                    self.controller,
                    "initialized",
                    False,
                )
            )

            if not initialized:

                try:
                    state = (
                        self.controller.communication_state()
                    )
                except Exception:
                    state = None

                raise RuntimeError(
                    "TMBSCOM initialization failed "
                    f"(state={state}, history={history})"
                )

            return {
                "connected": True,
                "already_connected": False,
                "communication_state": (
                    self.controller.communication_state()
                ),
                "axes": self.connected_axes(),
                "initialization_history": history,
            }

    # ------------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------------

    def disconnect(self):

        with self.lock:

            if self.controller is None:
                return {
                    "connected": False,
                    "already_disconnected": True,
                }

            try:

                result = self.controller.disconnect()

                return {
                    "connected": False,
                    "result": result,
                }

            finally:
                self.controller = None

    # ------------------------------------------------------------------------
    # Axis discovery
    # ------------------------------------------------------------------------

    def connected_axes(self):

        controller = self.require_controller()

        return controller.connected_axes()

    # ------------------------------------------------------------------------
    # Axis information
    # ------------------------------------------------------------------------

    def axis_info(self):

        controller = self.require_controller()

        return controller.axis_info()

    # ------------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------------

    def position(self, axis):

        controller = self.require_controller()

        axis = int(axis)

        value = controller.read_controller_position(
            axis
        )

        if isinstance(value, tuple):

            position, error = value

            return {
                "axis": axis,
                "position": position,
                "error": error,
            }

        return {
            "axis": axis,
            "position": value,
            "error": None,
        }

    # ------------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------------

    def status(self, axis=None):

        controller = self.require_controller()

        if axis is None:
            return controller.read_all_axis_status()

        return controller.read_axis_status(
            int(axis)
        )

    # ------------------------------------------------------------------------
    # Direct absolute movement
    # ------------------------------------------------------------------------

    def move_absolute(
        self,
        axis,
        position,
    ):

        controller = self.require_controller()

        axis = int(axis)
        position = int(round(position))

        result = controller.direct_move_absolute(
            axis,
            position,
        )

        return {
            "axis": axis,
            "position": position,
            "result": result,
            "accepted": bool(
                result == 1
            ),
        }

    # ------------------------------------------------------------------------
    # Direct incremental movement
    # ------------------------------------------------------------------------

    def move_incremental(
        self,
        axis,
        distance,
    ):

        controller = self.require_controller()

        axis = int(axis)
        distance = int(round(distance))

        result = controller.direct_move_incremental(
            axis,
            distance,
        )

        return {
            "axis": axis,
            "distance": distance,
            "result": result,
            "accepted": bool(
                result == 1
            ),
        }

    # ------------------------------------------------------------------------
    # Prepared motion
    # ------------------------------------------------------------------------

    def clear_prepared(self):

        controller = self.require_controller()

        controller.clear_motion_buffer()

        return {
            "cleared": True,
        }

    def prepare_absolute(
        self,
        axis,
        position,
    ):

        controller = self.require_controller()

        axis = int(axis)
        position = int(round(position))

        result = controller.prepare_absolute_move(
            axis,
            position,
        )

        return {
            "axis": axis,
            "position": position,
            "prepared": bool(result),
        }

    def prepare_incremental(
        self,
        axis,
        distance,
    ):

        controller = self.require_controller()

        axis = int(axis)
        distance = int(round(distance))

        result = controller.prepare_incremental_move(
            axis,
            distance,
        )

        return {
            "axis": axis,
            "distance": distance,
            "prepared": bool(result),
        }

    def prepared_axes(self):

        controller = self.require_controller()

        return controller.prepared_axes()

    # ------------------------------------------------------------------------
    # Execute prepared motion
    # ------------------------------------------------------------------------

    def execute_prepared(self):

        controller = self.require_controller()

        result = controller.start_prepared_moves()

        return {
            "executed": bool(result),
            "prepared_axes": (
                controller.prepared_axes()
            ),
        }

    # ------------------------------------------------------------------------
    # Wait
    # ------------------------------------------------------------------------

    def wait_prepared(
        self,
        timeout=30.0,
        interval=0.05,
    ):

        controller = self.require_controller()

        result = controller.wait_for_prepared_axes(
            timeout=float(timeout),
            interval=float(interval),
        )

        return {
            "completed": bool(result),
        }

    # ------------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------------

    def stop(self, axis=None):

        controller = self.require_controller()

        stop_function = getattr(
            controller,
            "stop",
            None,
        )

        if not callable(stop_function):

            raise RuntimeError(
                "No verified stop() operation is available "
                "in scn6_dll.py."
            )

        if axis is None:
            result = stop_function()
        else:
            result = stop_function(
                int(axis)
            )

        return {
            "stopped": bool(result),
            "axis": axis,
            "result": result,
        }

    # ------------------------------------------------------------------------
    # Communication information
    # ------------------------------------------------------------------------

    def communication_state(self):

        controller = self.require_controller()

        return {
            "state": (
                controller.communication_state()
            ),
            "baud": (
                controller.get_current_baud()
            ),
            "sio_error": (
                controller.get_sio_error()
            ),
            "com_error_log": (
                controller.get_com_errlog()
            ),
        }

    # ------------------------------------------------------------------------
    # Raw virtual memory
    # ------------------------------------------------------------------------

    def read_svmem(
        self,
        axis,
        address,
    ):

        controller = self.require_controller()

        axis = int(axis)

        if isinstance(address, str):
            address = int(address, 0)
        else:
            address = int(address)

        result = controller.read_virtual_memory(
            axis,
            address,
        )

        return {
            "axis": axis,
            "address": address,
            "result": result,
        }

    # ------------------------------------------------------------------------
    # COMMAND DISPATCH
    # ------------------------------------------------------------------------

    def handle(
        self,
        command: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:

        with self.lock:

            # --------------------------------------------------------------
            # ping
            # --------------------------------------------------------------

            if command == "ping":

                return {
                    "result": "pong",
                }

            # --------------------------------------------------------------
            # connect
            # --------------------------------------------------------------

            if command == "connect":

                return {
                    "result": self.connect(),
                }

            # --------------------------------------------------------------
            # disconnect
            # --------------------------------------------------------------

            if command == "disconnect":

                return {
                    "result": self.disconnect(),
                }

            # --------------------------------------------------------------
            # axes
            # --------------------------------------------------------------

            if command == "axes":

                return {
                    "axes": self.connected_axes(),
                }

            # --------------------------------------------------------------
            # axis_info
            # --------------------------------------------------------------

            if command == "axis_info":

                return {
                    "axes": self.axis_info(),
                }

            # --------------------------------------------------------------
            # communication
            # --------------------------------------------------------------

            if command == "communication":

                return {
                    "result": self.communication_state(),
                }

            # --------------------------------------------------------------
            # position
            # --------------------------------------------------------------

            if command == "position":

                return {
                    "result": self.position(
                        args["axis"]
                    ),
                }

            # --------------------------------------------------------------
            # status
            # --------------------------------------------------------------

            if command == "status":

                return {
                    "result": self.status(
                        args.get("axis")
                    ),
                }

            # --------------------------------------------------------------
            # move
            # --------------------------------------------------------------

            if command == "move":

                return {
                    "result": self.move_absolute(
                        args["axis"],
                        args["position"],
                    ),
                }

            # --------------------------------------------------------------
            # move_inc
            # --------------------------------------------------------------

            if command == "move_inc":

                return {
                    "result": self.move_incremental(
                        args["axis"],
                        args["distance"],
                    ),
                }

            # --------------------------------------------------------------
            # clear
            # --------------------------------------------------------------

            if command == "clear":

                return {
                    "result": self.clear_prepared(),
                }

            # --------------------------------------------------------------
            # prepare_abs
            # --------------------------------------------------------------

            if command == "prepare_abs":

                return {
                    "result": self.prepare_absolute(
                        args["axis"],
                        args["position"],
                    ),
                }

            # --------------------------------------------------------------
            # prepare_inc
            # --------------------------------------------------------------

            if command == "prepare_inc":

                return {
                    "result": self.prepare_incremental(
                        args["axis"],
                        args["distance"],
                    ),
                }

            # --------------------------------------------------------------
            # prepared_axes
            # --------------------------------------------------------------

            if command == "prepared_axes":

                return {
                    "axes": self.prepared_axes(),
                }

            # --------------------------------------------------------------
            # execute
            # --------------------------------------------------------------

            if command == "execute":

                return {
                    "result": self.execute_prepared(),
                }

            # --------------------------------------------------------------
            # wait
            # --------------------------------------------------------------

            if command == "wait":

                return {
                    "result": self.wait_prepared(
                        args.get(
                            "timeout",
                            30.0,
                        ),
                        args.get(
                            "interval",
                            0.05,
                        ),
                    ),
                }

            # --------------------------------------------------------------
            # stop
            # --------------------------------------------------------------

            if command == "stop":

                return {
                    "result": self.stop(
                        args.get("axis")
                    ),
                }

            # --------------------------------------------------------------
            # read_svmem
            # --------------------------------------------------------------

            if command == "read_svmem":

                return {
                    "result": self.read_svmem(
                        args["axis"],
                        args["address"],
                    ),
                }

            raise RuntimeError(
                f"Unknown command: {command}"
            )


server = SCN6Server()


# ============================================================================
# JSON-SAFE CONVERSION
# ============================================================================

def json_safe(value):

    if isinstance(value, bytes):
        return value.hex()

    if isinstance(value, bytearray):
        return bytes(value).hex()

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            json_safe(item)
            for item in value
        ]

    return value


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root():

    return {
        "name": "SCN6 Controller API",
        "status": "running",
        "docs": "/docs",
        "api": "/command",
    }


@app.get("/health")
def health():

    return {
        "ok": True,
        "connected": (
            server.controller is not None
            and getattr(
                server.controller,
                "initialized",
                False,
            )
        ),
    }


@app.post("/command")
def command(request: CommandRequest):

    try:

        result = server.handle(
            request.cmd,
            request.args,
        )

        return json_safe({
            "ok": True,
            **result,
        })

    except Exception as exc:

        server.log(
            f"{request.cmd} failed: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/connect")
def api_connect():

    try:

        return json_safe({
            "ok": True,
            "result": server.connect(),
        })

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/disconnect")
def api_disconnect():

    try:

        return json_safe({
            "ok": True,
            "result": server.disconnect(),
        })

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================================
# SERVER START
# ============================================================================

def main():

    server.log(
        "starting FastAPI SCN6 server"
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:

        server.log(
            "keyboard interrupt"
        )

        try:
            server.disconnect()
        except Exception:
            pass
