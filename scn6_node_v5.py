"""
scn6_node_v5.py
SCN6 Blender controller with direct FastAPI communication.
Architecture:
    Blender Object
         |
         v
    SCN6 Axis Node
         |
         | latest-value command
         v
    SCN6 HTTP Client
         |
         | HTTP
         v
    scn6_server.py
         |
         v
    scn6_dll.py
         |
         v
    Tmbscom.DLL
         |
         v
    SCN6 controller
The Blender node never imports scn6_dll and never communicates with TMBSCOM directly.
"""
from __future__ import annotations
import bpy
import json
import threading
import time
import urllib.request
import urllib.error
from bpy.types import Node, NodeTree, NodeSocket
from bpy.props import IntProperty, FloatProperty, BoolProperty, PointerProperty, EnumProperty, StringProperty
SERVER_URL = "http://127.0.0.1:8000"
SEND_INTERVAL = 0.05
STATUS_INTERVAL = 0.5
SOURCE_ITEMS = (
    ("LOC_X", "Location X", "Use object X location"),
    ("LOC_Y", "Location Y", "Use object Y location"),
    ("LOC_Z", "Location Z", "Use object Z location"),
    ("ROT_X", "Rotation X", "Use object X rotation"),
    ("ROT_Y", "Rotation Y", "Use object Y rotation"),
    ("ROT_Z", "Rotation Z", "Use object Z rotation"),
)
class SCN6ApiClient:
    def __init__(self, base_url=SERVER_URL):
        self.base_url = base_url.rstrip("/")
        self.lock = threading.RLock()
        self.last_error = ""
        self.last_status = {}
        self.running = True
        self.pending = {}
        self.worker = threading.Thread(target=self._worker, name="SCN6-HTTP", daemon=True)
        self.worker.start()
    def _request(self, method, path, payload=None, timeout=2.0):
        url = self.base_url + path
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                detail = json.loads(body).get("detail", body)
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Server unavailable: {exc.reason}")
    def status(self):
        result = self._request("GET", "/status")
        with self.lock:
            self.last_status = result
            self.last_error = ""
        return result
    def initialize(self):
        result = self._request("POST", "/initialize", {})
        with self.lock:
            self.last_status = result
            self.last_error = ""
        return result
    def disconnect(self):
        result = self._request("POST", "/disconnect", {})
        with self.lock:
            self.last_status = result
            self.last_error = ""
        return result
    def arm(self):
        result = self._request("POST", "/arm", {"armed": True})
        with self.lock:
            self.last_status = result
            self.last_error = ""
        return result
    def disarm(self):
        result = self._request("POST", "/disarm", {})
        with self.lock:
            self.last_status = result
            self.last_error = ""
        return result
    def position(self, axis):
        return self._request("GET", f"/axes/{int(axis)}/position")
    def axis_status(self, axis):
        return self._request("GET", f"/axes/{int(axis)}/status")
    def queue_move(self, axis, position):
        with self.lock:
            self.pending[int(axis)] = int(round(position))
    def clear_axis(self, axis):
        with self.lock:
            self.pending.pop(int(axis), None)
    def clear(self):
        with self.lock:
            self.pending.clear()
    def _worker(self):
        while self.running:
            started = time.monotonic()
            try:
                with self.lock:
                    commands = dict(self.pending)
                for axis, position in commands.items():
                    try:
                        self._request("POST", "/move", {"axis": axis, "position": position}, timeout=1.0)
                        with self.lock:
                            if self.pending.get(axis) == position:
                                self.pending.pop(axis, None)
                            self.last_error = ""
                    except Exception as exc:
                        with self.lock:
                            self.last_error = str(exc)
                elapsed = time.monotonic() - started
                time.sleep(max(0.001, SEND_INTERVAL - elapsed))
            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)
                time.sleep(SEND_INTERVAL)
    def stop(self):
        self.running = False
        self.clear()
        if self.worker.is_alive():
            self.worker.join(timeout=0.5)
_api = None
_api_lock = threading.RLock()
def get_api():
    global _api
    with _api_lock:
        if _api is None:
            _api = SCN6ApiClient()
        return _api
def stop_api():
    global _api
    with _api_lock:
        if _api is not None:
            _api.stop()
            _api = None
class SCN6ValueSocket(NodeSocket):
    bl_idname = "SCN6ValueSocket"
    bl_label = "SCN6 Value"
    def draw(self, context, layout, node, text):
        layout.label(text=text)
    def draw_color(self, context, node):
        return (0.10, 0.60, 1.00, 1.00)
    @classmethod
    def draw_color_simple(cls):
        return (0.10, 0.60, 1.00, 1.00)
class SCN6_OT_Initialize(bpy.types.Operator):
    bl_idname = "scn6.initialize"
    bl_label = "Initialize SCN6"
    bl_description = "Initialize the SCN6 FastAPI server and controller"
    def execute(self, context):
        try:
            result = get_api().initialize()
            if result.get("initialized"):
                self.report({"INFO"}, "SCN6 controller initialized.")
            else:
                self.report({"ERROR"}, "SCN6 initialization failed.")
        except Exception as exc:
            self.report({"ERROR"}, f"SCN6 initialization error: {exc}")
        return {"FINISHED"}
class SCN6_OT_Disconnect(bpy.types.Operator):
    bl_idname = "scn6.disconnect"
    bl_label = "Disconnect SCN6"
    bl_description = "Disarm and disconnect the SCN6 controller"
    def execute(self, context):
        try:
            api = get_api()
            api.clear()
            api.disarm()
            api.disconnect()
            self.report({"INFO"}, "SCN6 controller disconnected.")
        except Exception as exc:
            self.report({"ERROR"}, f"SCN6 disconnect error: {exc}")
        return {"FINISHED"}
class SCN6_OT_Arm(bpy.types.Operator):
    bl_idname = "scn6.arm"
    bl_label = "ARM SCN6"
    bl_description = "Enable SCN6 motion on the server"
    def execute(self, context):
        try:
            result = get_api().arm()
            if result.get("armed"):
                self.report({"INFO"}, "SCN6 ARMED.")
            else:
                self.report({"ERROR"}, "SCN6 failed to arm.")
        except Exception as exc:
            self.report({"ERROR"}, f"SCN6 arm error: {exc}")
        return {"FINISHED"}
class SCN6_OT_Disarm(bpy.types.Operator):
    bl_idname = "scn6.disarm"
    bl_label = "DISARM SCN6"
    bl_description = "Disable SCN6 motion and clear pending commands"
    def execute(self, context):
        try:
            api = get_api()
            api.clear()
            result = api.disarm()
            for node in get_scn6_nodes():
                node.armed = False
            if not result.get("armed", True):
                self.report({"INFO"}, "SCN6 DISARMED.")
            else:
                self.report({"ERROR"}, "SCN6 failed to disarm.")
        except Exception as exc:
            self.report({"ERROR"}, f"SCN6 disarm error: {exc}")
        return {"FINISHED"}
class SCN6AxisNode(Node):
    bl_idname = "SCN6AxisNode"
    bl_label = "SCN6 Axis"
    bl_icon = "DRIVER"
    axis: IntProperty(name="SCN6 Axis", description="SCN6 actuator axis number", default=0, min=0, max=15)
    target_object: PointerProperty(name="Object", description="Blender object used as trajectory source", type=bpy.types.Object)
    source: EnumProperty(name="Source", description="Object transform component", items=SOURCE_ITEMS, default="LOC_X")
    invert_direction: BoolProperty(name="Invert Direction", description="Invert trajectory direction", default=True)
    scale: FloatProperty(name="Scale", description="Multiply source value", default=1000.0)
    offset: FloatProperty(name="Offset", description="Add value after scaling", default=0.0)
    minimum: FloatProperty(name="Min", description="Minimum SCN6 position", default=-50000.0)
    maximum: FloatProperty(name="Max", description="Maximum SCN6 position", default=50000.0)
    enabled: BoolProperty(name="Enabled", description="Enable this node", default=True)
    armed: BoolProperty(name="ARM", description="Allow this node to command the actuator", default=False)
    use_world: BoolProperty(name="World", description="Use world-space object transform", default=False)
    last_source: FloatProperty(name="Last Source", default=0.0)
    last_command: FloatProperty(name="Last Command", default=0.0)
    actual_position: FloatProperty(name="Actual", default=0.0)
    connected: BoolProperty(name="Connected", default=False)
    command_clamped: BoolProperty(name="Clamped", default=False)
    def init(self, context):
        self.inputs.new("NodeSocketObject", "Object")
        value = self.inputs.new("SCN6ValueSocket", "Value")
        value.default_value = 0.0
        self.outputs.new("SCN6ValueSocket", "Command")
        self.outputs.new("SCN6ValueSocket", "Actual")
        self.outputs.new("NodeSocketBool", "Connected")
        self.outputs.new("NodeSocketInt", "Axis")
    def get_object(self):
        obj = self.target_object
        try:
            socket = self.inputs.get("Object")
            if socket is not None and socket.is_linked and socket.links:
                from_socket = socket.links[0].from_socket
                if hasattr(from_socket, "default_value"):
                    linked_object = from_socket.default_value
                    if linked_object is not None:
                        obj = linked_object
        except Exception:
            pass
        return obj
    def get_source_value(self):
        obj = self.get_object()
        if obj is None:
            return 0.0
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(depsgraph)
        except Exception:
            obj_eval = obj
        try:
            if self.use_world:
                matrix = obj_eval.matrix_world
                location = matrix.to_translation()
                rotation = matrix.to_euler()
            else:
                location = obj_eval.location
                rotation = obj_eval.rotation_euler
        except Exception:
            try:
                location = obj.location
                rotation = obj.rotation_euler
            except Exception:
                return 0.0
        try:
            if self.source == "LOC_X":
                return float(location.x)
            if self.source == "LOC_Y":
                return float(location.y)
            if self.source == "LOC_Z":
                return float(location.z)
            if self.source == "ROT_X":
                return float(rotation.x)
            if self.source == "ROT_Y":
                return float(rotation.y)
            if self.source == "ROT_Z":
                return float(rotation.z)
        except Exception:
            return 0.0
        return 0.0
    def calculate_command(self):
        source = self.get_source_value()
        self.last_source = source
        mapped_source = -source if self.invert_direction else source
        raw_command = mapped_source * float(self.scale) + float(self.offset)
        low = min(float(self.minimum), float(self.maximum))
        high = max(float(self.minimum), float(self.maximum))
        self.command_clamped = raw_command < low or raw_command > high
        command = max(low, min(raw_command, high))
        return float(command)
    def update_command(self):
        api = get_api()
        if not self.enabled or not self.armed:
            api.clear_axis(self.axis)
            return
        try:
            command = self.calculate_command()
            self.last_command = command
            api.queue_move(self.axis, command)
        except Exception as exc:
            print("[SCN6] command error:", exc)
    def update_actual(self):
        try:
            api = get_api()
            status = api.last_status
            self.connected = bool(status.get("initialized", False))
        except Exception:
            self.connected = False
    def update(self):
        try:
            self.calculate_command()
        except Exception:
            pass
    def draw_buttons(self, context, layout):
        layout.prop(self, "axis", text="Axis")
        layout.prop(self, "target_object", text="Object")
        layout.prop(self, "source", text="Source")
        layout.prop(self, "use_world", text="World")
        box = layout.box()
        box.label(text="Mapping")
        box.prop(self, "scale", text="Scale")
        box.prop(self, "offset", text="Offset")
        box.prop(self, "invert_direction", text="Inverted")
        box = layout.box()
        box.label(text="Limits")
        box.prop(self, "minimum", text="Min")
        box.prop(self, "maximum", text="Max")
        box = layout.box()
        box.label(text="SCN6")
        try:
            api = get_api()
            status = api.last_status
            initialized = bool(status.get("initialized", False))
            server_armed = bool(status.get("armed", False))
            if initialized:
                box.label(text="Controller: CONNECTED", icon="CHECKMARK")
                box.operator("scn6.disconnect", text="Disconnect", icon="UNLINKED")
            else:
                box.label(text="Controller: DISCONNECTED", icon="ERROR")
                box.operator("scn6.initialize", text="Initialize", icon="LINKED")
            if server_armed:
                row = box.row()
                row.alert = True
                row.operator("scn6.disarm", text="DISARM", icon="CANCEL")
            else:
                box.operator("scn6.arm", text="ARM SERVER", icon="REC")
            if api.last_error:
                box.label(text=api.last_error[:80], icon="ERROR")
        except Exception as exc:
            box.label(text="API: OFFLINE", icon="ERROR")
            box.label(text=str(exc)[:80])
        box = layout.box()
        box.label(text="Safety")
        box.prop(self, "enabled", text="Enabled")
        row = box.row()
        if self.armed:
            row.alert = True
            row.prop(self, "armed", text="ARMED", toggle=True)
        else:
            row.prop(self, "armed", text="ARM", toggle=True)
        layout.separator()
        try:
            source = self.get_source_value()
            command = self.calculate_command()
        except Exception:
            source = 0.0
            command = 0.0
        layout.label(text=f"Source: {source:.4f}")
        layout.label(text=f"Command: {command:.3f}")
        layout.label(text=f"Actual: {self.actual_position:.3f}")
        if self.command_clamped:
            row = layout.row()
            row.alert = True
            row.label(text="COMMAND CLAMPED", icon="ERROR")
        layout.label(text=f"Axis: {self.axis}")
        if self.armed:
            layout.label(text="MOTION ENABLED", icon="REC")
        else:
            layout.label(text="Motion disarmed", icon="PAUSE")
    def draw_label(self):
        if self.target_object:
            return f"SCN6 {self.axis} < {self.target_object.name} {self.source}"
        return f"SCN6 Axis {self.axis}"
class SCN6NodeTree(NodeTree):
    bl_idname = "SCN6NodeTree"
    bl_label = "SCN6"
    bl_icon = "PLUGIN"
def get_scn6_nodes():
    result = []
    try:
        for node_group in bpy.data.node_groups:
            try:
                for node in node_group.nodes:
                    if node.bl_idname == SCN6AxisNode.bl_idname:
                        result.append(node)
            except Exception:
                continue
    except Exception:
        pass
    return result
def scn6_trajectory_timer():
    try:
        nodes = get_scn6_nodes()
        any_armed = any(node.enabled and node.armed for node in nodes)
        api = get_api()
        if any_armed:
            try:
                if not api.last_status.get("armed", False):
                    api.arm()
            except Exception as exc:
                with api.lock:
                    api.last_error = str(exc)
        else:
            try:
                if api.last_status.get("armed", False):
                    api.clear()
                    api.disarm()
            except Exception as exc:
                with api.lock:
                    api.last_error = str(exc)
        for node in nodes:
            try:
                node.update_command()
            except Exception as exc:
                print("[SCN6] node update error:", exc)
        now = time.monotonic()
        if not hasattr(scn6_trajectory_timer, "_last_status"):
            scn6_trajectory_timer._last_status = 0.0
        if now - scn6_trajectory_timer._last_status >= STATUS_INTERVAL:
            scn6_trajectory_timer._last_status = now
            try:
                api.status()
            except Exception as exc:
                with api.lock:
                    api.last_error = str(exc)
        for node in nodes:
            try:
                node.update_actual()
            except Exception:
                pass
    except Exception as exc:
        print("[SCN6] trajectory timer error:", exc)
    return 0.02
def scn6_node_menu(self, context):
    try:
        self.layout.operator("node.add_node", text="SCN6 Axis", icon="DRIVER").type = SCN6AxisNode.bl_idname
    except Exception:
        pass
classes = (
    SCN6ValueSocket,
    SCN6AxisNode,
    SCN6NodeTree,
    SCN6_OT_Initialize,
    SCN6_OT_Disconnect,
    SCN6_OT_Arm,
    SCN6_OT_Disarm,
)
def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as exc:
            if "already registered" in str(exc):
                try:
                    bpy.utils.unregister_class(cls)
                except Exception:
                    pass
                bpy.utils.register_class(cls)
            else:
                raise
    try:
        bpy.types.NODE_MT_add.remove(scn6_node_menu)
    except Exception:
        pass
    bpy.types.NODE_MT_add.append(scn6_node_menu)
    try:
        if not bpy.app.timers.is_registered(scn6_trajectory_timer):
            bpy.app.timers.register(scn6_trajectory_timer, first_interval=0.1, persistent=False)
    except Exception as exc:
        print("[SCN6] trajectory timer registration error:", exc)
    print("[SCN6] scn6_node_v5 registered.")
def unregister():
    try:
        get_api().clear()
        try:
            get_api().disarm()
        except Exception:
            pass
    except Exception:
        pass
    try:
        bpy.types.NODE_MT_add.remove(scn6_node_menu)
    except Exception:
        pass
    try:
        if bpy.app.timers.is_registered(scn6_trajectory_timer):
            bpy.app.timers.unregister(scn6_trajectory_timer)
    except Exception:
        pass
    stop_api()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[SCN6] scn6_node_v5 unregistered.")
if __name__ == "__main__":
    register()
