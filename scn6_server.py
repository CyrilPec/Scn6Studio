from __future__ import annotations
import threading
import uvicorn
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from scn6_dll import TmbsController, COMPACK, create_compack
app=FastAPI(title="SCN6 Controller API",version="1.0.0")
_controller:TmbsController|None=None
_lock=threading.RLock()
class CommandRequest(BaseModel):
    name:str
    args:dict[str,Any]=Field(default_factory=dict)
def get_controller():
    if _controller is None or not _controller.initialized:
        raise HTTPException(status_code=503,detail="SCN6 controller is not initialized")
    return _controller
def pack_from_pairs(pairs):
    if not isinstance(pairs,list):
        raise ValueError("pairs must be a list")
    return create_compack([(int(pair[0]),int(pair[1])) for pair in pairs])
def pack_to_pairs(packet):
    result=[]
    for i in range(32):
        address=int(packet.address[i])
        if address<0:
            continue
        result.append([address,int(packet.data[i])])
    return result
@app.get("/")
def root():
    return {"name":"SCN6 Controller API","status":"running","docs":"/docs"}
@app.get("/health")
def health():
    return {"ok":True,"connected":_controller is not None and _controller.initialized}
@app.post("/command")
def command(request:CommandRequest):
    global _controller
    name=request.name
    args=request.args
    try:
        with _lock:
            if name=="ping":
                return {"ok":True,"result":"pong"}
            if name=="connect":
                if _controller is not None and _controller.initialized:
                    return {"ok":True,"result":{"connected":True,"already_connected":True,"axes":_controller.connected_axes()}}
                _controller=TmbsController()
                history=_controller.initialize()
                return {"ok":True,"result":{"connected":True,"initialization_history":history,"communication":_controller.communication_info(),"axes":_controller.connected_axes()}}
            if name=="disconnect":
                if _controller is None:
                    return {"ok":True,"result":{"connected":False}}
                result=_controller.disconnect()
                _controller=None
                return {"ok":True,"result":{"connected":False,"result":result}}
            c=get_controller()
            if name=="axes":
                return {"ok":True,"result":c.connected_axes()}
            if name=="axis_info":
                return {"ok":True,"result":c.axis_info()}
            if name=="communication":
                return {"ok":True,"result":c.communication_info()}
            if name=="status":
                axis=args.get("axis")
                result=c.read_all_axis_status() if axis is None else c.read_axis_status(int(axis))
                return {"ok":True,"result":result}
            if name=="position":
                result=c.read_controller_position(int(args["axis"]))
                return {"ok":True,"result":result}
            if name=="move":
                axis=int(args["axis"])
                position=int(args["position"])
                result=c.direct_move_absolute(axis,position)
                return {"ok":True,"result":{"accepted":True,"axis":axis,"position":position,"result":result}}
            if name=="move_inc":
                axis=int(args["axis"])
                distance=int(args["distance"])
                result=c.direct_move_incremental(axis,distance)
                return {"ok":True,"result":{"accepted":True,"axis":axis,"distance":distance,"result":result}}
            if name=="clear":
                return {"ok":True,"result":c.clear_motion_buffer()}
            if name=="prepare_abs":
                axis=int(args["axis"])
                position=int(args["position"])
                return {"ok":True,"result":c.prepare_absolute_move(axis,position)}
            if name=="prepare_inc":
                axis=int(args["axis"])
                distance=int(args["distance"])
                return {"ok":True,"result":c.prepare_incremental_move(axis,distance)}
            if name=="prepared_axes":
                return {"ok":True,"result":c.prepared_axes()}
            if name=="execute":
                return {"ok":True,"result":c.start_prepared_moves()}
            if name=="wait":
                timeout=float(args.get("timeout",30.0))
                interval=float(args.get("interval",0.05))
                return {"ok":True,"result":c.wait_for_prepared_axes(timeout,interval)}
            if name=="memory_read":
                axis=int(args["axis"])
                address=int(args["address"])
                return {"ok":True,"result":c.read_virtual_memory(axis,address)}
            if name=="memory_write":
                axis=int(args["axis"])
                address=int(args["address"])
                value=int(args["value"])
                return {"ok":True,"result":c.write_virtual_memory(axis,address,value)}
            if name=="parameters_read":
                axis=int(args["axis"])
                packet=c.read_parameter(axis)
                return {"ok":True,"result":pack_to_pairs(packet)}
            if name=="parameters_write":
                axis=int(args["axis"])
                packet=pack_from_pairs(args.get("pairs",[]))
                result=c.write_parameter(axis,packet)
                return {"ok":True,"result":result}
            if name=="point_read":
                axis=int(args["axis"])
                point=int(args["point"])
                packet=c.read_point(axis,point)
                return {"ok":True,"result":pack_to_pairs(packet)}
            if name=="point_write":
                axis=int(args["axis"])
                point=int(args["point"])
                packet=pack_from_pairs(args.get("pairs",[]))
                result=c.write_point(axis,point,packet)
                return {"ok":True,"result":result}
            if name=="servo_on":
                axis=int(args["axis"])
                if c.set_son is None:
                    raise RuntimeError("set_son export is not available")
                result=c.set_son(axis)
                return {"ok":True,"result":{"axis":axis,"result":result}}
            if name=="servo_off":
                axis=int(args["axis"])
                if c.set_soff is None:
                    raise RuntimeError("set_soff export is not available")
                result=c.set_soff(axis)
                return {"ok":True,"result":{"axis":axis,"result":result}}
            if name=="alarm_reset":
                axis=int(args["axis"])
                if c.reset_alarm is None:
                    raise RuntimeError("reset_alarm export is not available")
                result=c.reset_alarm(axis)
                return {"ok":True,"result":{"axis":axis,"result":result}}
            if name=="stop":
                axis=int(args["axis"])
                if c.move_jog is None:
                    raise RuntimeError("move_jog export is not available")
                result=c.move_jog(axis,0)
                return {"ok":True,"result":{"axis":axis,"stopped":True,"result":result}}
            raise HTTPException(status_code=400,detail=f"Unknown command: {name}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500,detail=f"{type(exc).__name__}: {exc}")
@app.on_event("shutdown")
def shutdown():
    global _controller
    with _lock:
        if _controller is not None:
            try:
                _controller.disconnect()
            except Exception:
                pass
            _controller=None
if __name__=="__main__":
    uvicorn.run(app,host="127.0.0.1",port=8000)
