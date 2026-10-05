```mermaid
graph LR
TmbsController-->isa-->Controller
TmbsController-->uses-->TmbscomDLL
TmbsController-->communicates_with-->SCN6Controller

TmbsController-->initializes-->Tmbscom
TmbsController-->discovers-->Axes
TmbsController-->manages-->AxisState

AxisState-->represents-->Axis
AxisState-->contains-->connected
AxisState-->contains-->commanded_position
AxisState-->contains-->prepared_motion
AxisState-->contains-->prepared_value

TmbsController-->reads-->AxisStatus
TmbsController-->reads-->ControllerPosition
TmbsController-->reads-->VirtualMemory
TmbsController-->reads-->Parameter
TmbsController-->reads-->Point

TmbsController-->performs-->DirectMotion
TmbsController-->performs-->PreparedMotion
TmbsController-->performs-->JogMotion

DirectMotion-->includes-->AbsoluteMove
DirectMotion-->includes-->IncrementalMove
DirectMotion-->includes-->PointMove
DirectMotion-->includes-->Jog

PreparedMotion-->prepares-->AbsoluteMove
PreparedMotion-->prepares-->IncrementalMove
PreparedMotion-->requires-->SafetyCheck
PreparedMotion-->executes-->MultipleAxes

TmbsController-->waits_for-->MotionCompletion
MotionCompletion-->depends_on-->AxisStatus

AxisSafety-->depends_on-->Initialized
AxisSafety-->depends_on-->Connected
AxisSafety-->depends_on-->Servo
AxisSafety-->depends_on-->Alarm

AbsoluteMove-->changes-->AxisPosition
IncrementalMove-->changes-->AxisPosition
Jog-->changes-->AxisPosition

TmbsController-->reads-->Position-->from-->PNOW
PNOW-->has_address-->0x7400

TmbsController-->reads-->Status
TmbsController-->checks-->Servo
TmbsController-->checks-->Run
TmbsController-->checks-->Alarm
TmbsController-->checks-->Origin
TmbsController-->checks-->PFIN

TmbsController-->uses-->COMPACK
COMPACK-->contains-->Address
COMPACK-->contains-->Data

read_parameter-->returns-->COMPACK
read_point-->returns-->COMPACK
write_parameter-->accepts-->COMPACK
write_point-->accepts-->COMPACK

```

```mermaid
graph LR
TmbsController -->|uses| TmbscomDLL
TmbsController -->|manages| Axis
TmbsController -->|reads| AxisStatus
TmbsController -->|performs| Motion
TmbsController -->|accesses| Memory
TmbsController -->|reads| Parameter
TmbsController -->|reads| Point

Motion -->|includes| AbsoluteMove
Motion -->|includes| IncrementalMove
Motion -->|includes| PointMove
Motion -->|includes| Jog

AbsoluteMove -->|changes| AxisPosition
IncrementalMove -->|changes| AxisPosition
PointMove -->|changes| AxisPosition
Jog -->|changes| AxisPosition

AxisStatus -->|contains| Servo
AxisStatus -->|contains| Alarm
AxisStatus -->|contains| Origin
AxisStatus -->|contains| PFIN

Motion -->|requires| Connected
Motion -->|requires| Servo
Motion -->|checks| Alarm

TmbsController -->|uses| COMPACK
COMPACK -->|contains| Address
COMPACK -->|contains| Data

Memory -->|contains| VirtualMemory
Memory -->|contains| Parameter
Memory -->|contains| Point

TmbscomDLL -->|controls| SCN6Controller
```
