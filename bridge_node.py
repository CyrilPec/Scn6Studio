"""
SCN6 Blender Bridge
===================
Blender 64-bit bridge for the external 32-bit SCN6 server.
Architecture:
    Blender
       |
       | latest-value command buffer
       v
    bridge_node.py
       |
       | JSON Lines
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
IMPORTANT:
- This file runs inside Blender.
- NEVER import scn6_dll here.
- Hardware access belongs to scn6_server.py.
- The trajectory node only updates the latest desired position.
- This bridge sends the latest position at a controlled rate.
"""
from __future__ import annotations
import json
import os
import queue
import subprocess
import threading
import time
SERVER_PYTHON=r"C:\Users\DarkLight\AppData\Local\Programs\Python\Python312-32\python.exe"
SERVER_SCRIPT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"scn6_server.py")
COMMUNICATION_INTERVAL=0.05
class SCN6Bridge:
    def __init__(self):
        self.process=None
        self.running=False
        self.request_id=0
        self.responses=queue.Queue()
        self.reader_thread=None
        self.stderr_thread=None
        self.lock=threading.RLock()
        self.send_lock=threading.Lock()
        self.connected=False
        self.initializing=False
        self.last_error=""
        self.command_queue={}
        self.active_axes=set()
        self.last_sent={}
        self.communication_thread=None
        self.communication_running=False
    @staticmethod
    def log(message):
        print("[SCN6_BRIDGE]",message)
    def start(self):
        if self.process is not None and self.process.poll() is None:
            self.running=True
            self._start_communication_thread()
            return True
        if not os.path.isfile(SERVER_PYTHON):
            raise RuntimeError("32-bit Python not found:\n"+SERVER_PYTHON)
        if not os.path.isfile(SERVER_SCRIPT):
            raise RuntimeError("SCN6 server script not found:\n"+SERVER_SCRIPT)
        self.log("starting SCN6 server")
        self.log("python: "+SERVER_PYTHON)
        self.log("server: "+SERVER_SCRIPT)
        creationflags=0
        if os.name=="nt":
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        self.process=subprocess.Popen(
            [SERVER_PYTHON,SERVER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self.running=True
        self.reader_thread=threading.Thread(target=self._read_stdout,daemon=True)
        self.reader_thread.start()
        self.stderr_thread=threading.Thread(target=self._read_stderr,daemon=True)
        self.stderr_thread.start()
        self._start_communication_thread()
        time.sleep(0.1)
        if self.process.poll() is not None:
            self.running=False
            raise RuntimeError("SCN6 server exited immediately.")
        self.log("SCN6 server started")
        return True
    def _start_communication_thread(self):
        if self.communication_running:
            return
        self.communication_running=True
        self.communication_thread=threading.Thread(target=self._communication_loop,daemon=True)
        self.communication_thread.start()
    def _read_stdout(self):
        process=self.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                line=line.strip()
                if not line:
                    continue
                try:
                    self.responses.put(json.loads(line))
                except json.JSONDecodeError as exc:
                    self.log("invalid JSON from server: "+str(exc))
                    self.log("raw: "+line)
        except Exception as exc:
            self.log("stdout reader error: "+str(exc))
    def _read_stderr(self):
        process=self.process
        if process is None or process.stderr is None:
            return
        try:
            for line in process.stderr:
                line=line.rstrip()
                if line:
                    print("[SCN6_SERVER]",line)
        except Exception as exc:
            self.log("stderr reader error: "+str(exc))
    def queue_move(self,axis,position):
        axis=int(axis)
        position=int(round(position))
        with self.lock:
            self.active_axes.add(axis)
            self.command_queue[axis]=position
    def clear_queued_moves(self):
        with self.lock:
            self.command_queue.clear()
            self.active_axes.clear()
    def _communication_loop(self):
        self.log("communication loop started")
        while self.communication_running:
            try:
                if not self.running or self.process is None or self.process.poll() is not None:
                    time.sleep(COMMUNICATION_INTERVAL)
                    continue
                if not self.connected:
                    time.sleep(COMMUNICATION_INTERVAL)
                    continue
                with self.lock:
                    commands=dict(self.command_queue)
                    sent=dict(self.last_sent)
                for axis,position in commands.items():
                    if sent.get(axis)==position:
                        continue
                    try:
                        response=self.send("move",timeout=5.0,axis=axis,position=position)
                        result=response.get("result",{})
                        if isinstance(result,dict) and result.get("accepted",False):
                            with self.lock:
                                self.last_sent[axis]=position
                    except Exception as exc:
                        self.last_error=str(exc)
                        self.log("trajectory command failed: "+str(exc))
                time.sleep(COMMUNICATION_INTERVAL)
            except Exception as exc:
                self.log("communication loop error: "+str(exc))
                time.sleep(COMMUNICATION_INTERVAL)
        self.log("communication loop stopped")
    def send(self,command,timeout=30.0,**arguments):
        with self.send_lock:
            process=self.process
            if process is None:
                raise RuntimeError("SCN6 server is not running.")
            if process.poll() is not None:
                raise RuntimeError("SCN6 server process has exited.")
            with self.lock:
                self.request_id+=1
                request_id=self.request_id
            request={"id":request_id,"cmd":command}
            request.update(arguments)
            text=json.dumps(request,separators=(",",":"))
            self.log("SEND "+text)
            try:
                process.stdin.write(text+"\n")
                process.stdin.flush()
            except Exception as exc:
                raise RuntimeError("Failed to send request: "+str(exc))
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                remaining=deadline-time.monotonic()
                try:
                    response=self.responses.get(timeout=min(remaining,0.1))
                except queue.Empty:
                    if process.poll() is not None:
                        raise RuntimeError("SCN6 server exited while waiting for response.")
                    continue
                if response.get("id")!=request_id:
                    self.responses.put(response)
                    continue
                self.log("RECV "+json.dumps(response,separators=(",",":"),default=str))
                if not response.get("ok",False):
                    raise RuntimeError(response.get("error","SCN6 server error."))
                return response
            raise TimeoutError("SCN6 server response timeout for command '"+command+"'.")
    def initialize(self):
        self.initializing=True
        self.last_error=""
        try:
            if self.process is None or self.process.poll() is not None:
                self.start()
            self.log("testing server communication")
            self.ping()
            self.log("server communication OK")
            self.log("connecting to SCN6 controller")
            response=self.connect()
            result=response.get("result",{})
            self.connected=bool(result.get("connected",False))
            if not self.connected:
                raise RuntimeError("SCN6 controller did not report connected.")
            self.log("SCN6 controller connected")
            self.log("communication_state: "+str(result.get("communication_state")))
            self.log("axes: "+str(result.get("axes")))
            with self.lock:
                self.last_sent.clear()
            return True
        except Exception as exc:
            self.connected=False
            self.last_error=str(exc)
            self.log("initialization failed: "+self.last_error)
            return False
        finally:
            self.initializing=False
    def ping(self):
        return self.send("ping")
    def connect(self):
        return self.send("connect",timeout=20.0)
    def disconnect(self):
        response=self.send("disconnect",timeout=10.0)
        self.connected=False
        return response
    def axes(self):
        return self.send("axes")
    def axis_info(self):
        return self.send("axis_info")
    def status(self,axis=None):
        if axis is None:
            return self.send("status")
        return self.send("status",axis=int(axis))
    def get_position(self,axis):
        response=self.send("position",axis=int(axis),timeout=5.0)
        result=response.get("result",{})
        return float(result.get("position",0.0))
    def move(self,axis,position):
        return self.send("move",axis=int(axis),position=int(round(position)))
    def move_inc(self,axis,distance):
        return self.send("move_inc",axis=int(axis),distance=int(round(distance)))
    def clear(self):
        return self.send("clear")
    def prepare_abs(self,axis,position):
        return self.send("prepare_abs",axis=int(axis),position=int(round(position)))
    def prepare_inc(self,axis,distance):
        return self.send("prepare_inc",axis=int(axis),distance=int(round(distance)))
    def prepared_axes(self):
        return self.send("prepared_axes")
    def execute(self):
        return self.send("execute",timeout=30.0)
    def wait(self,timeout=30.0,interval=0.05):
        return self.send("wait",timeout=float(timeout),interval=float(interval))
    def memory_read(self,axis,address):
        return self.send("memory_read",axis=int(axis),address=int(address))
    def memory_write(self,axis,address,value):
        return self.send("memory_write",axis=int(axis),address=int(address),value=int(value))
    def parameters_read(self,axis):
        return self.send("parameters_read",axis=int(axis))
    def parameters_write(self,axis,pairs):
        return self.send("parameters_write",axis=int(axis),pairs=pairs)
    def point_read(self,axis,point):
        return self.send("point_read",axis=int(axis),point=int(point))
    def point_write(self,axis,point,pairs):
        return self.send("point_write",axis=int(axis),point=int(point),pairs=pairs)
    def servo_on(self,axis):
        return self.send("servo_on",axis=int(axis))
    def servo_off(self,axis):
        return self.send("servo_off",axis=int(axis))
    def alarm_reset(self,axis):
        return self.send("alarm_reset",axis=int(axis))
    def stop_axis(self,axis):
        return self.send("stop",axis=int(axis))
    def stop(self,axis=None):
        if axis is not None:
            return self.stop_axis(axis)
        return self.shutdown()
    def shutdown(self):
        self.communication_running=False
        self.connected=False
        process=self.process
        if process is None:
            self.running=False
            return
        if process.poll() is not None:
            self.process=None
            self.running=False
            return
        try:
            self.send("exit",timeout=3.0)
        except Exception as exc:
            self.log("normal server shutdown failed: "+str(exc))
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self.log("server did not exit; terminating")
            try:
                process.terminate()
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self.process=None
        self.running=False
        with self.lock:
            self.command_queue.clear()
            self.active_axes.clear()
            self.last_sent.clear()
        self.log("SCN6 server stopped")
_bridge=None
def get_bridge():
    global _bridge
    if _bridge is None:
        _bridge=SCN6Bridge()
    return _bridge
def register():
    bridge=get_bridge()
    try:
        bridge.start()
        bridge.ping()
        print("[SCN6] bridge connected to 32-bit SCN6 server")
    except Exception as exc:
        print("[SCN6] bridge startup error:",exc)
def unregister():
    global _bridge
    if _bridge is not None:
        try:
            _bridge.shutdown()
        except Exception as exc:
            print("[SCN6] bridge shutdown error:",exc)
        _bridge=None
