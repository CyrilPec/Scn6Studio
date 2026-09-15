import pytest
from scn6_simulated_controller import SimulatedSCN6Controller
from scn6_service import SCN6Service
def test_simulator_initialize():
    controller = SimulatedSCN6Controller()
    result = controller.initialize()
    assert result["initialized"] is True
    assert controller.initialized is True
def test_simulator_arm_and_disarm():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    result = controller.arm()
    assert result["armed"] is True
    assert controller.armed is True
    result = controller.disarm()
    assert result["armed"] is False
    assert controller.armed is False
def test_simulator_absolute_move():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    controller.arm()
    result = controller.direct_move_absolute(0, 1000)
    assert result["axis"] == 0
    assert result["position"] == 1000
    assert controller.read_controller_position(0) == 1000
def test_simulator_incremental_move():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    controller.arm()
    controller.direct_move_absolute(0, 1000)
    result = controller.direct_move_incremental(0, 250)
    assert result["axis"] == 0
    assert result["distance"] == 250
    assert result["position"] == 1250
    assert controller.read_controller_position(0) == 1250
def test_simulator_prepared_move():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    controller.arm()
    controller.prepare_absolute_move(0, 500)
    controller.prepare_incremental_move(1, 200)
    assert controller.prepared_axes() == [0, 1]
    result = controller.start_prepared_moves()
    assert result["started"] is True
    assert controller.read_controller_position(0) == 500
    assert controller.read_controller_position(1) == 200
    assert controller.prepared_axes() == []
def test_simulator_disarmed_motion_fails():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    with pytest.raises(RuntimeError, match="disarmed"):
        controller.direct_move_absolute(0, 100)
def test_simulator_invalid_axis_fails():
    controller = SimulatedSCN6Controller()
    controller.initialize()
    controller.arm()
    with pytest.raises(ValueError):
        controller.direct_move_absolute(16, 100)
def test_service_uses_simulator():
    service = SCN6Service(simulated=True)
    result = service.initialize()
    assert result["initialized"] is True
    service.arm()
    result = service.direct_move_absolute(0, 1234)
    assert result["position"] == 1234
    assert service.read_controller_position(0) == 1234
def test_service_status():
    service = SCN6Service(simulated=True)
    service.initialize()
    status = service.status()
    assert status["initialized"] is True
    assert status["armed"] is False
    assert status["communication"]["simulated"] is True
    assert len(status["connected_axes"]) == 16
