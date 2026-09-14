"""
scn6_node_v4.py
===============

SCN6 Blender controller - Version 4.1

Architecture:

    Blender Object
         |
         v
    SCN6 Axis Node
         |
         | latest-value command
         v
    bridge_node.py
         |
         | JSON Lines
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


IMPORTANT
=========

This node NEVER imports scn6_dll.

This node NEVER communicates with TMBSCOM directly.

All hardware communication belongs to:

    bridge_node.py
        |
        v
    scn6_server.py


TRAJECTORY
==========

The node does NOT call bridge.move() directly.

It uses:

    bridge.queue_move()

The bridge keeps only the newest requested position for each axis
and sends commands at a controlled rate.

This prevents Blender's timer/dependency updates from flooding
the SCN6 server with duplicate commands.


SAFETY
======

Each node has:

    Enabled
    ARM

Default:

    Enabled = True
    ARM = False

No movement command is generated unless ARM is enabled.
"""

from __future__ import annotations

import bpy

from bpy.types import Node, NodeTree, NodeSocket
from bpy.props import (
    IntProperty,
    FloatProperty,
    BoolProperty,
    PointerProperty,
    EnumProperty,
)


# ============================================================================
# BRIDGE
# ============================================================================

try:
    from .bridge_node import get_bridge
except ImportError:
    from bridge_node import get_bridge


# ============================================================================
# SOURCE ENUM
# ============================================================================

SOURCE_ITEMS = (
    (
        "LOC_X",
        "Location X",
        "Use object X location",
    ),
    (
        "LOC_Y",
        "Location Y",
        "Use object Y location",
    ),
    (
        "LOC_Z",
        "Location Z",
        "Use object Z location",
    ),
    (
        "ROT_X",
        "Rotation X",
        "Use object X rotation",
    ),
    (
        "ROT_Y",
        "Rotation Y",
        "Use object Y rotation",
    ),
    (
        "ROT_Z",
        "Rotation Z",
        "Use object Z rotation",
    ),
)


# ============================================================================
# VALUE SOCKET
# ============================================================================

class SCN6ValueSocket(NodeSocket):

    bl_idname = "SCN6ValueSocket"
    bl_label = "SCN6 Value"

    def draw(
        self,
        context,
        layout,
        node,
        text,
    ):
        layout.label(text=text)

    def draw_color(
        self,
        context,
        node,
    ):
        return (
            0.10,
            0.60,
            1.00,
            1.00,
        )

    @classmethod
    def draw_color_simple(cls):
        return (
            0.10,
            0.60,
            1.00,
            1.00,
        )


# ============================================================================
# INITIALIZE OPERATOR
# ============================================================================

class SCN6_OT_Initialize(
    bpy.types.Operator
):

    bl_idname = "scn6.initialize"
    bl_label = "Initialize SCN6"

    bl_description = (
        "Start the SCN6 32-bit bridge server and connect to the controller"
    )

    def execute(
        self,
        context,
    ):

        try:

            bridge = get_bridge()

            response = bridge.initialize()

            if response:

                self.report(
                    {"INFO"},
                    "SCN6 bridge initialized.",
                )

            else:

                error = getattr(
                    bridge,
                    "last_error",
                    "",
                )

                if error:

                    self.report(
                        {"ERROR"},
                        f"SCN6 initialization failed: {error}",
                    )

                else:

                    self.report(
                        {"ERROR"},
                        "SCN6 bridge initialization failed.",
                    )

        except Exception as exc:

            self.report(
                {"ERROR"},
                f"SCN6 initialization error: {exc}",
            )

        return {"FINISHED"}


# ============================================================================
# SCN6 AXIS NODE
# ============================================================================

class SCN6AxisNode(Node):

    bl_idname = "SCN6AxisNode"
    bl_label = "SCN6 Axis"
    bl_icon = "DRIVER"

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    axis: IntProperty(
        name="SCN6 Axis",
        description="SCN6 actuator axis number",
        default=0,
        min=0,
        max=255,
    )

    target_object: PointerProperty(
        name="Object",
        description="Blender object used as trajectory source",
        type=bpy.types.Object,
    )

    source: EnumProperty(
        name="Source",
        description="Object transform component",
        items=SOURCE_ITEMS,
        default="LOC_X",
    )

    invert_direction: BoolProperty(
        name="Invert Direction",
        description="Invert trajectory direction",
        default=True,
    )

    scale: FloatProperty(
        name="Scale",
        description="Multiply source value",
        default=1000.0,
    )

    offset: FloatProperty(
        name="Offset",
        description="Add value after scaling",
        default=0.0,
    )

    minimum: FloatProperty(
        name="Min",
        description="Minimum SCN6 position",
        default=-50000.0,
    )

    maximum: FloatProperty(
        name="Max",
        description="Maximum SCN6 position",
        default=50000.0,
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this node",
        default=True,
    )

    armed: BoolProperty(
        name="ARM",
        description="Allow this node to command the actuator",
        default=False,
    )

    use_world: BoolProperty(
        name="World",
        description="Use world-space object transform",
        default=False,
    )

    last_source: FloatProperty(
        name="Last Source",
        default=0.0,
    )

    last_command: FloatProperty(
        name="Last Command",
        default=0.0,
    )

    command_clamped: BoolProperty(
        name="Clamped",
        default=False,
    )

    # =========================================================================
    # INIT
    # =========================================================================

    def init(
        self,
        context,
    ):

        self.inputs.new(
            "NodeSocketObject",
            "Object",
        )

        value = self.inputs.new(
            "SCN6ValueSocket",
            "Value",
        )

        value.default_value = 0.0

        self.outputs.new(
            "SCN6ValueSocket",
            "Command",
        )

        self.outputs.new(
            "SCN6ValueSocket",
            "Actual",
        )

        self.outputs.new(
            "NodeSocketBool",
            "Connected",
        )

        self.outputs.new(
            "NodeSocketInt",
            "Axis",
        )

    # =========================================================================
    # OBJECT
    # =========================================================================

    def get_object(self):

        obj = self.target_object

        try:

            socket = self.inputs.get("Object")

            if socket is not None:

                if socket.is_linked and socket.links:

                    from_socket = (
                        socket.links[0].from_socket
                    )

                    if hasattr(
                        from_socket,
                        "default_value",
                    ):

                        linked_object = (
                            from_socket.default_value
                        )

                        if linked_object is not None:

                            obj = linked_object

        except Exception:

            pass

        return obj

    # =========================================================================
    # SOURCE VALUE
    # =========================================================================

    def get_source_value(self):

        obj = self.get_object()

        if obj is None:
            return 0.0

        try:

            depsgraph = (
                bpy.context.evaluated_depsgraph_get()
            )

            obj_eval = obj.evaluated_get(
                depsgraph
            )

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

    # =========================================================================
    # CALCULATE COMMAND
    # =========================================================================

    def calculate_command(self):

        source = self.get_source_value()

        self.last_source = source

        mapped_source = source

        if self.invert_direction:

            mapped_source = -mapped_source

        raw_command = (
            mapped_source
            * float(self.scale)
        )

        raw_command += float(self.offset)

        low = min(
            float(self.minimum),
            float(self.maximum),
        )

        high = max(
            float(self.minimum),
            float(self.maximum),
        )

        self.command_clamped = (
            raw_command < low
            or raw_command > high
        )

        command = max(
            low,
            min(
                raw_command,
                high,
            ),
        )

        return float(command)

    # =========================================================================
    # UPDATE COMMAND
    # =========================================================================

    def update_command(self):

        # ---------------------------------------------------------------
        # SAFETY
        # ---------------------------------------------------------------

        if not self.enabled:
            return

        if not self.armed:
            return

        # ---------------------------------------------------------------
        # GET BRIDGE
        # ---------------------------------------------------------------

        try:

            bridge = get_bridge()

        except Exception as exc:

            print(
                "[SCN6] bridge access error:",
                exc,
            )

            return

        # ---------------------------------------------------------------
        # BRIDGE MUST BE RUNNING
        # ---------------------------------------------------------------

        if not bridge.running:

            return

        # ---------------------------------------------------------------
        # CONTROLLER MUST BE CONNECTED
        #
        # Do not send trajectory commands while the hardware is
        # disconnected or while initialization is in progress.
        # ---------------------------------------------------------------

        if not bridge.connected:

            return

        if bridge.initializing:

            return

        # ---------------------------------------------------------------
        # CALCULATE
        # ---------------------------------------------------------------

        try:

            command = self.calculate_command()

        except Exception as exc:

            print(
                "[SCN6] command calculation error:",
                exc,
            )

            return

        self.last_command = command

        # ---------------------------------------------------------------
        # LATEST-VALUE QUEUE
        #
        # IMPORTANT:
        #
        # DO NOT USE:
        #
        #     bridge.move(...)
        #
        # here.
        #
        # queue_move() stores only the latest command for this axis.
        # bridge_node.py sends it at its controlled communication rate.
        # ---------------------------------------------------------------

        try:

            bridge.queue_move(
                axis=int(self.axis),
                position=command,
            )

        except Exception as exc:

            print(
                "[SCN6] queue move error:",
                exc,
            )

    # =========================================================================
    # NODE UPDATE
    # =========================================================================

    def update(self):

        try:

            self.calculate_command()

        except Exception:

            pass

    # =========================================================================
    # UI
    # =========================================================================

    def draw_buttons(
        self,
        context,
        layout,
    ):

        layout.prop(
            self,
            "axis",
            text="Axis",
        )

        layout.prop(
            self,
            "target_object",
            text="Object",
        )

        layout.prop(
            self,
            "source",
            text="Source",
        )

        layout.prop(
            self,
            "use_world",
            text="World",
        )

        box = layout.box()

        box.label(
            text="Mapping"
        )

        box.prop(
            self,
            "scale",
            text="Scale",
        )

        box.prop(
            self,
            "offset",
            text="Offset",
        )

        box.prop(
            self,
            "invert_direction",
            text="Inverted",
        )

        box = layout.box()

        box.label(
            text="Limits"
        )

        box.prop(
            self,
            "minimum",
            text="Min",
        )

        box.prop(
            self,
            "maximum",
            text="Max",
        )

        # ---------------------------------------------------------------
        # SCN6 BRIDGE STATUS
        # ---------------------------------------------------------------

        box = layout.box()

        box.label(
            text="SCN6"
        )

        try:

            bridge = get_bridge()

            if bridge.running:

                if bridge.connected:

                    box.label(
                        text="Controller: CONNECTED",
                        icon="CHECKMARK",
                    )

                else:

                    box.label(
                        text="Controller: DISCONNECTED",
                        icon="ERROR",
                    )

                box.operator(
                    "scn6.initialize",
                    text="Ping / Initialize",
                    icon="LINKED",
                )

            else:

                box.label(
                    text="Bridge: OFFLINE",
                    icon="ERROR",
                )

                box.operator(
                    "scn6.initialize",
                    text="Start Bridge",
                    icon="LINKED",
                )

        except Exception:

            box.label(
                text="Bridge: UNKNOWN",
                icon="ERROR",
            )

            box.operator(
                "scn6.initialize",
                text="Initialize SCN6",
                icon="LINKED",
            )

        # ---------------------------------------------------------------
        # SAFETY
        # ---------------------------------------------------------------

        box = layout.box()

        box.label(
            text="Safety"
        )

        box.prop(
            self,
            "enabled",
            text="Enabled",
        )

        row = box.row()

        if self.armed:

            row.alert = True

            row.prop(
                self,
                "armed",
                text="ARMED",
                toggle=True,
            )

        else:

            row.prop(
                self,
                "armed",
                text="ARM",
                toggle=True,
            )

        # ---------------------------------------------------------------
        # CURRENT VALUES
        # ---------------------------------------------------------------

        layout.separator()

        try:

            source = self.get_source_value()

            command = self.calculate_command()

        except Exception:

            source = 0.0
            command = 0.0

        layout.label(
            text=f"Source: {source:.4f}"
        )

        layout.label(
            text=f"Command: {command:.3f}"
        )

        if self.command_clamped:

            row = layout.row()

            row.alert = True

            row.label(
                text="COMMAND CLAMPED",
                icon="ERROR",
            )

        # ---------------------------------------------------------------
        # AXIS
        # ---------------------------------------------------------------

        layout.label(
            text=f"Axis: {self.axis}"
        )

        # ---------------------------------------------------------------
        # ARM STATUS
        # ---------------------------------------------------------------

        if self.armed:

            layout.label(
                text="MOTION ENABLED",
                icon="REC",
            )

        else:

            layout.label(
                text="Motion disarmed",
                icon="PAUSE",
            )

    # =========================================================================
    # LABEL
    # =========================================================================

    def draw_label(self):

        if self.target_object:

            return (
                f"SCN6 {self.axis} "
                f"< {self.target_object.name} "
                f"{self.source}"
            )

        return f"SCN6 Axis {self.axis}"


# ============================================================================
# NODE TREE
# ============================================================================

class SCN6NodeTree(NodeTree):

    bl_idname = "SCN6NodeTree"
    bl_label = "SCN6"
    bl_icon = "PLUGIN"


# ============================================================================
# FIND SCN6 NODES
# ============================================================================

def get_scn6_nodes():

    result = []

    try:

        for node_group in bpy.data.node_groups:

            try:

                for node in node_group.nodes:

                    if (
                        node.bl_idname
                        == SCN6AxisNode.bl_idname
                    ):

                        result.append(node)

            except Exception:

                continue

    except Exception:

        pass

    return result


# ============================================================================
# TRAJECTORY TIMER
# ============================================================================

def scn6_trajectory_timer():

    try:

        nodes = get_scn6_nodes()

        for node in nodes:

            try:

                node.update_command()

            except Exception as exc:

                print(
                    "[SCN6] node update error:",
                    exc,
                )

    except Exception as exc:

        print(
            "[SCN6] trajectory timer error:",
            exc,
        )

    # 50 Hz
    return 0.02


# ============================================================================
# MENU
# ============================================================================

def scn6_node_menu(
    self,
    context,
):

    try:

        self.layout.operator(
            "node.add_node",
            text="SCN6 Axis",
            icon="DRIVER",
        ).type = SCN6AxisNode.bl_idname

    except Exception:

        pass


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    SCN6ValueSocket,
    SCN6AxisNode,
    SCN6NodeTree,
    SCN6_OT_Initialize,
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

        bpy.types.NODE_MT_add.remove(
            scn6_node_menu
        )

    except Exception:

        pass

    bpy.types.NODE_MT_add.append(
        scn6_node_menu
    )

    try:

        if not bpy.app.timers.is_registered(
            scn6_trajectory_timer
        ):

            bpy.app.timers.register(
                scn6_trajectory_timer,
                first_interval=0.1,
                persistent=False,
            )

    except Exception as exc:

        print(
            "[SCN6] trajectory timer registration error:",
            exc,
        )

    print(
        "[SCN6] scn6_node_v4 registered."
    )


def unregister():

    try:

        bpy.types.NODE_MT_add.remove(
            scn6_node_menu
        )

    except Exception:

        pass

    try:

        if bpy.app.timers.is_registered(
            scn6_trajectory_timer
        ):

            bpy.app.timers.unregister(
                scn6_trajectory_timer
            )

    except Exception:

        pass

    for cls in reversed(classes):

        try:

            bpy.utils.unregister_class(cls)

        except Exception:

            pass

    print(
        "[SCN6] scn6_node_v4 unregistered."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    register()
