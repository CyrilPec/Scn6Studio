from __future__ import annotations
import threading
from typing import Optional
from scn6_dll import TmbsController, SCN6Error, SCN6AxisError, SCN6CommunicationError, SCN6MotionError
class SCN6Controller:
    def __init__(self, dll_path: Optional[str] = None, com_port: Optional[str] = None):
        self.dll_path = dll_path
        self.com_port = com_port
        self._controller: Optional[TmbsController] = None
        self._lock = threading.RLock()
        self.armed = False
    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._controller is not None and self._controller.initialized
    @property
    def controller(self) -> TmbsController:
        with self._lock:
            if self._controller is None:
                raise SCN6Error("SCN6 controller is not initialized")
            if not self._controller.initialized:
                raise SCN6Error("SCN6 controller is not initialized")
            return self._controller
    def initialize(self):
        with self._lock:
            if self.initialized:
                return {"initialized": True, "already_initialized": True}
            kwargs = {}
            if self.dll_path is not None:
                kwargs["dll_path"] = self.dll_path
            if self.com_port is not None:
                kwargs["com_port"] = self.com_port
            self._controller = TmbsController(**kwargs)
            result = self._controller.initialize()
            self.armed = False
            return result
    def disconnect(self):
        with self._lock:
            self.armed = False
            if self._controller is not None:
                try:
                    self._controller.disconnect()
                finally:
                    self._controller = None
            return {"initialized": False, "armed": False}
    def require_armed(self):
        with self._lock:
            if not self.armed:
                raise SCN6MotionError("Controller is disarmed")
    def arm(self):
        with self._lock:
            self.controller
            self.armed = True
            return {"armed": True}
    def disarm(self):
        with self._lock:
            self.armed = False
            return {"armed": False}
    def status(self):
        with self._lock:
            controller = self.controller
            return {
                "initialized": controller.initialized,
                "armed": self.armed,
                "communication": controller.communication_info(),
                "connected_axes": controller.connected_axes(),
                "axis_info": controller.axis_info(),
            }
    def communication_info(self):
        with self._lock:
            return self.controller.communication_info()
    def connected_axes(self):
        with self._lock:
            return self.controller.connected_axes()
    def axis_info(self):
        with self._lock:
            return self.controller.axis_info()
    def refresh_connected_axes(self):
        with self._lock:
            return self.controller.refresh_connected_axes()
    def read_axis_status(self, axis: int):
        with self._lock:
            return self.controller.read_axis_status(axis)
    def read_all_axis_status(self):
        with self._lock:
            return self.controller.read_all_axis_status()
    def read_controller_position(self, axis: int):
        with self._lock:
            return self.controller.read_controller_position(axis)
    def direct_move_absolute(self, axis: int, position: int):
        with self._lock:
            self.require_armed()
            return self.controller.direct_move_absolute(axis, position)
    def direct_move_incremental(self, axis: int, distance: int):
        with self._lock:
            self.require_armed()
            return self.controller.direct_move_incremental(axis, distance)
    def prepare_absolute_move(self, axis: int, position: int):
        with self._lock:
            self.require_armed()
            return self.controller.prepare_absolute_move(axis, position)
    def prepare_incremental_move(self, axis: int, distance: int):
        with self._lock:
            self.require_armed()
            return self.controller.prepare_incremental_move(axis, distance)
    def prepared_axes(self):
        with self._lock:
            return self.controller.prepared_axes()
    def clear_motion_buffer(self):
        with self._lock:
            return self.controller.clear_motion_buffer()
    def start_prepared_moves(self):
        with self._lock:
            self.require_armed()
            return self.controller.start_prepared_moves()
    def wait_for_prepared_axes(self, timeout: float = 30.0, interval: float = 0.05):
        with self._lock:
            self.require_armed()
            return self.controller.wait_for_prepared_axes(timeout, interval)
