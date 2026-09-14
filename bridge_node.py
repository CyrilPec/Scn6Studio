"""
SCN6 Blender Bridge
===================

Blender 64-bit
      |
      | HTTP / JSON
      v
scn6_server.py
      |
      v
scn6_dll.py
      |
      v
Tmbscom.DLL
      |
      v
SCN6 controller

IMPORTANT:
- This file runs inside Blender.
- NEVER import scn6_dll here.
- Hardware access belongs to scn6_server.py.
- The trajectory node updates the latest desired position.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request


# ============================================================================
# CONFIGURATION
# ============================================================================

SERVER_PYTHON = (
    r"C:\Users\DarkLight\AppData\Local\Programs"
    r"\Python\Python312-32\python.exe"
)

SERVER_SCRIPT = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "scn6_server.py",
)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

SERVER_URL = (
    f"http://{SERVER_HOST}:{SERVER_PORT}"
)

COMMUNICATION_INTERVAL = 0.05


# ============================================================================
# BRIDGE
# ============================================================================

class SCN6Bridge:

    def __init__(self):

        self.process = None

        self.running = False
        self.connected = False
        self.initializing = False
        self.last_error = ""

        # Latest-value trajectory buffer.
        self.lock = threading.RLock()

        self.command_queue = {}
        self.active_axes = set()
        self.last_sent = {}

        self.communication_thread = None
        self.communication_running = False

    # ------------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------------

    @staticmethod
    def log(message):

        print(
            "[SCN6_BRIDGE]",
            message,
        )

    # ------------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------------

    def _http_request(
        self,
        method,
        path,
        payload=None,
        timeout=30.0,
    ):

        url = SERVER_URL + path

        data = None

        if payload is not None:

            data = json.dumps(
                payload
            ).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=data,
            method=method,
        )

        request.add_header(
            "Content-Type",
            "application/json",
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:

                body = response.read()

                if not body:
                    return {}

                return json.loads(
                    body.decode("utf-8")
                )

        except urllib.error.HTTPError as exc:

            body = exc.read()

            try:
                detail = json.loads(
                    body.decode("utf-8")
                )
            except Exception:
                detail = body.decode(
                    "utf-8",
                    errors="replace",
                )

            raise RuntimeError(
                f"SCN6 HTTP {exc.code}: {detail}"
            )

        except urllib.error.URLError as exc:

            raise RuntimeError(
                "SCN6 server is unreachable: "
                + str(exc)
            )

    # ------------------------------------------------------------------------
    # Start server
    # ------------------------------------------------------------------------

    def start(self):

        if (
            self.process is not None
            and self.process.poll() is None
        ):

            self.running = True

            self._start_communication_thread()

            return True

        if not os.path.isfile(
            SERVER_PYTHON
        ):

            raise RuntimeError(
                "32-bit Python not found:\n"
                + SERVER_PYTHON
            )

        if not os.path.isfile(
            SERVER_SCRIPT
        ):

            raise RuntimeError(
                "SCN6 server script not found:\n"
                + SERVER_SCRIPT
            )

        self.log(
            "starting SCN6 FastAPI server"
        )

        self.log(
            "python: "
            + SERVER_PYTHON
        )

        self.log(
            "server: "
            + SERVER_SCRIPT
        )

        creationflags = 0

        if os.name == "nt":

            creationflags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )

        self.process = subprocess.Popen(
            [
                SERVER_PYTHON,
                SERVER_SCRIPT,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )

        self.running = True

        threading.Thread(
            target=self._read_stderr,
            daemon=True,
        ).start()

        # Wait until FastAPI is actually available.
        deadline = (
            time.monotonic()
            + 10.0
        )

        while time.monotonic() < deadline:

            if self.process.poll() is not None:

                self.running = False

                raise RuntimeError(
                    "SCN6 FastAPI server exited immediately."
                )

            try:

                health = self._http_request(
                    "GET",
                    "/health",
                    timeout=0.5,
                )

                if health.get("ok"):

                    self.log(
                        "SCN6 FastAPI server started"
                    )

                    self._start_communication_thread()

                    return True

            except Exception:
                pass

            time.sleep(0.1)

        raise RuntimeError(
            "SCN6 FastAPI server did not become ready."
        )

    # ------------------------------------------------------------------------
    # stderr
    # ------------------------------------------------------------------------

    def _read_stderr(self):

        process = self.process

        if (
            process is None
            or process.stderr is None
        ):
            return

        try:

            for line in process.stderr:

                line = line.rstrip()

                if line:

                    print(
                        "[SCN6_SERVER]",
                        line,
                    )

        except Exception as exc:

            self.log(
                "stderr reader error: "
                + str(exc)
            )

    # ------------------------------------------------------------------------
    # Communication thread
    # ------------------------------------------------------------------------

    def _start_communication_thread(self):

        if self.communication_running:
            return

        self.communication_running = True

        self.communication_thread = (
            threading.Thread(
                target=self._communication_loop,
                daemon=True,
            )
        )

        self.communication_thread.start()

    # ------------------------------------------------------------------------
    # Latest-value trajectory
    # ------------------------------------------------------------------------

    def queue_move(
        self,
        axis,
        position,
    ):

        axis = int(axis)
        position = int(round(position))

        with self.lock:

            self.active_axes.add(axis)

            self.command_queue[
                axis
            ] = position

    def clear_queued_moves(self):

        with self.lock:

            self.command_queue.clear()
            self.active_axes.clear()

    def _communication_loop(self):

        self.log(
            "communication loop started"
        )

        while self.communication_running:

            try:

                if not self.running:

                    time.sleep(
                        COMMUNICATION_INTERVAL
                    )

                    continue

                if not self.connected:

                    time.sleep(
                        COMMUNICATION_INTERVAL
                    )

                    continue

                with self.lock:

                    commands = dict(
                        self.command_queue
                    )

                    sent = dict(
                        self.last_sent
                    )

                for axis, position in commands.items():

                    if sent.get(axis) == position:
                        continue

                    try:

                        response = self.send(
                            "move",
                            timeout=5.0,
                            axis=axis,
                            position=position,
                        )

                        result = response.get(
                            "result",
                            {},
                        )

                        if (
                            isinstance(
                                result,
                                dict,
                            )
                            and result.get(
                                "accepted",
                                False,
                            )
                        ):

                            with self.lock:

                                self.last_sent[
                                    axis
                                ] = position

                    except Exception as exc:

                        self.last_error = str(
                            exc
                        )

                        self.log(
                            "trajectory command failed: "
                            + str(exc)
                        )

                time.sleep(
                    COMMUNICATION_INTERVAL
                )

            except Exception as exc:

                self.log(
                    "communication loop error: "
                    + str(exc)
                )

                time.sleep(
                    COMMUNICATION_INTERVAL
                )

        self.log(
            "communication loop stopped"
        )

    # ------------------------------------------------------------------------
    # Generic command
    # ------------------------------------------------------------------------

    def send(
        self,
        command,
        timeout=30.0,
        **arguments,
    ):

        if not self.running:

            raise RuntimeError(
                "SCN6 server is not running."
            )

        payload = {
            "cmd": command,
            "args": arguments,
        }

        self.log(
            "SEND "
            + json.dumps(
                payload,
                separators=(",", ":"),
            )
        )

        response = self._http_request(
            "POST",
            "/command",
            payload,
            timeout=timeout,
        )

        self.log(
            "RECV "
            + json.dumps(
                response,
                separators=(",", ":"),
                default=str,
            )
        )

        if not response.get(
            "ok",
            False,
        ):

            raise RuntimeError(
                response.get(
                    "error",
                    "SCN6 server error.",
                )
            )

        return response

    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------

    def initialize(self):

        self.initializing = True
        self.last_error = ""

        try:

            if (
                self.process is None
                or self.process.poll() is not None
            ):
                self.start()

            self.log(
                "testing server communication"
            )

            self.ping()

            self.log(
                "server communication OK"
            )

            self.log(
                "connecting to SCN6 controller"
            )

            response = self.connect()

            result = response.get(
                "result",
                {},
            )

            self.connected = bool(
                result.get(
                    "connected",
                    False,
                )
            )

            if not self.connected:

                raise RuntimeError(
                    "SCN6 controller did not report connected."
                )

            self.log(
                "SCN6 controller connected"
            )

            self.log(
                "communication_state: "
                + str(
                    result.get(
                        "communication_state"
                    )
                )
            )

            self.log(
                "axes: "
                + str(
                    result.get(
                        "axes"
                    )
                )
            )

            with self.lock:
                self.last_sent.clear()

            return True

        except Exception as exc:

            self.connected = False
            self.last_error = str(exc)

            self.log(
                "initialization failed: "
                + self.last_error
            )

            return False

        finally:

            self.initializing = False

    # ------------------------------------------------------------------------
    # Public SCN6 API
    # ------------------------------------------------------------------------

    def ping(self):
        return self.send(
            "ping"
        )

    def connect(self):
        return self.send(
            "connect",
            timeout=20.0,
        )

    def disconnect(self):

        response = self.send(
            "disconnect",
            timeout=10.0,
        )

        self.connected = False

        return response

    def axes(self):
        return self.send(
            "axes"
        )

    def axis_info(self):
        return self.send(
            "axis_info"
        )

    def status(
        self,
        axis=None,
    ):

        if axis is None:
            return self.send(
                "status"
            )

        return self.send(
            "status",
            axis=int(axis),
        )

    def get_position(
        self,
        axis,
    ):

        response = self.send(
            "position",
            axis=int(axis),
            timeout=5.0,
        )

        result = response.get(
            "result",
            {},
        )

        return float(
            result.get(
                "position",
                0.0,
            )
        )

    def move(
        self,
        axis,
        position,
    ):

        return self.send(
            "move",
            axis=int(axis),
            position=int(
                round(position)
            ),
        )

    def move_inc(
        self,
        axis,
        distance,
    ):

        return self.send(
            "move_inc",
            axis=int(axis),
            distance=int(
                round(distance)
            ),
        )

    def clear(self):

        return self.send(
            "clear"
        )

    def prepare_abs(
        self,
        axis,
        position,
    ):

        return self.send(
            "prepare_abs",
            axis=int(axis),
            position=int(
                round(position)
            ),
        )

    def prepare_inc(
        self,
        axis,
        distance,
    ):

        return self.send(
            "prepare_inc",
            axis=int(axis),
            distance=int(
                round(distance)
            ),
        )

    def prepared_axes(self):

        return self.send(
            "prepared_axes"
        )

    def execute(self):

        return self.send(
            "execute",
            timeout=30.0,
        )

    def wait(
        self,
        timeout=30.0,
        interval=0.05,
    ):

        return self.send(
            "wait",
            timeout=float(timeout),
            interval=float(interval),
        )

    def stop_axis(
        self,
        axis,
    ):

        return self.send(
            "stop",
            axis=int(axis),
        )

    def stop(
        self,
        axis=None,
    ):

        if axis is not None:

            return self.stop_axis(
                axis
            )

        return self.disconnect()

    def communication(self):

        return self.send(
            "communication"
        )

    def read_svmem(
        self,
        axis,
        address,
    ):

        return self.send(
            "read_svmem",
            axis=int(axis),
            address=address,
        )

    # ------------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------------

    def shutdown(self):

        self.communication_running = False
        self.connected = False

        process = self.process

        if process is None:

            self.running = False
            return

        if process.poll() is not None:

            self.process = None
            self.running = False
            return

        try:

            self.send(
                "disconnect",
                timeout=5.0,
            )

        except Exception as exc:

            self.log(
                "normal server shutdown failed: "
                + str(exc)
            )

        try:

            process.wait(
                timeout=3.0
            )

        except subprocess.TimeoutExpired:

            self.log(
                "server did not exit; terminating"
            )

            try:

                process.terminate()

                process.wait(
                    timeout=2.0
                )

            except Exception:

                try:
                    process.kill()
                except Exception:
                    pass

        self.process = None
        self.running = False

        with self.lock:

            self.command_queue.clear()
            self.active_axes.clear()
            self.last_sent.clear()

        self.log(
            "SCN6 server stopped"
        )


# ============================================================================
# BLENDER REGISTRATION
# ============================================================================

_bridge = None


def get_bridge():

    global _bridge

    if _bridge is None:
        _bridge = SCN6Bridge()

    return _bridge


def register():

    bridge = get_bridge()

    try:

        bridge.start()

        bridge.ping()

        print(
            "[SCN6] bridge connected to "
            "FastAPI SCN6 server"
        )

    except Exception as exc:

        print(
            "[SCN6] bridge startup error:",
            exc,
        )


def unregister():

    global _bridge

    if _bridge is not None:

        try:

            _bridge.shutdown()

        except Exception as exc:

            print(
                "[SCN6] bridge shutdown error:",
                exc,
            )

        _bridge = None
