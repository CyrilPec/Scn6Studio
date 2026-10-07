# Scn6Studio
Graphic editor for controller. 

classDiagram

    class SCN6Error {
        <<Exception>>
        Base SCN6 API exception
    }

    class SCN6NotInitializedError {
        Controller not initialized
    }

    class SCN6AxisError {
        Invalid or unavailable axis
    }

    class SCN6CommunicationError {
        TMBSCOM communication failure
    }

    class SCN6MotionError {
        Motion command failed
    }

    SCN6Error <|-- SCN6NotInitializedError
    SCN6Error <|-- SCN6AxisError
    SCN6Error <|-- SCN6CommunicationError
    SCN6Error <|-- SCN6MotionError


    class AxisState {
        +int axis_number
        +bool connected
        +Optional[int] commanded_position
        +Optional[str] prepared_motion
        +Optional[int] prepared_value
    }


    class COMPACK {
        +address
        +data
    }


    class TmbsController {
        +dll_path
        +com_port
        +baud_code
        +nrt
        +reset
        +automatic
        +dll
        +initialized
        +axes_info
        +axes
        +last_status

        +__init__()
        +bind_dll_functions()
        +communication_state()
        +communication_state_name()
        +communication_info()
        +initialize()
        +disconnect()

        +require_initialized()
        +require_axis()
        +require_connected_axis()

        +refresh_connected_axes()
        +connected_axes()
        +axis_info()

        +read_axis_status()
        +read_all_axis_status()

        +move_point()
        +move_abs()
        +move_inc()
        +move_org()
        +move_rotate()
        +move_jog()
        +follow_position()

        +set_servo_on()
        +set_servo_off()
        +reset_alarm()

        +read_svmem()
        +write_svmem()
        +read_param()
        +write_param()
        +read_point()
        +write_point()
    }


    TmbsController "1" *-- "0..16" AxisState : contains
    TmbsController ..> COMPACK : uses
    TmbsController ..> SCN6Error : raises
    TmbsController ..> SCN6AxisError : raises
    TmbsController ..> SCN6CommunicationError : raises
    TmbsController ..> SCN6NotInitializedError : raises
