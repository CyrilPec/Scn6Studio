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
    Repository --|The repository works with data models and persistence.|> Model : maps data 
    Repository --> Database : queries
```
