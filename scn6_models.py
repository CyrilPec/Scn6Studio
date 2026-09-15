from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
class MoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    position: int
class IncrementalMoveRequest(BaseModel):
    axis: int = Field(..., ge=0, le=15)
    distance: int
class ArmRequest(BaseModel):
    armed: bool
class WaitRequest(BaseModel):
    timeout: float = Field(30.0, gt=0)
    interval: float = Field(0.05, gt=0)
class APIResponse(BaseModel):
    ok: bool = True
    result: Any = None
class StatusResponse(BaseModel):
    initialized: bool
    armed: bool
    communication: Any = None
    connected_axes: Any = None
    axis_info: Any = None
class RootResponse(BaseModel):
    name: str
    version: str
    running: bool
    initialized: bool
    armed: bool
    docs: str
class MoveResponse(BaseModel):
    ok: bool = True
    axis: int
    position: Optional[int] = None
    distance: Optional[int] = None
    result: Any = None
