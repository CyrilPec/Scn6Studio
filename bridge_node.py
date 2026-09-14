from __future__ import annotations
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request

SERVER_PYTHON = r"C:\Users\DarkLight\AppData\Local\Programs\Python\Python312-32\python.exe"
SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scn6_server.py")
SERVER_URL = "http://127.0.0.1:8000"
COMMUNICATION_INTERVAL = 0.05

class SCN6Bridge:
    def __init__(self):
        self.process = None
        self.running = False
        self.connected = False
        self.initializing = False
        self.last_error = ""
        self.lock = threading.RLock()
        self.send_lock = threading.Lock()
        self.command_queue = {}
        self.active_axes = set()
        self.last_sent = {}
        self.communication_thread = None
        self.communication_running = False

    @staticmethod
    def log(message):
        print("[SCN6_BRIDGE]", message)

    def _request(self, method, path, data=None, timeout=30.0):
        url = SERVER_URL + path
        body = None
        if data is not None:
            body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                detail = json.loads(raw.decode("utf-8"))
            except Exception:
                detail = raw.decode("utf-8", errors="replace")
            raise RuntimeError(f"SCN6 HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SCN6 server unavailable: {exc}")

    def start(self):
        if self.process is not None and self.process.poll() is None:
            self.running = True
            self._start_communication_thread()
            return True
        if not os.path.isfile(SERVER_PYTHON):
            raise RuntimeError("32-bit Python not found:\n" + SERVER_PYTHON)
        if not os.path.isfile(SERVER_SCRIPT):
            raise RuntimeError("SCN6 server not found:\n" + SERVER_SCRIPT)
        self.log("starting FastAPI SCN6 server")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.process = subprocess.Popen(
            [SERVER_PYTHON, SERVER_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self.running = True
        threading.Thread(target=self._read_stderr, daemon=True).start()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.running = False
                raise RuntimeError("SCN6 FastAPI server exited immediately.")
            try:
                response = self._request("GET", "/health", timeout=0.5)
                if response.get("ok"):
                    self.log("FastAPI server ready")
                    self._start_communication_thread()
                    return True
            except Exception:
                pass
            time.sleep(0.1)
        raise RuntimeError("SCN6 FastAPI server did not become ready.")

    def _read_stderr(self):
        process = self.process
        if process is None or process.stderr is None:
            return
        try:
            for line in process.stderr:
                line = line.rstrip()
                if line:
                    print("[SCN6_SERVER]", line)
        except Exception as exc:
            self.log("stderr reader error: " + str(exc))

    def _start_communication_thread(self):
        if self.communication_running:
            return
        self.communication_running = True
        self.communication_thread = threading.Thread(target=self._communication_loop, daemon=True)
        self.communication_thread.start()
        
    def communication(self):
        return self.send("communication")

    def queue_move(self, axis, position):
        axis = int(axis)
        position = int(round(position))
        with self.lock:
            self.active_axes.add(axis)
            self.command_queue[axis] = position

    def clear_queued_moves(self):
        with self.lock:
            self.command_queue.clear()
            self.active_axes.clear()

    def _communication_loop(self):
        self.log("communication loop started")
        while self.communication_running:
            try:
                if not self.running or not self.connected:
                    time.sleep(COMMUNICATION_INTERVAL)
                    continue
                with self.lock:
                    commands = dict(self.command_queue)
                    sent = dict(self.last_sent)
                for axis, position in commands.items():
                    if sent.get(axis) == position:
                        continue
                    try:
                        response = self.send("move", timeout=5.0, axis=axis, position=position)
                        result = response.get("result", {})
                        accepted = result.get("accepted", True) if isinstance(result, dict) else True
                        if accepted:
                            with self.lock:
                                self.last_sent[axis] = position
                    except Exception as exc:
                        self.last_error = str(exc)
                        self.log("trajectory command failed: " + str(exc))
                time.sleep(COMMUNICATION_INTERVAL)
            except Exception as exc:
                self.log("communication loop error: " + str(exc))
                time.sleep(COMMUNICATION_INTERVAL)
        self.log("communication loop stopped")

    def send(self, command, timeout=30.0, **arguments):
        with self.send_lock:
            if not self.running:
                raise RuntimeError("SCN6 server is not running.")
            if self.process is not None and self.process.poll() is not None:
                self.running = False
                raise RuntimeError("SCN6 server process has exited.")
            payload = {"name": command, "args": arguments}
            self.log("SEND " + json.dumps(payload, separators=(",", ":")))
            response = self._request("POST", "/command", payload, timeout)
            self.log("RECV " + json.dumps(response, separators=(",", ":"), default=str))
            if not response.get("ok", False):
                raise RuntimeError(response.get("error", response.get("detail", "SCN6 server error.")))
            return response

    def initialize(self):
        self.initializing = True
        self.last_error = ""
        try:
            if self.process is None or self.process.poll() is not None:
                self.start()
            self.log("testing server communication")
            self.ping()
            self.log("server communication OK")
            self.log("connecting to SCN6 controller")
            response = self.connect()
            result = response.get("result", {})
            self.connected = bool(result.get("connected", False))
            if not self.connected:
                raise RuntimeError("SCN6 controller did not report connected.")
            self.log("SCN6 controller connected")
            self.log("axes: " + str(result.get("axes")))
            with self.lock:
                self.last_sent.clear()
            return True
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            self.log("initialization failed: " + self.last_error)
            return False
        finally:
            self.initializing = False

    def ping(self):
        return self.send("ping")

    def connect(self):
        return self.send("connect", timeout=20.0)

    def disconnect(self):
        response = self.send("disconnect", timeout=10.0)
        self.connected = False
        return response

    def axes(self):
        return self.send("axes")

    def axis_info(self):
        return self.send("axis_info")

    def status(self, axis=None):
        return self.send("status") if axis is None else self.send("status", axis=int(axis))

    def get_position(self, axis):
        response = self.send("position", axis=int(axis), timeout=5.0)
        result = response.get("result", {})
        return float(result.get("position", 0.0))

    def move(self, axis, position):
        return self.send("move", axis=int(axis), position=int(round(position)))

    def move_inc(self, axis, distance):
        return self.send("move_inc", axis=int(axis), distance=int(round(distance)))

    def clear(self):
        return self.send("clear")

    def prepare_abs(self, axis, position):
        return self.send("prepare_abs", axis=int(axis), position=int(round(position)))

    def prepare_inc(self, axis, distance):
        return self.send("prepare_inc", axis=int(axis), distance=int(round(distance)))

    def prepared_axes(self):
        return self.send("prepared_axes")

    def execute(self):
        return self.send("execute", timeout=30.0)

    def wait(self, timeout=30.0, interval=0.05):
        return self.send("wait", timeout=float(timeout), interval=float(interval))

    def memory_read(self, axis, address):
        return self.send("memory_read", axis=int(axis), address=int(address))

    def memory_write(self, axis, address, value):
        return self.send("memory_write", axis=int(axis), address=int(address), value=int(value))

    def parameters_read(self, axis):
        return self.send("parameters_read", axis=int(axis))

    def parameters_write(self, axis, pairs):
        return self.send("parameters_write", axis=int(axis), pairs=pairs)

    def point_read(self, axis, point):
        return self.send("point_read", axis=int(axis), point=int(point))

    def point_write(self, axis, point, pairs):
        return self.send("point_write", axis=int(axis), point=int(point), pairs=pairs)

    def servo_on(self, axis):
        return self.send("servo_on", axis=int(axis))

    def servo_off(self, axis):
        return self.send("servo_off", axis=int(axis))

    def alarm_reset(self, axis):
        return self.send("alarm_reset", axis=int(axis))

    def stop_axis(self, axis):
        return self.send("stop", axis=int(axis))

    def stop(self, axis=None):
        return self.stop_axis(axis) if axis is not None else self.shutdown()

    def shutdown(self):
        self.communication_running = False
        self.connected = False
        process = self.process
        if process is None:
            self.running = False
            return
        try:
            if process.poll() is None:
                try:
                    self.send("disconnect", timeout=5.0)
                except Exception as exc:
                    self.log("disconnect failed: " + str(exc))
                try:
                    process.terminate()
                    process.wait(timeout=3.0)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
        finally:
            self.process = None
            self.running = False
            with self.lock:
                self.command_queue.clear()
                self.active_axes.clear()
                self.last_sent.clear()
        self.log("SCN6 server stopped")

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
        print("[SCN6] bridge connected to FastAPI server")
    except Exception as exc:
        print("[SCN6] bridge startup error:", exc)

def unregister():
    global _bridge
    if _bridge is not None:
        try:
            _bridge.shutdown()
        except Exception as exc:
            print("[SCN6] bridge shutdown error:", exc)
        _bridge = None
