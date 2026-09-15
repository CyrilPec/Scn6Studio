from __future__ import annotations
from typing import Optional
from scn6_controller import SCN6Controller
class SCN6Service:
    def __init__(self, dll_path: Optional[str] = None, com_port: Optional[str] = None):
        self.controller = SCN6Controller(dll_path=dll_path, com_port=com_port)
    def initialize(self):
        return self.controller.initialize()
    def disconnect(self):
        return self.controller.disconnect()
    def status(self):
        return self.controller.status()
    def communication_info(self):
        return self.controller.communication_info()
    def connected_axes(self):
        return self.controller.connected_axes()
    def axis_info(self):
        return self.controller.axis_info()
    def refresh_connected_axes(self):
        return self.controller.refresh_connected_axes()
    def arm(self):
        return self.controller.arm()
    def disarm(self):
        return self.controller.disarm()
    def read_axis_status(self, axis: int):
        return self.controller.read_axis_status(axis)
    def read_all_axis_status(self):
        return self.controller.read_all_axis_status()
    def read_controller_position(self, axis: int):
        return self.controller.read_controller_position(axis)
    def direct_move_absolute(self, axis: int, position: int):
        return self.controller.direct_move_absolute(axis, position)
    def direct_move_incremental(self, axis: int, distance: int):
        return self.controller.direct_move_incremental(axis, distance)
    def prepare_absolute_move(self, axis: int, position: int):
        return self.controller.prepare_absolute_move(axis, position)
    def prepare_incremental_move(self, axis: int, distance: int):
        return self.controller.prepare_incremental_move(axis, distance)
    def prepared_axes(self):
        return self.controller.prepared_axes()
    def clear_motion_buffer(self):
        return self.controller.clear_motion_buffer()
    def start_prepared_moves(self):
        return self.controller.start_prepared_moves()
    def wait_for_prepared_axes(self, timeout: float = 30.0, interval: float = 0.05):
        return self.controller.wait_for_prepared_axes(timeout, interval)
