"""
scn6_server.py

32-bit Python JSON bridge between Blender and SCN6/TMBSCOM.

Architecture
------------

    Blender (64-bit)
          |
          | JSON Lines via stdin/stdout
          v
    scn6_server.py (32-bit Python)
          |
          v
    scn6_dll.py
          |
          v
    Tmbscom.DLL
          |
          v
    SCN6 controller

IMPORTANT
---------
- Must run under 32-bit Python.
- scn6_dll.py must be importable.
- Tmbscom.DLL must be where scn6_dll.py expects it.
- stdout is ONLY the JSON protocol.
- Diagnostics go to stderr.

Example requests
----------------

{"id":1,"cmd":"ping"}
{"id":2,"cmd":"connect"}
{"id":3,"cmd":"axes"}
{"id":4,"cmd":"axis_info"}
{"id":5,"cmd":"position","axis":0}
{"id":6,"cmd":"status","axis":0}
{"id":7,"cmd":"move","axis":0,"position":10000}
{"id":8,"cmd":"move_inc","axis":0,"distance":500}
{"id":9,"cmd":"clear"}
{"id":10,"cmd":"prepare_abs","axis":0,"position":10000}
{"id":11,"cmd":"prepare_abs","axis":1,"position":20000}
{"id":12,"cmd":"prepared_axes"}
{"id":13,"cmd":"execute"}
{"id":14,"cmd":"wait","timeout":30}
{"id":15,"cmd":"stop","axis":0}
{"id":16,"cmd":"disconnect"}
{"id":17,"cmd":"exit"}

The server is intentionally thin.

Hardware/DLL behavior belongs in scn6_dll.py.
JSON/IPC behavior belongs here.
"""


from __future__ import annotations

import json
import sys
import traceback


# ---------------------------------------------------------------------------
# Import the actual hardware API
# ---------------------------------------------------------------------------

try:
    from scn6_dll import TmbsController
except Exception as exc:
    TmbsController = None
    IMPORT_ERROR = str(exc)


# ===========================================================================
# SERVER
# ===========================================================================

class SCN6Server:

    def __init__(self):
        self.controller = None
        self.running = True

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @staticmethod
    def log(message):
        """
        Diagnostics ONLY.

        Never write logs to stdout because stdout is the JSON IPC channel.
        """

        sys.stderr.write(
            "[SCN6_SERVER] "
            + str(message)
            + "\n"
        )

        sys.stderr.flush()

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------

    @staticmethod
    def send(data):
        """
        Send exactly one JSON object followed by newline.
        """

        text = json.dumps(
            data,
            separators=(",", ":"),
            default=str,
        )

        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Controller access
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self):

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

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    def disconnect(self):

        if self.controller is None:
            return {
                "connected": False,
                "already_disconnected": True,
            }

        try:

            close_tmbs = getattr(
                self.controller,
                "close_tmbs",
                None,
            )

            result = None

            if callable(close_tmbs):
                result = close_tmbs()

        finally:

            self.controller = None

        return {
            "connected": False,
            "result": result,
        }

    # ------------------------------------------------------------------
    # Axis discovery
    # ------------------------------------------------------------------

    def connected_axes(self):

        controller = self.require_controller()

        result = []

        for axis_number, axis_state in controller.axes.items():

            if axis_state.connected:
                result.append(axis_number)

        return result

    # ------------------------------------------------------------------
    # Axis information
    # ------------------------------------------------------------------

    def axis_info(self):

        controller = self.require_controller()

        result = {}

        for axis_number, axis_state in controller.axes.items():

            result[str(axis_number)] = {
                "axis": axis_number,
                "connected": bool(
                    axis_state.connected
                ),
                "commanded_position": (
                    axis_state.commanded_position
                ),
                "prepared_motion": (
                    axis_state.prepared_motion
                ),
                "prepared_value": (
                    axis_state.prepared_value
                ),
            }

        return result

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self, axis=None):

        controller = self.require_controller()

        if axis is None:
            return controller.read_all_axis_status()

        return controller.read_axis_status(
            int(axis)
        )

    # ------------------------------------------------------------------
    # Direct absolute movement
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Direct incremental movement
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Prepared motion
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Execute prepared motion
    # ------------------------------------------------------------------

    def execute_prepared(self):

        controller = self.require_controller()

        result = controller.start_prepared_moves()

        return {
            "executed": bool(result),
            "prepared_axes": (
                controller.prepared_axes()
            ),
        }

    # ------------------------------------------------------------------
    # Wait for prepared motion
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop(self, axis=None):

        controller = self.require_controller()

        """
        Do NOT invent a stop operation.

        The current DLL/API does not expose a generic emergency-stop
        operation that we have verified.

        If scn6_dll.py later gets a verified stop function, the server
        can simply forward it here.
        """

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

        result = stop_function(
            None if axis is None else int(axis)
        )

        return {
            "stopped": bool(result),
            "axis": axis,
            "result": result,
        }

    # ------------------------------------------------------------------
    # Communication information
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Raw/advanced API
    # ------------------------------------------------------------------

    def read_svmem(
        self,
        axis,
        address,
    ):

        controller = self.require_controller()

        axis = int(axis)
        address = int(address, 0) if isinstance(
            address,
            str,
        ) else int(address)

        result = controller.read_virtual_memory(
            axis,
            address,
        )

        return {
            "axis": axis,
            "address": address,
            "result": result,
        }

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def handle(self, request):

        request_id = request.get("id")
        command = request.get("cmd")

        if not command:

            self.send({
                "id": request_id,
                "ok": False,
                "error": "Missing command.",
            })

            return

        try:

            # ----------------------------------------------------------
            # ping
            # ----------------------------------------------------------

            if command == "ping":

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": "pong",
                })

            # ----------------------------------------------------------
            # connect
            # ----------------------------------------------------------

            elif command == "connect":

                result = self.connect()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # disconnect
            # ----------------------------------------------------------

            elif command == "disconnect":

                result = self.disconnect()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # axes
            # ----------------------------------------------------------

            elif command == "axes":

                result = self.connected_axes()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # axis_info
            # ----------------------------------------------------------

            elif command == "axis_info":

                result = self.axis_info()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # communication
            # ----------------------------------------------------------

            elif command == "communication":

                result = self.communication_state()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # position
            # ----------------------------------------------------------

            elif command == "position":

                axis = request["axis"]

                result = self.position(axis)

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # status
            # ----------------------------------------------------------

            elif command == "status":

                axis = request.get("axis")

                result = self.status(axis)

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # move absolute
            # ----------------------------------------------------------

            elif command == "move":

                axis = request["axis"]
                position = request["position"]

                result = self.move_absolute(
                    axis,
                    position,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # move incremental
            # ----------------------------------------------------------

            elif command == "move_inc":

                axis = request["axis"]
                distance = request["distance"]

                result = self.move_incremental(
                    axis,
                    distance,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # clear prepared motion
            # ----------------------------------------------------------

            elif command == "clear":

                result = self.clear_prepared()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepare absolute
            # ----------------------------------------------------------

            elif command == "prepare_abs":

                axis = request["axis"]
                position = request["position"]

                result = self.prepare_absolute(
                    axis,
                    position,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepare incremental
            # ----------------------------------------------------------

            elif command == "prepare_inc":

                axis = request["axis"]
                distance = request["distance"]

                result = self.prepare_incremental(
                    axis,
                    distance,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # prepared axes
            # ----------------------------------------------------------

            elif command == "prepared_axes":

                result = self.prepared_axes()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "axes": result,
                })

            # ----------------------------------------------------------
            # execute prepared
            # ----------------------------------------------------------

            elif command == "execute":

                result = self.execute_prepared()

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # wait
            # ----------------------------------------------------------

            elif command == "wait":

                timeout = request.get(
                    "timeout",
                    30.0,
                )

                interval = request.get(
                    "interval",
                    0.05,
                )

                result = self.wait_prepared(
                    timeout,
                    interval,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # stop
            # ----------------------------------------------------------

            elif command == "stop":

                result = self.stop(
                    request.get("axis")
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # raw virtual memory read
            # ----------------------------------------------------------

            elif command == "read_svmem":

                axis = request["axis"]
                address = request["address"]

                result = self.read_svmem(
                    axis,
                    address,
                )

                self.send({
                    "id": request_id,
                    "ok": True,
                    "result": result,
                })

            # ----------------------------------------------------------
            # exit
            # ----------------------------------------------------------

            elif command == "exit":

                try:
                    self.disconnect()

                finally:

                    self.send({
                        "id": request_id,
                        "ok": True,
                        "result": "bye",
                    })

                    self.running = False

            # ----------------------------------------------------------
            # unknown command
            # ----------------------------------------------------------

            else:

                self.send({
                    "id": request_id,
                    "ok": False,
                    "error": (
                        f"Unknown command: {command}"
                    ),
                })

        except Exception as exc:

            self.log(
                f"{command} failed: {exc}"
            )

            self.send({
                "id": request_id,
                "ok": False,
                "error": str(exc),
            })

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):

        self.log("starting")

        while self.running:

            line = sys.stdin.readline()

            if not line:
                break

            line = line.strip()

            if not line:
                continue

            try:

                request = json.loads(line)

            except json.JSONDecodeError as exc:

                self.send({
                    "id": None,
                    "ok": False,
                    "error": (
                        f"Invalid JSON: {exc}"
                    ),
                })

                continue

            if not isinstance(request, dict):

                self.send({
                    "id": None,
                    "ok": False,
                    "error": (
                        "Request must be a JSON object."
                    ),
                })

                continue

            self.handle(request)

        try:

            self.disconnect()

        except Exception as exc:

            self.log(
                f"disconnect failed: {exc}"
            )

        self.log("stopped")


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():

    server = SCN6Server()

    try:

        server.run()

    except KeyboardInterrupt:

        server.log(
            "keyboard interrupt"
        )

    except Exception as exc:

        server.log(
            f"fatal error: {exc}"
        )

        traceback.print_exc(
            file=sys.stderr
        )

        try:
            server.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
