from __future__ import annotations
import threading
import time
import requests
class SCN6Bridge:
    def __init__(self):
        self.base_url="http://127.0.0.1:8000"
        self.connected=False
        self.running=False
        self.initializing=False
        self.last_error=""
        self.last_response=None
        self._lock=threading.RLock()
        self._targets={}
        self._thread=None
        self._stop_event=threading.Event()
        self.communication_interval=0.05
    def _request(self,name,args=None,timeout=2.0):
        payload={"name":name,"args":args or {}}
        response=requests.post(f"{self.base_url}/command",json=payload,timeout=timeout)
        response.raise_for_status()
        data=response.json()
        if not data.get("ok",False):
            raise RuntimeError(str(data.get("error","Unknown SCN6 server error")))
        self.last_response=data
        return data.get("result")
    def initialize(self):
        with self._lock:
            if self.connected:
                return True
            if self.initializing:
                return False
            self.initializing=True
            self.last_error=""
        try:
            self._request("ping",timeout=2.0)
            self._request("connect",timeout=10.0)
            self.connected=True
            self.running=True
            self._stop_event.clear()
            if self._thread is None or not self._thread.is_alive():
                self._thread=threading.Thread(target=self._communication_loop,name="SCN6Bridge",daemon=True)
                self._thread.start()
            return True
        except Exception as exc:
            self.connected=False
            self.running=False
            self.last_error=str(exc)
            return False
        finally:
            self.initializing=False
    def queue_move(self,axis,position):
        with self._lock:
            self._targets[int(axis)]=float(position)
    def _communication_loop(self):
        while not self._stop_event.wait(self.communication_interval):
            if not self.running or not self.connected:
                continue
            with self._lock:
                targets=dict(self._targets)
            for axis,position in targets.items():
                try:
                    self._request("move",{"axis":axis,"position":int(round(position))},timeout=1.0)
                except Exception as exc:
                    self.last_error=str(exc)
                    self.connected=False
                    self.running=False
                    break
    def stop_axis(self,axis):
        try:
            return self._request("stop",{"axis":int(axis)},timeout=2.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def stop_all(self):
        with self._lock:
            axes=list(self._targets.keys())
            self._targets.clear()
        for axis in axes:
            self.stop_axis(axis)
        return True
    def servo_on(self,axis):
        try:
            return self._request("servo_on",{"axis":int(axis)},timeout=3.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def servo_off(self,axis):
        try:
            return self._request("servo_off",{"axis":int(axis)},timeout=3.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def alarm_reset(self,axis):
        try:
            return self._request("alarm_reset",{"axis":int(axis)},timeout=3.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def get_position(self,axis):
        try:
            return self._request("position",{"axis":int(axis)},timeout=2.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def get_status(self,axis=None):
        try:
            args={} if axis is None else {"axis":int(axis)}
            return self._request("status",args,timeout=2.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def get_axes(self):
        try:
            return self._request("axes",timeout=2.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def disconnect(self):
        with self._lock:
            self.running=False
            self.connected=False
            self._stop_event.set()
            self._targets.clear()
        try:
            return self._request("disconnect",timeout=5.0)
        except Exception as exc:
            self.last_error=str(exc)
            return None
    def shutdown(self):
        try:
            self.stop_all()
        except Exception:
            pass
        self.disconnect()
_bridge=None
_bridge_lock=threading.Lock()
def get_bridge():
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge=SCN6Bridge()
        return _bridge
