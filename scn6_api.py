from __future__ import annotations
from typing import Optional
from scn6_service import SCN6Service
class SCN6API:
    def __init__(self, service: Optional[SCN6Service] = None):
        self.service = service or SCN6Service()
    def initialize(self):
        return self.service.initialize()
    def disconnect(self):
        return self.service.disconnect()
    def status(self):
        return self.service.status()
    def communication_info(self):
        return self.service.communication_info()
    def connected_axes(self):
        return self.service.connected_axes()
    def axis_info(self):
        return self.service.axis_info()
    def refresh_connected_axes(self):
        return self.service.refresh_connected_axes()
    def arm(self):
        return self.service.arm()
    def disarm(self):
        return self.service.disarm()
    def read_axis_status(self, axis: int):
        return self.service.read_axis_status(axis)
    def read_all_axis_status(self):
        return self.service.read_all_axis_status()
    def read_controller_position(self, axis: int):
        return self.service.read_controller_position(axis)
    def direct_move_absolute(self, axis: int, position: int):
        return self.service.direct_move_absolute(axis, position)
    def direct_move_incremental(self, axis: int, distance: int):
        return self.service.direct_move_incremental(axis, distance)
    def prepare_absolute_move(self, axis: int, position: int):
        return self.service.prepare_absolute_move(axis, position)
    def prepare_incremental_move(self, axis: int, distance: int):
        return self.service.prepare_incremental_move(axis, distance)
    def prepared_axes(self):
        return self.service.prepared_axes()
    def clear_motion_buffer(self):
        return self.service.clear_motion_buffer()
    def start_prepared_moves(self):
        return self.service.start_prepared_moves()
    def wait_for_prepared_axes(self, timeout: float = 30.0, interval: float = 0.05):
        return self.service.wait_for_prepared_axes(timeout, interval)
