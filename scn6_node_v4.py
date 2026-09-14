from __future__ import annotations
import bpy
from bpy.types import Node, NodeTree, NodeSocket
from bpy.props import IntProperty, FloatProperty, BoolProperty, PointerProperty, EnumProperty
try:
    from .bridge_node import get_bridge
except ImportError:
    from bridge_node import get_bridge
SOURCE_ITEMS=(("LOC_X","Location X","Use object X location"),("LOC_Y","Location Y","Use object Y location"),("LOC_Z","Location Z","Use object Z location"),("ROT_X","Rotation X","Use object X rotation"),("ROT_Y","Rotation Y","Use object Y rotation"),("ROT_Z","Rotation Z","Use object Z rotation"))
class SCN6ValueSocket(NodeSocket):
    bl_idname="SCN6ValueSocket"
    bl_label="SCN6 Value"
    def draw(self,context,layout,node,text):
        layout.label(text=text)
    def draw_color(self,context,node):
        return (0.10,0.60,1.00,1.00)
    @classmethod
    def draw_color_simple(cls):
        return (0.10,0.60,1.00,1.00)
class SCN6_OT_Initialize(bpy.types.Operator):
    bl_idname="scn6.initialize"
    bl_label="Initialize SCN6"
    def execute(self,context):
        try:
            bridge=get_bridge()
            if bridge.initialize():
                self.report({"INFO"},"SCN6 connected.")
            else:
                self.report({"ERROR"},bridge.last_error or "SCN6 initialization failed.")
        except Exception as exc:
            self.report({"ERROR"},f"SCN6 error: {exc}")
        return {"FINISHED"}
class SCN6_OT_Stop(bpy.types.Operator):
    bl_idname="scn6.stop"
    bl_label="STOP SCN6"
    def execute(self,context):
        try:
            bridge=get_bridge()
            bridge.stop_all()
            self.report({"INFO"},"SCN6 STOP sent.")
        except Exception as exc:
            self.report({"ERROR"},f"SCN6 stop error: {exc}")
        return {"FINISHED"}
class SCN6AxisNode(Node):
    bl_idname="SCN6AxisNode"
    bl_label="SCN6 Axis"
    bl_icon="DRIVER"
    axis:IntProperty(name="SCN6 Axis",default=0,min=0,max=255)
    target_object:PointerProperty(name="Object",type=bpy.types.Object)
    source:EnumProperty(name="Source",items=SOURCE_ITEMS,default="LOC_X")
    invert_direction:BoolProperty(name="Invert Direction",default=True)
    scale:FloatProperty(name="Scale",default=1000.0)
    offset:FloatProperty(name="Offset",default=0.0)
    minimum:FloatProperty(name="Min",default=-50000.0)
    maximum:FloatProperty(name="Max",default=50000.0)
    enabled:BoolProperty(name="Enabled",default=True)
    armed:BoolProperty(name="ARM",default=False)
    use_world:BoolProperty(name="World",default=False)
    last_source:FloatProperty(name="Last Source",default=0.0)
    last_command:FloatProperty(name="Last Command",default=0.0)
    command_clamped:BoolProperty(name="Clamped",default=False)
    def init(self,context):
        self.inputs.new("NodeSocketObject","Object")
        value=self.inputs.new("SCN6ValueSocket","Value")
        value.default_value=0.0
        self.outputs.new("SCN6ValueSocket","Command")
        self.outputs.new("SCN6ValueSocket","Actual")
        self.outputs.new("NodeSocketBool","Connected")
        self.outputs.new("NodeSocketInt","Axis")
    def get_object(self):
        obj=self.target_object
        try:
            socket=self.inputs.get("Object")
            if socket and socket.is_linked and socket.links:
                from_socket=socket.links[0].from_socket
                if hasattr(from_socket,"default_value") and from_socket.default_value is not None:
                    obj=from_socket.default_value
        except Exception:
            pass
        return obj
    def get_source_value(self):
        obj=self.get_object()
        if obj is None:
            return 0.0
        try:
            depsgraph=bpy.context.evaluated_depsgraph_get()
            obj_eval=obj.evaluated_get(depsgraph)
        except Exception:
            obj_eval=obj
        try:
            if self.use_world:
                matrix=obj_eval.matrix_world
                location=matrix.to_translation()
                rotation=matrix.to_euler()
            else:
                location=obj_eval.location
                rotation=obj_eval.rotation_euler
            values={"LOC_X":location.x,"LOC_Y":location.y,"LOC_Z":location.z,"ROT_X":rotation.x,"ROT_Y":rotation.y,"ROT_Z":rotation.z}
            return float(values.get(self.source,0.0))
        except Exception:
            return 0.0
    def calculate_command(self):
        source=self.get_source_value()
        self.last_source=source
        mapped=-source if self.invert_direction else source
        raw=mapped*float(self.scale)+float(self.offset)
        low=min(float(self.minimum),float(self.maximum))
        high=max(float(self.minimum),float(self.maximum))
        self.command_clamped=raw<low or raw>high
        command=max(low,min(raw,high))
        return float(command)
    def update_command(self):
        if not self.enabled or not self.armed:
            return
        try:
            bridge=get_bridge()
            if not bridge.running or not bridge.connected or bridge.initializing:
                return
            command=self.calculate_command()
            self.last_command=command
            bridge.queue_move(int(self.axis),command)
        except Exception as exc:
            print("[SCN6] command error:",exc)
    def update(self):
        try:
            self.calculate_command()
        except Exception:
            pass
    def draw_buttons(self,context,layout):
        layout.prop(self,"axis",text="Axis")
        layout.prop(self,"target_object",text="Object")
        layout.prop(self,"source",text="Source")
        layout.prop(self,"use_world",text="World")
        box=layout.box()
        box.label(text="Mapping")
        box.prop(self,"scale",text="Scale")
        box.prop(self,"offset",text="Offset")
        box.prop(self,"invert_direction",text="Inverted")
        box=layout.box()
        box.label(text="Limits")
        box.prop(self,"minimum",text="Min")
        box.prop(self,"maximum",text="Max")
        box=layout.box()
        box.label(text="SCN6")
        try:
            bridge=get_bridge()
            if bridge.running and bridge.connected:
                box.label(text="CONNECTED",icon="CHECKMARK")
            elif bridge.running:
                box.label(text="SERVER RUNNING",icon="ERROR")
            else:
                box.label(text="OFFLINE",icon="ERROR")
            box.operator("scn6.initialize",text="Initialize",icon="LINKED")
            box.operator("scn6.stop",text="STOP",icon="CANCEL")
        except Exception:
            box.label(text="UNKNOWN",icon="ERROR")
            box.operator("scn6.initialize",text="Initialize",icon="LINKED")
        box=layout.box()
        box.label(text="Safety")
        box.prop(self,"enabled",text="Enabled")
        row=box.row()
        row.alert=self.armed
        row.prop(self,"armed",text="ARMED" if self.armed else "ARM",toggle=True)
        source=self.get_source_value()
        command=self.calculate_command()
        layout.label(text=f"Source: {source:.4f}")
        layout.label(text=f"Command: {command:.3f}")
        if self.command_clamped:
            row=layout.row()
            row.alert=True
            row.label(text="COMMAND CLAMPED",icon="ERROR")
        layout.label(text=f"Axis: {self.axis}")
    def draw_label(self):
        if self.target_object:
            return f"SCN6 {self.axis} < {self.target_object.name} {self.source}"
        return f"SCN6 Axis {self.axis}"
class SCN6NodeTree(NodeTree):
    bl_idname="SCN6NodeTree"
    bl_label="SCN6"
    bl_icon="PLUGIN"
def get_scn6_nodes():
    result=[]
    try:
        for node_group in bpy.data.node_groups:
            for node in node_group.nodes:
                if node.bl_idname==SCN6AxisNode.bl_idname:
                    result.append(node)
    except Exception:
        pass
    return result
def scn6_trajectory_timer():
    try:
        for node in get_scn6_nodes():
            try:
                node.update_command()
            except Exception as exc:
                print("[SCN6] node update error:",exc)
    except Exception as exc:
        print("[SCN6] timer error:",exc)
    return 0.02
def scn6_node_menu(self,context):
    try:
        self.layout.operator("node.add_node",text="SCN6 Axis",icon="DRIVER").type=SCN6AxisNode.bl_idname
    except Exception:
        pass
classes=(SCN6ValueSocket,SCN6AxisNode,SCN6NodeTree,SCN6_OT_Initialize,SCN6_OT_Stop)
def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            bpy.utils.register_class(cls)
    try:
        bpy.types.NODE_MT_add.remove(scn6_node_menu)
    except Exception:
        pass
    bpy.types.NODE_MT_add.append(scn6_node_menu)
    try:
        if not bpy.app.timers.is_registered(scn6_trajectory_timer):
            bpy.app.timers.register(scn6_trajectory_timer,first_interval=0.1,persistent=False)
    except Exception as exc:
        print("[SCN6] timer registration error:",exc)
    print("[SCN6] node registered")
def unregister():
    try:
        bpy.types.NODE_MT_add.remove(scn6_node_menu)
    except Exception:
        pass
    try:
        if bpy.app.timers.is_registered(scn6_trajectory_timer):
            bpy.app.timers.unregister(scn6_trajectory_timer)
    except Exception:
        pass
    try:
        get_bridge().shutdown()
    except Exception:
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[SCN6] node unregistered")
if __name__=="__main__":
    register()
