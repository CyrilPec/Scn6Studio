from **future** import annotations
import threading
import time
from typing import Dict, List
class SimulatedSCN6Controller:
def **init**(self, axis_count: int = 16):
self.axis_count = axis_count
self._lock = threading.RLock()
self._initialized = False
self.armed = False
self._positions: Dict[int, int] = {axis: 0 for axis in range(axis_count)}
self._prepared: Dict[int, int] = {}
@property
def initialized(self) -> bool:
with self._lock:
return self._initialized
def _check_axis(self, axis: int) -> None:
if axis < 0 or axis >= self.axis_count:
raise ValueError(f"Axis must be between 0 and {self.axis_count - 1}")
def _require_initialized(self) -> None:
if not self._initialized:
raise RuntimeError("SCN6 controller is not initialized")
def _require_armed(self) -> None:
self._require_initialized()
if not self.armed:
raise RuntimeError("Controller is disarmed")
def initialize(self):
with self._lock:
if self._initialized:
return {"initialized": True, "already_initialized": True, "simulated": True}
self._initialized = True
self.armed = False
self._positions = {axis: 0 for axis in range(self.axis_count)}
self._prepared.clear()
return {"initialized": True, "already_initialized": False, "simulated": True}
def disconnect(self):
with self._lock:
self.armed = False
self._initialized = False
self._prepared.clear()
return {"initialized": False, "armed": False, "simulated": True}
def arm(self):
with self._lock:
self._require_initialized()
self.armed = True
return {"armed": True, "simulated": True}
def disarm(self):
with self._lock:
self.armed = False
return {"armed": False, "simulated": True}
def status(self):
with self._lock:
self._require_initialized()
return {
"initialized": self._initialized,
"armed": self.armed,
"communication": self.communication_info(),
"connected_axes": self.connected_axes(),
"axis_info": self.axis_info(),
}
def communication_info(self):
with self._lock:
self._require_initialized()
return {
"simulated": True,
"connected": True,
"transport": "simulation",
}
def connected_axes(self):
with self._lock:
self._require_initialized()
return list(range(self.axis_count))
def axis_info(self):
with self._lock:
self._require_initialized()
return {
axis: {
"axis": axis,
"connected": True,
"position": self._positions[axis],
"simulated": True,
}
for axis in range(self.axis_count)
}
def refresh_connected_axes(self):
with self._lock:
self._require_initialized()
return {
"connected_axes": self.connected_axes(),
"simulated": True,
}
def read_axis_status(self, axis: int):
with self._lock:
self._check_axis(axis)
self._require_initialized()
return {
"axis": axis,
"position": self._positions[axis],
"servo": self.armed,
"run": False,
"alarm": False,
"origin": self._positions[axis] == 0,
"simulated": True,
}
def read_all_axis_status(self):
with self._lock:
self._require_initialized()
return {
axis: self.read_axis_status(axis)
for axis in range(self.axis_count)
}
def read_controller_position(self, axis: int):
with self._lock:
self._check_axis(axis)
self._require_initialized()
return self._positions[axis]
def direct_move_absolute(self, axis: int, position: int):
with self._lock:
self._check_axis(axis)
self._require_armed()
self._positions[axis] = position
return {
"axis": axis,
"position": position,
"simulated": True,
}
def direct_move_incremental(self, axis: int, distance: int):
with self._lock:
self._check_axis(axis)
self._require_armed()
self._positions[axis] += distance
return {
"axis": axis,
"position": self._positions[axis],
"distance": distance,
"simulated": True,
}
def prepare_absolute_move(self, axis: int, position: int):
with self._lock:
self._check_axis(axis)
self._require_armed()
self._prepared[axis] = position
return {
"axis": axis,
"position": position,
"prepared": True,
"simulated": True,
}
def prepare_incremental_move(self, axis: int, distance: int):
with self._lock:
self._check_axis(axis)
self._require_armed()
self._prepared[axis] = self._positions[axis] + distance
return {
"axis": axis,
"position": self._prepared[axis],
"distance": distance,
"prepared": True,
"simulated": True,
}
def prepared_axes(self) -> List[int]:
with self._lock:
return list(self._prepared.keys())
def clear_motion_buffer(self):
with self._lock:
count = len(self._prepared)
self._prepared.clear()
return {
"cleared": True,
"axes": count,
"simulated": True,
}
def start_prepared_moves(self):
with self._lock:
self._require_armed()
moves = {}
for axis, position in self._prepared.items():
self._positions[axis] = position
moves[axis] = position
self._prepared.clear()
return {
"started": True,
"moves": moves,
"simulated": True,
}
def wait_for_prepared_axes(self, timeout: float = 30.0, interval: float = 0.05):
with self._lock:
self._require_armed()
start = time.monotonic()
while self._prepared:
if time.monotonic() - start >= timeout:
return {
"finished": False,
"timeout": True,
"prepared_axes": self.prepared_axes(),
"simulated": True,
}
time.sleep(interval)
return {
"finished": True,
"timeout": False,
"prepared_axes": [],
"simulated": True,
}
