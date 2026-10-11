```mermaid

classDiagram
    direction TB

    class FastAPIApp {
        +initialize()
        +register_routes()
    }

    class APIRouter {
        +get()
        +post()
        +put()
        +delete()
    }

    class Controller {
        +handle_request()
        +validate_input()
    }

    class Service {
        +execute_operation()
        +apply_business_rules()
    }

    class Repository {
        +find_by_id()
        +save()
        +update()
        +delete()
    }

    class Model {
        +id
        +attributes
    }

    class Database {
        +connect()
        +execute_query()
    }

    FastAPIApp o-- APIRouter : registers , The application registers its endpoints.
    APIRouter --> Controller : routes requests , Incoming HTTP requests are dispatched to handlers.
    Controller --> Service : delegates , Request handling delegates business logic.
    Service --> Repository : accesses data ,  Data access is separated from business rules.
    Repository --> Model : maps data , The repository works with data models and persistence.
    Repository --> Database : queries

```
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
```
