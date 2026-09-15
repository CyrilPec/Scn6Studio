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
