```mermaid

flowchart TD
    Server["scn6_server.py<br/>HTTP endpoints"]
    Models["scn6_models.py<br/>Pydantic request/response models"]
    API["scn6_api.py<br/>API facade"]
    Service["scn6_service.py<br/>Service layer"]
    Controller["scn6_controller.py<br/>Hardware controller and safety"]
    Simulated["scn6_simulated_controller.py<br/>Simulation"]
    DLL["scn6_dll.py<br/>TmbsController and DLL bindings"]
    Native["Tmbscom.DLL"]
    Hardware["SCN6 hardware"]

    Server --> API
    Server --> Models
    Server --> Service
    API --> Service
    Service --> Controller
    Service --> Simulated
    Controller --> DLL
    DLL --> Native
    Native --> Hardware

classDiagram
    direction TB

    class FastAPI_Server {
        +app: FastAPI
        +controller: TmbsController
        +controller_lock: RLock
        +armed: bool
        +get_controller()
        +initialize()
        +disconnect()
        +status()
        +move()
        +move_incremental()
        +set_arm()
        +disarm()
    }

    class TmbsController {
        +initialize()
        +disconnect()
        +communication_info()
        +connected_axes()
        +axis_info()
        +refresh_connected_axes()
        +read_axis_status(axis)
        +read_all_axis_status()
        +read_controller_position(axis)
        +direct_move_absolute(axis, position)
        +direct_move_incremental(axis, distance)
        +prepare_absolute_move(axis, position)
        +prepare_incremental_move(axis, distance)
    }

    class MoveRequest {
        +int axis
        +int position
    }

    class IncrementalMoveRequest {
        +int axis
        +int distance
    }

    class AxisRequest {
        +int axis
    }

    class ArmRequest {
        +bool armed
    }

    class SCN6Error {
        <<exception>>
    }

    class SCN6AxisError {
        <<exception>>
    }

    class SCN6CommunicationError {
        <<exception>>
    }

    class SCN6MotionError {
        <<exception>>
    }

    FastAPI_Server --> TmbsController : owns and calls
    FastAPI_Server ..> MoveRequest : validates input
    FastAPI_Server ..> IncrementalMoveRequest : validates input
    FastAPI_Server ..> AxisRequest : validates input
    FastAPI_Server ..> ArmRequest : validates input

    FastAPI_Server ..> SCN6Error : handles exceptions
    SCN6Error <|-- SCN6AxisError
    SCN6Error <|-- SCN6CommunicationError
    SCN6Error <|-- SCN6MotionError
```
