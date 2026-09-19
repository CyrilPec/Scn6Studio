"""
scn6_dll.py
SCN6 / TMBSCOM.DLL Python API

32-bit Python required.

Architecture:

    Blender (64-bit)
          |
          | JSON Lines
          v
    scn6_server.py
          |
          v
    TmbsController
          |
          v
    Tmbscom.DLL
          |
          v
    SCN6 controller

This module is the hardware/API layer.

IMPORTANT:
- Do not put CLI code here.
- Do not write protocol data to stdout here.
- Hardware diagnostics should be returned as API errors/results.
- Tmbscom.DLL must be available beside this file or where configured.
"""

from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

DLL_NAME = "Tmbscom.DLL"

COM_PORT = "COM6"
BAUD_CODE = 0x14       # TMBS_BAUD_115200
NRT = 2
RESET = False
AUTOMATIC = False

MAX_AXIS_COUNT = 16
AXIS_NUMBERS = tuple(range(MAX_AXIS_COUNT))


# ============================================================================
# DOCUMENTED VIRTUAL MEMORY
# ============================================================================

PNOW_MEMORY_ADDRESS = 0x7400
VM_VNOW = 0x7401
VM_STAT = 0x7403
VM_ALRM = 0x7404
VM_STA2 = 0x7408
VM_PNTM = 0x7415


# ============================================================================
# EXECUTION DATA AREA
# ============================================================================

EXECUTION_DATA_BANK_BASE_ADDRESS = 0x7800

EXECUTION_PROFILE_ADDRESSES = {
    0x7800: "CNTM",
    0x7801: "CNTL",
    0x7802: "LIMM",
    0x7803: "LIML",
    0x7804: "ZONM",
    0x7805: "ZONL",
    0x7806: "ORG",
    0x7807: "PHSP",
    0x7808: "FPIO",
    0x7809: "BRSL",
    0x780A: "OVCM",
    0x780B: "OACC",
    0x780C: "RTIM",
    0x780D: "INP",
    0x780E: "VCMD",
    0x780F: "ACMD",
    0x7810: "SPOW",
    0x7811: "DPOW",
    0x7812: "PLG0",
    0x7813: "MXAC",
    0x7814: "CPAC",
    0x7815: "PSWT",
    0x7818: "ZRMK",
    0x7819: "ODPW",
    0x781A: "OTIM",
    0x781B: "PLG1",
    0x781C: "PLJL",
    0x781D: "FLSL",
    0x781E: "FLFC",
}


# ============================================================================
# TMBSCOM RETURN VALUES
# ============================================================================

SIO_ERROR = 0
SIO_DONE = 1

TMBS_STATE_NAMES = {
    -1: "SIO_COMUSED",
    -2: "SIO_TIMEOUT",
    -5: "SIO_INVALID_PARAM",
    -6: "SIO_NOTSUPORT_TO",
    -8: "SIO_NOTSUPORT_BAUD",
    -9: "SIO_NOTSUPORT_PARA",
    -10: "SIO_NO_CONFIGFILE",
    -12: "TMBS_INIT_ERROR / COM OPEN FAILURE",
    2: "TMBS_INIT_ERROR",
    3: "TMBS_OPENING",
    4: "TMBS_RUNNING",
}


# ============================================================================
# EXCEPTIONS
# ============================================================================

class SCN6Error(Exception):
    """Base SCN6 API exception."""


class SCN6NotInitializedError(SCN6Error):
    """Controller has not been initialized."""


class SCN6AxisError(SCN6Error):
    """Invalid or unavailable axis."""


class SCN6CommunicationError(SCN6Error):
    """TMBSCOM communication failure."""


class SCN6MotionError(SCN6Error):
    """Motion command rejected or failed."""


# ============================================================================
# AXIS STATE
# ============================================================================

@dataclass
class AxisState:
    axis_number: int
    connected: bool = False

    # Local bookkeeping only.
    # Actual controller position is read from PNOW.
    commanded_position: Optional[int] = None

    # Locally prepared motion.
    prepared_motion: Optional[str] = None
    prepared_value: Optional[int] = None


# ============================================================================
# COMPACK
# ============================================================================

class COMPACK(ctypes.Structure):
    _fields_ = [
        ("address", ctypes.c_int * 32),
        ("data", ctypes.c_long * 32),
    ]


def create_empty_compack() -> COMPACK:
    packet = COMPACK()

    for index in range(32):
        packet.address[index] = -1
        packet.data[index] = 0

    return packet


def create_compack(address_data_pairs) -> COMPACK:
    if len(address_data_pairs) > 32:
        raise ValueError("maximum is 32 address/data pairs")

    packet = create_empty_compack()

    for index, (address, data) in enumerate(address_data_pairs):
        packet.address[index] = int(address)
        packet.data[index] = int(data)

    return packet


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def raw_hex(buffer) -> str:
    return " ".join(f"{byte:02X}" for byte in bytes(buffer))


def status_name(value: int) -> str:
    return TMBS_STATE_NAMES.get(
        value,
        f"UNKNOWN({value})",
    )


def axis_name(axis_number: int) -> str:
    return format(axis_number, "X")


# ============================================================================
# MAIN API
# ============================================================================

class TmbsController:

    def __init__(
        self,
        dll_path: Optional[str] = None,
        com_port: str = COM_PORT,
        baud_code: int = BAUD_CODE,
        nrt: int = NRT,
        reset: bool = RESET,
        automatic: bool = AUTOMATIC,
    ):
        if dll_path is None:
            dll_path = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                DLL_NAME,
            )

        self.dll_path = dll_path
        self.com_port = com_port
        self.baud_code = baud_code
        self.nrt = nrt
        self.reset = reset
        self.automatic = automatic

        self.dll = ctypes.WinDLL(self.dll_path)

        self.initialized = False

        self.axes_info = [-1] * MAX_AXIS_COUNT

        self.axes = {
            axis_number: AxisState(axis_number)
            for axis_number in AXIS_NUMBERS
        }

        self.last_status = {}

        self.bind_dll_functions()


    # ========================================================================
    # DLL BINDINGS
    # ========================================================================

    def bind_dll_functions(self):

        controller = self.dll

        # --------------------------------------------------------------------
        # Communication
        # --------------------------------------------------------------------

        self.init_tmbs_config = controller.init_tmbs_config
        self.init_tmbs_config.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self.init_tmbs_config.restype = ctypes.c_int

        self.init_tmbs = controller.init_tmbs
        self.init_tmbs.argtypes = []
        self.init_tmbs.restype = ctypes.c_int

        self.init_sio = controller.init_sio
        self.init_sio.argtypes = []
        self.init_sio.restype = ctypes.c_int

        self.init_sio_tbus = getattr(
            controller,
            "init_sio_tbus",
            None,
        )

        if self.init_sio_tbus:
            self.init_sio_tbus.argtypes = []
            self.init_sio_tbus.restype = ctypes.c_int

        self.close_tmbs = controller.close_tmbs
        self.close_tmbs.argtypes = []
        self.close_tmbs.restype = ctypes.c_int

        self.reopen_tmbs = getattr(
            controller,
            "reopen_tmbs",
            None,
        )

        if self.reopen_tmbs:
            self.reopen_tmbs.argtypes = []
            self.reopen_tmbs.restype = ctypes.c_int

        self.get_tmbs_state = controller.get_tmbs_state
        self.get_tmbs_state.argtypes = []
        self.get_tmbs_state.restype = ctypes.c_int

        self.get_current_baud = controller.get_current_baud
        self.get_current_baud.argtypes = []
        self.get_current_baud.restype = ctypes.c_int

        self.get_sio_error = controller.get_sio_error
        self.get_sio_error.argtypes = []
        self.get_sio_error.restype = ctypes.c_int

        self.get_com_errlog = controller.get_com_errlog
        self.get_com_errlog.argtypes = []
        self.get_com_errlog.restype = ctypes.c_int

        self.get_axes = controller.get_axes
        self.get_axes.argtypes = [
            ctypes.POINTER(ctypes.c_ushort)
        ]
        self.get_axes.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Motion
        # --------------------------------------------------------------------

        self.move_point = getattr(
            controller,
            "move_point",
            None,
        )

        if self.move_point:
            self.move_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_point.restype = ctypes.c_int

        self.move_abs = getattr(
            controller,
            "move_abs",
            None,
        )

        if self.move_abs:
            self.move_abs.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_abs.restype = ctypes.c_int

        self.move_inc = getattr(
            controller,
            "move_inc",
            None,
        )

        if self.move_inc:
            self.move_inc.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_inc.restype = ctypes.c_int

        self.move_org = getattr(
            controller,
            "move_org",
            None,
        )

        if self.move_org:
            self.move_org.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_org.restype = None

        self.move_rotate = getattr(
            controller,
            "move_rotate",
            None,
        )

        if self.move_rotate:
            self.move_rotate.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.move_rotate.restype = ctypes.c_int

        self.move_jog = getattr(
            controller,
            "move_jog",
            None,
        )

        if self.move_jog:
            self.move_jog.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.move_jog.restype = ctypes.c_int

        self.follow_position = getattr(
            controller,
            "follow_position",
            None,
        )

        if self.follow_position:
            self.follow_position.argtypes = [
                ctypes.c_int
            ]
            self.follow_position.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Status
        # --------------------------------------------------------------------

        self.check_pfin = getattr(
            controller,
            "check_pfin",
            None,
        )

        self.check_status = getattr(
            controller,
            "check_status",
            None,
        )

        self.check_run = getattr(
            controller,
            "check_run",
            None,
        )

        self.check_son = getattr(
            controller,
            "check_son",
            None,
        )

        self.check_alrm = getattr(
            controller,
            "check_alrm",
            None,
        )

        self.check_org = getattr(
            controller,
            "check_org",
            None,
        )

        for dll_function in (
            self.check_pfin,
            self.check_status,
            self.check_run,
            self.check_son,
            self.check_alrm,
            self.check_org,
        ):
            if dll_function:
                dll_function.argtypes = [
                    ctypes.c_int
                ]
                dll_function.restype = ctypes.c_int

        self.get_status = controller.get_status
        self.get_status.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        self.get_status.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Servo / state-changing functions
        # --------------------------------------------------------------------

        self.write_position = getattr(
            controller,
            "write_position",
            None,
        )

        if self.write_position:
            self.write_position.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_position.restype = ctypes.c_int

        self.set_son = getattr(
            controller,
            "set_son",
            None,
        )

        if self.set_son:
            self.set_son.argtypes = [
                ctypes.c_int
            ]
            self.set_son.restype = ctypes.c_int

        self.set_soff = getattr(
            controller,
            "set_soff",
            None,
        )

        if self.set_soff:
            self.set_soff.argtypes = [
                ctypes.c_int
            ]
            self.set_soff.restype = ctypes.c_int

        self.reset_alarm = getattr(
            controller,
            "reset_alarm",
            None,
        )

        if self.reset_alarm:
            self.reset_alarm.argtypes = [
                ctypes.c_int
            ]
            self.reset_alarm.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Execution-area parameter functions
        # --------------------------------------------------------------------

        self.write_velocity = getattr(
            controller,
            "write_velocity",
            None,
        )

        if self.write_velocity:
            self.write_velocity.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.write_velocity.restype = ctypes.c_int

        self.write_inpos = getattr(
            controller,
            "write_inpos",
            None,
        )

        if self.write_inpos:
            self.write_inpos.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_inpos.restype = ctypes.c_int

        self.write_fzone = getattr(
            controller,
            "write_fzone",
            None,
        )

        if self.write_fzone:
            self.write_fzone.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_fzone.restype = ctypes.c_int

        self.write_rzone = getattr(
            controller,
            "write_rzone",
            None,
        )

        if self.write_rzone:
            self.write_rzone.argtypes = [
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_rzone.restype = ctypes.c_int

        self.select_svparm = getattr(
            controller,
            "select_svparm",
            None,
        )

        if self.select_svparm:
            self.select_svparm.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.select_svparm.restype = ctypes.c_int

        self.write_trqlim = getattr(
            controller,
            "write_trqlim",
            None,
        )

        if self.write_trqlim:
            self.write_trqlim.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            self.write_trqlim.restype = ctypes.c_int

        self.reset_memory = getattr(
            controller,
            "reset_memory",
            None,
        )

        if self.reset_memory:
            self.reset_memory.argtypes = [
                ctypes.c_int
            ]
            self.reset_memory.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Virtual memory
        # --------------------------------------------------------------------

        self.read_svmem = getattr(
            controller,
            "read_svmem",
            None,
        )

        if self.read_svmem:
            self.read_svmem.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_long),
            ]
            self.read_svmem.restype = ctypes.c_int

        self.write_svmem = getattr(
            controller,
            "write_svmem",
            None,
        )

        if self.write_svmem:
            self.write_svmem.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_long,
            ]
            self.write_svmem.restype = ctypes.c_int

        # --------------------------------------------------------------------
        # Parameter / PTP memory
        # --------------------------------------------------------------------

        self.read_param = getattr(
            controller,
            "read_param",
            None,
        )

        if self.read_param:
            self.read_param.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.read_param.restype = ctypes.c_int

        self.write_param = getattr(
            controller,
            "write_param",
            None,
        )

        if self.write_param:
            self.write_param.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.write_param.restype = ctypes.c_int

        self.read_point = getattr(
            controller,
            "read_point",
            None,
        )

        if self.read_point:
            self.read_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.read_point.restype = ctypes.c_int

        self.write_point = getattr(
            controller,
            "write_point",
            None,
        )

        if self.write_point:
            self.write_point.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(COMPACK),
            ]
            self.write_point.restype = ctypes.c_int

        self.load_param = getattr(
            controller,
            "load_param",
            None,
        )

        if self.load_param:
            self.load_param.argtypes = [
                ctypes.c_int
            ]
            self.load_param.restype = ctypes.c_int

        self.save_param = getattr(
            controller,
            "save_param",
            None,
        )

        if self.save_param:
            self.save_param.argtypes = [
                ctypes.c_int
            ]
            self.save_param.restype = ctypes.c_int

        self.save_point = getattr(
            controller,
            "save_point",
            None,
        )

        if self.save_point:
            self.save_point.argtypes = [
                ctypes.c_int
            ]
            self.save_point.restype = ctypes.c_int


    # ========================================================================
    # COMMUNICATION API
    # ========================================================================

    def communication_state(self) -> int:
        return self.get_tmbs_state()


    def communication_state_name(self) -> str:
        return status_name(
            self.communication_state()
        )


    def communication_info(self) -> dict:
        return {
            "state": self.communication_state(),
            "state_name": self.communication_state_name(),
            "baud": self.get_current_baud(),
            "sio_error": self.get_sio_error(),
            "com_error_log": self.get_com_errlog(),
        }


    def initialize(self) -> list[int]:
        """
        Initialize TMBSCOM and discover axes.

        TMBSCOM initialization can initially report OPENING.
        The existing two-stage initialization behavior is preserved.
        """

        axis_array = (
            ctypes.c_int * MAX_AXIS_COUNT
        )(
            *([-1] * MAX_AXIS_COUNT)
        )

        history = []

        result = self.init_tmbs_config(
            self.com_port.encode("ascii"),
            self.baud_code,
            self.nrt,
            int(self.reset),
            int(self.automatic),
            axis_array,
        )

        history.append(result)

        current_state = self.communication_state()

        if current_state == 4:
            self.axes_info = list(axis_array)
            self.initialized = True
            self.refresh_connected_axes()
            return history

        if current_state in (-12, 2):
            self.axes_info = list(axis_array)
            self.initialized = False

            raise SCN6CommunicationError(
                "TMBSCOM initialization failed "
                f"(state={current_state}, "
                f"state_name={status_name(current_state)})"
            )

        time.sleep(1.0)

        result = self.init_tmbs_config(
            self.com_port.encode("ascii"),
            self.baud_code,
            self.nrt,
            int(self.reset),
            int(self.automatic),
            axis_array,
        )

        history.append(result)

        current_state = self.communication_state()

        if current_state == 4:
            self.axes_info = list(axis_array)
            self.initialized = True
            self.refresh_connected_axes()
            return history

        poll_delay = 0.005
        max_polls = 200

        for _ in range(max_polls):

            current_state = self.communication_state()

            if current_state == 4:
                self.axes_info = list(axis_array)
                self.initialized = True
                self.refresh_connected_axes()
                return history

            if current_state in (-12, 2):
                break

            time.sleep(poll_delay)

        self.axes_info = list(axis_array)
        self.initialized = False

        raise SCN6CommunicationError(
            "TMBSCOM initialization timed out "
            f"(state={current_state}, "
            f"state_name={status_name(current_state)}, "
            f"history={history})"
        )


    def disconnect(self) -> int:
        """
        Close TMBSCOM.
        """

        result = self.close_tmbs()

        self.initialized = False

        for axis_state in self.axes.values():
            axis_state.connected = False

        return result


    # ========================================================================
    # VALIDATION
    # ========================================================================

    def require_initialized(self):
        if not self.initialized:
            raise SCN6NotInitializedError(
                "SCN6 controller is not initialized."
            )


    def require_axis(self, axis_number: int):
        axis_number = int(axis_number)

        if axis_number not in AXIS_NUMBERS:
            raise SCN6AxisError(
                f"axis {axis_number} is outside 0..F."
            )

        return axis_number


    def require_connected_axis(self, axis_number: int):
        axis_number = self.require_axis(
            axis_number
        )

        if not self.axes[
            axis_number
        ].connected:
            raise SCN6AxisError(
                f"axis {axis_number:X} is not connected."
            )

        return axis_number


    # ========================================================================
    # AXIS DISCOVERY
    # ========================================================================

    def refresh_connected_axes(self) -> int:
        self.require_initialized()

        axis_array = (
            ctypes.c_ushort * MAX_AXIS_COUNT
        )()

        result = self.get_axes(axis_array)

        for axis_number in AXIS_NUMBERS:
            self.axes[
                axis_number
            ].connected = False

        if result == SIO_DONE:

            values = list(axis_array)

            for axis_number in AXIS_NUMBERS:

                self.axes_info[
                    axis_number
                ] = values[axis_number]

                # Controller reports:
                #
                # 0x0000 = axis present
                # 0xFFFF = axis absent
                #
                # c_ushort turns -1 into 65535.

                self.axes[
                    axis_number
                ].connected = (
                    values[axis_number] == 0
                )

        return result


    def connected_axes(self) -> list[int]:
        self.require_initialized()

        return [
            axis_number
            for axis_number in AXIS_NUMBERS
            if self.axes[
                axis_number
            ].connected
        ]


    def axis_info(self) -> dict:
        self.require_initialized()

        result = {}

        for axis_number in AXIS_NUMBERS:

            state = self.axes[
                axis_number
            ]

            result[str(axis_number)] = {
                "axis": axis_number,
                "connected": bool(
                    state.connected
                ),
                "commanded_position": (
                    state.commanded_position
                ),
                "prepared_motion": (
                    state.prepared_motion
                ),
                "prepared_value": (
                    state.prepared_value
                ),
            }

        return result


    # ========================================================================
    # STATUS API
    # ========================================================================

    def read_axis_status(
        self,
        axis_number: int,
    ) -> dict:

        self.require_initialized()
        axis_number = self.require_axis(
            axis_number
        )

        if self.check_status:
            self.check_status(axis_number)

        raw_status = (
            ctypes.c_ubyte * 4
        )()

        result = self.get_status(
            axis_number,
            raw_status,
        )

        def check(dll_function):

            if dll_function is None:
                return None

            return dll_function(
                axis_number
            )

        status = {
            "axis": axis_number,
            "result": result,
            "raw": bytes(raw_status),
            "raw_hex": raw_hex(raw_status),
            "servo": check(self.check_son),
            "run": check(self.check_run),
            "alarm": check(self.check_alrm),
            "origin": check(self.check_org),
            "pfin": check(self.check_pfin),
        }

        self.last_status[
            axis_number
        ] = status

        return status


    def read_all_axis_status(self) -> dict:

        self.require_initialized()

        result = {}

        for axis_number in AXIS_NUMBERS:

            if self.axes[
                axis_number
            ].connected:

                result[axis_number] = (
                    self.read_axis_status(
                        axis_number
                    )
                )

        return result


    def axis_is_safe_to_move(
        self,
        axis_number: int,
    ):

        axis_number = self.require_connected_axis(
            axis_number
        )

        status = self.read_axis_status(
            axis_number
        )

        if status["result"] != SIO_DONE:
            return False, status

        if status["alarm"] == SIO_DONE:
            return False, status

        if status["servo"] != SIO_DONE:
            return False, status

        return True, status


    # ========================================================================
    # POSITION API
    # ========================================================================

    def read_controller_position(
        self,
        axis_number: int,
    ):

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.read_svmem is None:
            raise SCN6CommunicationError(
                "read_svmem export not present."
            )

        destination = ctypes.c_long(0)

        result = self.read_svmem(
            axis_number,
            PNOW_MEMORY_ADDRESS,
            ctypes.byref(destination),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                "read_svmem failed "
                f"(result={result})"
            )

        return {
            "axis": axis_number,
            "position": int(
                destination.value
            ),
            "error": None,
        }


    # ========================================================================
    # DIRECT MOTION API
    # ========================================================================

    def direct_move_absolute(
        self,
        axis_number: int,
        position: int,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_connected_axis(
            axis_number
        )

        position = int(position)

        if self.move_abs is None:
            raise SCN6MotionError(
                "move_abs export not present."
            )

        safe, status = (
            self.axis_is_safe_to_move(
                axis_number
            )
        )

        if not safe:
            raise SCN6MotionError(
                f"axis {axis_number:X} is not safe "
                f"to move; status={status}"
            )

        result = self.move_abs(
            axis_number,
            ctypes.c_long(position),
        )

        if result != SIO_DONE:
            raise SCN6MotionError(
                f"move_abs failed "
                f"(axis={axis_number:X}, "
                f"position={position}, "
                f"result={result})"
            )

        self.axes[
            axis_number
        ].commanded_position = position

        return result


    def direct_move_incremental(
        self,
        axis_number: int,
        distance: int,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_connected_axis(
            axis_number
        )

        distance = int(distance)

        if self.move_inc is None:
            raise SCN6MotionError(
                "move_inc export not present."
            )

        safe, status = (
            self.axis_is_safe_to_move(
                axis_number
            )
        )

        if not safe:
            raise SCN6MotionError(
                f"axis {axis_number:X} is not safe "
                f"to move; status={status}"
            )

        result = self.move_inc(
            axis_number,
            ctypes.c_long(distance),
        )

        if result != SIO_DONE:
            raise SCN6MotionError(
                f"move_inc failed "
                f"(axis={axis_number:X}, "
                f"distance={distance}, "
                f"result={result})"
            )

        old_position = self.axes[
            axis_number
        ].commanded_position

        if old_position is not None:
            self.axes[
                axis_number
            ].commanded_position = (
                old_position + distance
            )

        return result


    # ========================================================================
    # PREPARED MOTION API
    # ========================================================================

    def clear_motion_buffer(self):
        self.require_initialized()

        for axis_state in self.axes.values():
            axis_state.prepared_motion = None
            axis_state.prepared_value = None

        return {
            "cleared": True
        }


    def prepare_absolute_move(
        self,
        axis_number: int,
        position: int,
    ) -> bool:

        self.require_initialized()

        axis_number = self.require_connected_axis(
            axis_number
        )

        position = int(position)

        self.axes[
            axis_number
        ].prepared_motion = "absolute"

        self.axes[
            axis_number
        ].prepared_value = position

        return True


    def prepare_incremental_move(
        self,
        axis_number: int,
        distance: int,
    ) -> bool:

        self.require_initialized()

        axis_number = self.require_connected_axis(
            axis_number
        )

        distance = int(distance)

        self.axes[
            axis_number
        ].prepared_motion = "incremental"

        self.axes[
            axis_number
        ].prepared_value = distance

        return True


    def prepared_axes(self) -> list[int]:

        self.require_initialized()

        return [
            axis_number
            for axis_number in AXIS_NUMBERS
            if self.axes[
                axis_number
            ].prepared_motion is not None
        ]


    def start_prepared_moves(self) -> bool:

        self.require_initialized()

        axes_to_move = self.prepared_axes()

        if not axes_to_move:
            raise SCN6MotionError(
                "no prepared axes."
            )

        # ------------------------------------------------------------
        # Safety preflight.
        #
        # Nothing should physically move before every participating
        # axis has passed the safety check.
        # ------------------------------------------------------------

        for axis_number in axes_to_move:

            safe, status = (
                self.axis_is_safe_to_move(
                    axis_number
                )
            )

            if not safe:
                raise SCN6MotionError(
                    f"prepared move aborted: "
                    f"axis {axis_number:X} failed "
                    f"safety preflight; "
                    f"status={status}"
                )

        all_accepted = True

        for axis_number in axes_to_move:

            state = self.axes[
                axis_number
            ]

            if state.prepared_motion == "absolute":

                if self.move_abs is None:
                    raise SCN6MotionError(
                        "move_abs export not present."
                    )

                result = self.move_abs(
                    axis_number,
                    ctypes.c_long(
                        state.prepared_value
                    ),
                )

                if result == SIO_DONE:
                    state.commanded_position = (
                        state.prepared_value
                    )

            elif state.prepared_motion == "incremental":

                if self.move_inc is None:
                    raise SCN6MotionError(
                        "move_inc export not present."
                    )

                result = self.move_inc(
                    axis_number,
                    ctypes.c_long(
                        state.prepared_value
                    ),
                )

                if result == SIO_DONE:

                    if (
                        state.commanded_position
                        is not None
                    ):
                        state.commanded_position += (
                            state.prepared_value
                        )

            else:
                raise SCN6MotionError(
                    f"unknown prepared operation "
                    f"on axis {axis_number:X}"
                )

            if result != SIO_DONE:
                all_accepted = False

                raise SCN6MotionError(
                    f"axis {axis_number:X} "
                    f"did not accept movement "
                    f"(result={result})"
                )

        return all_accepted


    # ========================================================================
    # WAIT API
    # ========================================================================

    def wait_for_prepared_axes(
        self,
        timeout: float = 30.0,
        interval: float = 0.05,
    ) -> bool:

        self.require_initialized()

        timeout = float(timeout)
        interval = float(interval)

        axes_to_monitor = self.prepared_axes()

        if not axes_to_monitor:
            raise SCN6MotionError(
                "no prepared axes to monitor."
            )

        start_time = time.monotonic()

        while (
            time.monotonic() - start_time
            < timeout
        ):

            all_finished = True

            for axis_number in axes_to_monitor:

                status = self.read_axis_status(
                    axis_number
                )

                if status["alarm"] == SIO_DONE:
                    raise SCN6MotionError(
                        f"alarm detected on "
                        f"axis {axis_number:X}"
                    )

                if status["pfin"] != SIO_DONE:
                    all_finished = False

            if all_finished:
                return True

            time.sleep(interval)

        return False


    # ========================================================================
    # RAW VIRTUAL MEMORY API
    # ========================================================================

    def read_virtual_memory(
        self,
        axis_number: int,
        address: int,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.read_svmem is None:
            raise SCN6CommunicationError(
                "read_svmem export not present."
            )

        destination = ctypes.c_long(0)

        result = self.read_svmem(
            axis_number,
            int(address),
            ctypes.byref(destination),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"read_svmem failed "
                f"(axis={axis_number:X}, "
                f"address=0x{int(address):04X}, "
                f"result={result})"
            )

        return int(destination.value)


    def write_virtual_memory(
        self,
        axis_number: int,
        address: int,
        value: int,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.write_svmem is None:
            raise SCN6CommunicationError(
                "write_svmem export not present."
            )

        result = self.write_svmem(
            axis_number,
            int(address),
            ctypes.c_long(value),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"write_svmem failed "
                f"(axis={axis_number:X}, "
                f"address=0x{int(address):04X}, "
                f"value={value}, "
                f"result={result})"
            )

        return result


    # ========================================================================
    # PARAMETER / POINT MEMORY API
    # ========================================================================

    def read_parameter(
        self,
        axis_number: int,
    ) -> COMPACK:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.read_param is None:
            raise SCN6CommunicationError(
                "read_param export not present."
            )

        packet = create_empty_compack()

        result = self.read_param(
            axis_number,
            ctypes.byref(packet),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"read_param failed "
                f"(axis={axis_number:X}, "
                f"result={result})"
            )

        return packet


    def write_parameter(
        self,
        axis_number: int,
        packet: COMPACK,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.write_param is None:
            raise SCN6CommunicationError(
                "write_param export not present."
            )

        result = self.write_param(
            axis_number,
            ctypes.byref(packet),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"write_param failed "
                f"(axis={axis_number:X}, "
                f"result={result})"
            )

        return result


    def read_point(
        self,
        axis_number: int,
        point_number: int,
    ) -> COMPACK:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.read_point is None:
            raise SCN6CommunicationError(
                "read_point export not present."
            )

        packet = create_empty_compack()

        result = self.read_point(
            axis_number,
            int(point_number),
            ctypes.byref(packet),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"read_point failed "
                f"(axis={axis_number:X}, "
                f"point={point_number}, "
                f"result={result})"
            )

        return packet


    def write_point(
        self,
        axis_number: int,
        point_number: int,
        packet: COMPACK,
    ) -> int:

        self.require_initialized()

        axis_number = self.require_axis(
            axis_number
        )

        if self.write_point is None:
            raise SCN6CommunicationError(
                "write_point export not present."
            )

        result = self.write_point(
            axis_number,
            int(point_number),
            ctypes.byref(packet),
        )

        if result != SIO_DONE:
            raise SCN6CommunicationError(
                f"write_point failed "
                f"(axis={axis_number:X}, "
                f"point={point_number}, "
                f"result={result})"
            )

        return result


# ============================================================================
# END
# ============================================================================
