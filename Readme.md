Write code without empty lines.
Write full sentences for less scrolling.
All files in one directory, so file names define service and module.
reference docs: TERMIBUS-EE06426I-EN.pdf TMBSCOM-EN.pdf an2k-028.pdf RC_Serial_Communication.pdf

Scn6Studio/
│
├── blender/
│   ├── nodes/
│   │   └── scn6_axis_node.py
│   ├── operators/
│   ├── ui/
│   └── client/
│       └── scn6_api_client.py
│
├── server/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── controller.py
│   │   ├── axes.py
│   │   └── motion.py
│   │
│   ├── schemas/
│   │   ├── controller.py
│   │   ├── axis.py
│   │   └── motion.py
│   │
│   ├── services/
│   │   ├── controller_service.py
│   │   ├── motion_service.py
│   │   └── axis_service.py
│   │
│   ├── hardware/
│   │   └── scn6_controller.py
│   │
│   └── core/
│       ├── config.py
│       ├── logging.py
│       └── exceptions.py
│
└── tests/
    ├── test_api.py
    ├── test_motion.py
    └── test_controller.py


 Area	Library
API	FastAPI
Server	Uvicorn
Validation	Pydantic v2
Settings	pydantic-settings
HTTP client	httpx
Logging	structlog
Retry	tenacity
State machine	transitions
Testing	pytest
API testing	httpx
Static typing	mypy or pyright
Formatting	ruff
Packaging	uv
DB, if needed	SQLModel + SQLite
DB migrations	Alembic
Hardware abstraction	your own interface

 Split scn6_server.py into API / service / hardware layers.

Replace /command with typed REST endpoints.

Create Pydantic request/response models.

Create SCN6Controller hardware interface.

Create SimulatedSCN6Controller.

Move controller lifecycle into a FastAPI lifespan/service.

Introduce an SCN6 state machine.

Replace urllib with httpx in Blender.

Add structlog + proper error taxonomy.

Add pytest tests against the simulated controller.

Add pydantic-settings.

Only then consider persistence/database.

That would turn what you currently have from "FastAPI wrapped around the DLL" into a much more robust hardware-control architecture.

 I am developing two hardware-control projects and want to evolve them toward a common, clean architecture.

SCN6 project:
GitHub: https://github.com/CyrilPec/Scn6Studio
Branch: Scn6-with-FastApi

Current SCN6 architecture:
Blender
↓
FastAPI / REST API
↓
SCN6API
↓
SCN6Service
↓
SCN6Controller
↓
Tmbscom.DLL
↓
SCN6 hardware

The controller layer is now separated from the API/service layers.
SCN6Controller handles hardware access and software ARM/DISARM permission.
SCN6Service owns the controller and provides the application-level interface.
SCN6API exposes that service to FastAPI.
The Blender node communicates with FastAPI using httpx.

A simulated controller has also been designed:
SCN6Controller
SimulatedSCN6Controller

The simulator allows testing the service/API without real SCN6 hardware.

The latest Blender node commit is:
b8662acec3e1a7bb78bcced072e088763f202036
"Update scn6_node_v5.py"

Important SCN6 rule:
SCN6Controller.arm() currently means software motion permission. It does NOT mean hardware servo-on. Do not confuse these concepts.

Next SCN6 development order:

1. Add/finalize simulator tests.
2. Add FastAPI/API integration tests using the simulator.
3. Add a proper SCN6 state machine.
4. Improve error taxonomy/logging.
5. Continue hardware testing only after the software architecture is stable.

VFD project:
GitHub: https://github.com/CyrilPec/vfd_node
Main branch.

The VFD is a Huanyang HY01D523B VFD controlled through RS-485.

Current intended VFD architecture:
Blender VFD Node
↓
VFDManager / VFDController
↓
HY01D523B driver
↓
pyserial RS-485 transport
↓
HY01D523B VFD

The VFD architecture has already identified several important problems:

* serial transport must be passed correctly to the driver
* commands must validate actual VFD responses
* CRC, slave ID and malformed responses must be checked
* frequency uses Hz × 100 in the protocol
* frequency and parameter ranges must be validated
* running/reverse/fault are currently partly locally tracked
* actual spindle RPM is currently estimated, not measured
* disable/disarm should attempt STOP
* software STOP is not a safety-rated emergency stop
* real safety must use appropriate hardware/STO
* actual status registers must not be invented without exact protocol/firmware documentation

The important architectural idea now is:
Do NOT force SCN6 and VFD to have identical commands.

Instead, share the common controller lifecycle and architecture:

Controller

* initialize()
* disconnect()
* status()
* arm()
* disarm()

Then each hardware controller has its own domain commands.

SCN6:

* move_absolute()
* move_incremental()
* prepare_move()
* start_prepared_moves()
* read_axis_status()
* read_position()

VFD:

* start()
* stop()
* halt()
* forward()
* reverse()
* set_frequency()
* read_parameter()
* write_parameter()
* status()

The generalized architecture should eventually look like:

```
                     Blender
                        ↓
                   FastAPI/API
                        ↓
                 Controller Service
                   ↙           ↘
          SCN6Controller    VFDController
                ↓                ↓
           Tmbscom.DLL       HY01D523B
                ↓                ↓
              SCN6             RS-485
```

Both controllers can have simulators:

SCN6Controller
SimulatedSCN6Controller

VFDController
SimulatedVFDController

The main benefit is that adding the VFD becomes much easier after the SCN6 architecture is stabilized. We should reuse the architectural pattern, not copy SCN6-specific motion logic into the VFD.

IMPORTANT NEXT MOVE:
First inspect the CURRENT GitHub state before changing anything.

For SCN6, inspect the current branch Scn6-with-FastApi and verify the current versions of:

* scn6_controller.py
* scn6_service.py
* scn6_api.py
* scn6_server.py
* scn6_models.py
* scn6_simulated_controller.py
* scn6_node_v5.py
* requirements.txt / pyproject files if present
* README if relevant

Then decide the smallest next implementation step based on the actual repository, rather than assuming the old versions.

After SCN6 simulator/API tests are stable, start integrating the VFD using the same layered pattern:

vfd_driver.py
↓
vfd_controller.py
↓
vfd_service.py
↓
vfd_api.py
↓
FastAPI
↓
Blender VFD node

The existing VFDManager should be evaluated and, where appropriate, transformed into the controller/service separation rather than blindly copied.

For VFD testing, create a fake serial transport before testing a real spindle. Test:

* exact transmitted frames
* CRC
* slave ID
* Hz × 100
* parameter encoding
* invalid frequency
* invalid parameter
* connection failure
* partial writes
* malformed response
* bad CRC
* wrong slave ID

Do not claim that a command succeeded merely because the local software state changed.

Also keep the distinction:
commanded state ≠ measured hardware state.

For example:
commanded_frequency may be 200 Hz while measured_frequency/status may be unknown until the VFD actually reports it.

The goal is a robust hardware-control architecture that can eventually control both SCN6 motion hardware and the VFD from Blender through FastAPI, while keeping hardware-specific logic isolated.

When editing GitHub files:

* inspect/fetch the current file first
* preserve the current architecture and user changes
* update the complete file using the current SHA
* do not overwrite newer user changes
* prefer small incremental commits
* code should contain NO unnecessary blank lines
* if possible, keep files top-level rather than introducing unnecessary folders

Start by inspecting the current SCN6 repository and tell me what the actual next move should be.

