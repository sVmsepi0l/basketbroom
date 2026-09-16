"""Small, checked wrappers around the UE 5.8 Blueprint graph editor API.

Run inside Unreal's editor Python interpreter. Runtime behavior is compiled into
Blueprints; this module is an authoring tool, not a runtime dependency.

    g = Graph(bp)
    g.var("Score", "int", 0)
    start = g.event("ReceiveBeginPlay")
    update = g.set("Score", 0)
    message = g.call("/Script/Engine.KismetSystemLibrary.PrintString",
                     InString="Basketbroom ready")
    g.chain(start, update, message)
    g.compile()

Node and pin objects remain native Unreal objects. Pass an output pin (or a
single-result node) as an input value to connect it, or a literal to set it.
"""

import json
from pathlib import Path

import unreal


_UNSET = object()
BEL = unreal.BlueprintEditorLibrary
PINS = unreal.BlueprintGraphPinLibrary
_BLUEPRINT_SETTINGS = None


def _trace(operation, **details):
    """Record the last editor API operation, including if native code crashes."""
    path = Path(__file__).resolve().parents[1] / ".local" / "last-graph-operation.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"operation": operation, **details}, default=str), encoding="utf-8")


def _add_typed_function_call(editor, function):
    """Spawn the requested UFunction without UE 5.8's operator-spawner cache.

    UBlueprintFunctionNodeSpawner::Create caches promotable math spawners in
    FTypePromotion's raw-pointer map. A Blueprint compile can collect a spawner
    created by this scripting API, leaving the next call to invoke a stale
    pointer. These scripts already specify typed UFunctions, so use their
    concrete nodes. The preference is restored immediately and never saved.
    """
    global _BLUEPRINT_SETTINGS
    if _BLUEPRINT_SETTINGS is None:
        settings_class = unreal.load_class(None, "/Script/BlueprintGraph.BlueprintEditorSettings")
        if settings_class is None:
            raise RuntimeError("Cannot load Blueprint editor settings for typed function calls")
        _BLUEPRINT_SETTINGS = unreal.get_default_object(settings_class)
    settings = _BLUEPRINT_SETTINGS
    # This MinimalAPI settings class has no generated Python wrapper; use the
    # reflected C++ property name rather than a generated snake_case alias.
    promote = settings.get_editor_property("bEnableTypePromotion")
    if not promote:
        return editor.add_call_function_node(function)
    # Default notifications rebuild the entire action database; no UI or config
    # notification is needed for this synchronous, temporary spawn override.
    notify = unreal.PropertyAccessChangeNotifyMode.NEVER
    settings.set_editor_property("bEnableTypePromotion", False, notify_mode=notify)
    try:
        return editor.add_call_function_node(function)
    finally:
        settings.set_editor_property("bEnableTypePromotion", promote, notify_mode=notify)


def create_blueprint(asset_path, parent_class=unreal.Actor):
    """Create a new Blueprint at a full /Game or plugin asset path."""
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        raise ValueError("Asset already exists: " + asset_path)
    cls = parent_class if isinstance(parent_class, unreal.Class) else parent_class.static_class()
    blueprint = BEL.create_blueprint_asset_with_parent(asset_path, cls)
    if blueprint is None:
        # A failed earlier load can leave an empty package in memory. The native
        # helper rejects any existing package; the standard factory supports it.
        package_path, _, asset_name = asset_path.rpartition("/")
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", cls)
        blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name, package_path, unreal.Blueprint, factory)
        if blueprint is None:
            raise RuntimeError("Could not create Blueprint " + asset_path)
    return blueprint


def literal(value):
    """Return Unreal's import-text representation, without quoting pin strings."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (tuple, list)):
        # Convenient vector/rotation literals; use Unreal structs for other types.
        if len(value) == 3:
            return "(X={},Y={},Z={})".format(*value)
        if len(value) == 2:
            return "(X={},Y={})".format(*value)
        raise ValueError("Use an Unreal struct or explicit import-text for this literal")
    if hasattr(value, "export_text"):
        return value.export_text()
    if isinstance(value, unreal.Object):
        return value.get_path_name()
    raise TypeError("Unsupported Blueprint literal: {!r}".format(value))


def pin_type(kind):
    """Resolve a primitive name, Unreal struct/class, or existing pin type."""
    if isinstance(kind, unreal.EdGraphPinType):
        return kind
    if isinstance(kind, unreal.BlueprintGraphPin):
        return PINS.get_pin_type(kind)
    if isinstance(kind, str):
        aliases = {"boolean": "bool", "float": "real", "double": "real",
                   "integer": "int", "str": "string"}
        name = aliases.get(kind.lower(), kind.lower())
        if name in {"bool", "byte", "int", "int64", "real", "name", "string", "text"}:
            return BEL.get_basic_type_by_name(name)
        structs = {"vector": unreal.Vector, "vector2d": unreal.Vector2D,
                   "rotator": unreal.Rotator, "transform": unreal.Transform,
                   "linearcolor": unreal.LinearColor, "color": unreal.Color}
        if name in structs:
            return BEL.get_struct_type(structs[name].static_struct())
        raise ValueError("Unknown pin type {!r}; pass a class, struct or EdGraphPinType".format(kind))
    if isinstance(kind, unreal.Class):
        return BEL.get_object_reference_type(kind)
    if isinstance(kind, unreal.ScriptStruct):
        return BEL.get_struct_type(kind)
    if hasattr(kind, "static_struct"):
        return BEL.get_struct_type(kind.static_struct())
    if hasattr(kind, "static_class"):
        return BEL.get_object_reference_type(kind.static_class())
    raise TypeError("Unsupported Blueprint pin type: {!r}".format(kind))


def _require_pin(pin, label):
    if pin is None or not PINS.is_valid(pin):
        raise ValueError("Missing Blueprint pin: " + label)
    return pin


def _node_name(node):
    return "{} ({})".format(node.get_name(), BEL.get_node_title(node))


def connect(source, destination):
    _require_pin(source, "source")
    _require_pin(destination, "destination")
    if not PINS.try_create_connection(source, destination):
        raise ValueError("Cannot connect {}.{} to {}.{}".format(
            _node_name(PINS.get_owning_node(source)), PINS.get_pin_name(source),
            _node_name(PINS.get_owning_node(destination)), PINS.get_pin_name(destination)))
    return destination


class Graph:
    def __init__(self, blueprint, name="EventGraph", editor=None):
        self.bp = blueprint
        self.editor = editor or unreal.BlueprintGraphEditor.get_graph_editor_by_name(blueprint, name)
        if self.editor is None:
            raise ValueError("Blueprint {} has no graph {!r}".format(blueprint.get_path_name(), name))
        self.name = str(self.editor.get_graph().get_name())
        self._index = len(self.editor.list_all_nodes())

    def _place(self, node, label="node", pos=None):
        if node is None:
            raise ValueError("Could not create {} in {}".format(label, self.name))
        if pos is None:
            pos = ((self._index % 8) * 320, (self._index // 8) * 260)
        BEL.set_node_pos(node, unreal.IntPoint(int(pos[0]), int(pos[1])))
        self._index += 1
        return node

    @staticmethod
    def input(node, name):
        return _require_pin(BEL.find_input_pin(node, name), _node_name(node) + "." + str(name))

    @staticmethod
    def output(node, name="ReturnValue"):
        return _require_pin(BEL.find_output_pin(node, name), _node_name(node) + "." + str(name))

    out = output

    @staticmethod
    def result(node):
        return _require_pin(BEL.find_result_pin(node), _node_name(node) + ".result")

    @staticmethod
    def value(pin, value):
        """Wire a pin/node value, or assign a checked literal default."""
        _require_pin(pin, "value destination")
        if isinstance(value, unreal.BlueprintGraphPin):
            connect(value, pin)
        elif isinstance(value, unreal.K2Node):
            connect(Graph.result(value), pin)
        elif not PINS.set_pin_value(pin, literal(value)):
            raise ValueError("Invalid value {!r} for {}.{}".format(
                value, _node_name(PINS.get_owning_node(pin)), PINS.get_pin_name(pin)))
        return pin

    def inputs(self, node, **values):
        # Promotable math operators start with wildcard pins. Establish connected
        # operand types before assigning constants (e.g. -380 * DeltaSeconds).
        items = sorted(values.items(), key=lambda item: not isinstance(
            item[1], (unreal.BlueprintGraphPin, unreal.K2Node)))
        for name, value in items:
            pin = BEL.find_self_pin(node) if name == "target" else self.input(node, name)
            value = self._numeric_input(pin, value)
            self.value(pin, value)
        return node

    def _numeric_input(self, destination, value):
        """Author explicit scalar casts for concrete numeric function inputs.

        Promotable operators used to hide these conversions. The scripting
        connection API does not reliably insert Blueprint autocast nodes, so
        the concrete functions need integer-to-real casts here. Unreal handles
        float/double precision conversion directly between real pins.
        Integer narrowing/rounding remains an explicit authoring decision.
        """
        if isinstance(value, unreal.K2Node):
            value = self.result(value)
        if not isinstance(value, unreal.BlueprintGraphPin):
            return value

        def kind(pin):
            # FEdGraphPinType's members are protected in Python. The scripting
            # API exposes its public JSON schema and human-readable type label.
            schema_text = PINS.get_pin_type_as_json_schema(pin)
            schema = json.loads(schema_text) if schema_text else {}
            category = schema.get("type")
            if category == "number":
                return "double"  # Covers real float/double pins alike.
            if category != "integer":
                return None  # Includes containers, objects and wildcards.
            display = str(PINS.get_pin_type_display_string(pin)).lower()
            if "64" in display or schema.get("format") == "int64":
                return "int64"
            if "byte" in display:
                return "byte"
            return "int"

        source_kind, target_kind = kind(value), kind(destination)
        if source_kind == target_kind:
            return value
        conversion = {
            ("int", "double"): ("Conv_IntToDouble", "InInt"),
            ("int64", "double"): ("Conv_Int64ToDouble", "InInt"),
            ("byte", "double"): ("Conv_ByteToDouble", "InByte"),
            ("int", "int64"): ("Conv_IntToInt64", "InInt"),
        }.get((source_kind, target_kind))
        if conversion is not None:
            function, input_name = conversion
            value = self.result(self.call("/Script/Engine.KismetMathLibrary." + function,
                                          **{input_name: value}))
        return value

    def call(self, function, **values):
        """Add a call by full UFunction path or local Blueprint function name."""
        details = dict(function=function, inputs=list(values),
                       blueprint=self.bp.get_path_name(), graph=self.name)
        _trace("call.spawn", **details)
        node = _add_typed_function_call(self.editor, function)
        _trace("call.place", **details)
        node = self._place(node, "function " + function)
        _trace("call.inputs", node=node.get_name(), **details)
        self.inputs(node, **values)
        _trace("call.complete", node=node.get_name(), **details)
        return node

    def node(self, category_and_name, context=(), declaring_class=None, **values):
        """Add an action using its exact no-spaces Category|Name identifier."""
        _trace("node", name=category_and_name, inputs=list(values), blueprint=self.bp.get_path_name(), graph=self.name)
        node = self.editor.create_node_from_name(
            category_and_name, unreal.Vector2D(0, 0), list(context), declaring_class)
        return self.inputs(self._place(node, category_and_name), **values)

    def macro(self, path, **values):
        return self.inputs(self._place(self.editor.add_macro_node(path), "macro " + path), **values)

    def event(self, name, pos=None):
        """Get/create an inherited event using its internal name (ReceiveTick)."""
        _trace("event", name=name, blueprint=self.bp.get_path_name(), graph=self.name)
        if self.name != "EventGraph":
            raise ValueError("Inherited events must be authored in EventGraph")
        node = BEL.add_event_override(self.bp, name, unreal.IntPoint(0, 0))
        return self._place(node, "event " + name, pos)

    def custom_event(self, name):
        return self._place(self.editor.add_custom_event_node(name), "custom event " + name)

    def var(self, name, kind="bool", default=_UNSET, editable=False, category="Basketbroom"):
        names = [str(item) for item in BEL.list_member_variable_names(self.bp, False)]
        if name in names:
            raise ValueError("Member variable already exists: " + name)
        text = "" if default is _UNSET else literal(default)
        if not self.editor.add_member_variable(name, pin_type(kind), text):
            raise ValueError("Could not add member variable " + name)
        if editable:
            BEL.set_blueprint_variable_instance_editable(self.bp, name, True)
        if category:
            BEL.set_blueprint_variable_category(self.bp, name, category)
        return name

    def get(self, name, target=_UNSET, class_path=""):
        node = self._place(self.editor.add_get_member_variable_node(name, class_path), "get " + name)
        if target is not _UNSET:
            self.value(BEL.find_self_pin(node), target)
        return self.output(node, name)

    def set(self, name, value=_UNSET, target=_UNSET, class_path=""):
        node = self._place(self.editor.add_set_member_variable_node(name, class_path), "set " + name)
        if value is not _UNSET:
            self.value(self.input(node, name), value)
        if target is not _UNSET:
            self.value(BEL.find_self_pin(node), target)
        return node

    def branch(self, condition=_UNSET):
        node = self._place(self.editor.add_branch_node(), "branch")
        if condition is not _UNSET:
            self.value(BEL.find_condition_pin(node), condition)
        return node

    def sequence(self, count=2):
        if count < 2:
            raise ValueError("Sequence needs at least two outputs")
        node = self.node("Utilities|FlowControl|Sequence")
        for _ in range(count - 2):
            if not self.editor.add_node_pin(node):
                raise ValueError("Could not add Sequence output")
        return node

    @staticmethod
    def exec(previous, following, out="then"):
        source = previous if isinstance(previous, unreal.BlueprintGraphPin) else Graph.output(previous, out)
        target = following if isinstance(following, unreal.BlueprintGraphPin) else BEL.find_execute_pin(following)
        connect(source, _require_pin(target, "execute"))
        return following

    @staticmethod
    def chain(*nodes):
        for previous, following in zip(nodes, nodes[1:]):
            Graph.exec(previous, following)
        return nodes[-1] if nodes else None

    def function(self, name, pure=False):
        if BEL.find_graph(self.bp, name) is not None:
            raise ValueError("Function graph already exists: " + name)
        editor = unreal.BlueprintGraphEditor.create_and_edit_function_graph(self.bp, name)
        graph = Graph(self.bp, name, editor)
        if pure:
            editor.set_is_pure_function(True)
        return graph

    def entry(self):
        return _require_pin(self.editor.find_graph_entry_pin(), self.name + " entry")

    def param(self, name, kind="bool", default=_UNSET):
        text = "" if default is _UNSET else literal(default)
        return _require_pin(self.editor.add_graph_input_parameter(name, pin_type(kind), text), name)

    def return_value(self, name, kind, value=_UNSET):
        node = self.editor.add_graph_output_parameter(name, pin_type(kind))
        if node is None:
            raise ValueError("Could not create return parameter " + name)
        if value is not _UNSET:
            self.value(self.input(node, name), value)
        return node

    def compile(self, save=False):
        _trace("compile", blueprint=self.bp.get_path_name(), graph=self.name, save=save)
        BEL.compile_blueprint(self.bp)
        errors = []
        for raw_graph in BEL.list_graphs(self.bp):
            editor = unreal.BlueprintGraphEditor.get_graph_editor(raw_graph)
            for node in editor.list_nodes_with_errors():
                errors.append("{}: {}".format(node.get_name(), node.get_editor_property("error_msg")))
        status = self.bp.get_editor_property("status")
        if errors or status == unreal.BlueprintStatus.BS_ERROR:
            raise RuntimeError("Blueprint compile failed: {}\n{}".format(self.bp.get_path_name(), "\n".join(errors)))
        if save and not unreal.EditorAssetLibrary.save_loaded_asset(self.bp):
            raise RuntimeError("Could not save " + self.bp.get_path_name())
        return self.bp

    def export_manifest(self, filename):
        """Export inspectable pin topology and member types; not a CK asset import."""
        members = []
        for name in BEL.list_member_variable_names(self.bp, False):
            kind = BEL.get_member_variable_type(self.bp, name)
            members.append({"name": str(name), "type": kind.export_text() if kind else None})
        nodes = []
        for node in self.editor.list_all_nodes():
            position = BEL.get_node_pos(node)
            pins = []
            for pin in BEL.list_all_pins(node):
                pins.append({"name": str(PINS.get_pin_name(pin)),
                             "direction": str(PINS.get_pin_direction(pin)),
                             "type": PINS.get_pin_type(pin).export_text(),
                             "value": PINS.get_pin_value(pin),
                             "links": [{"node": PINS.get_owning_node(other).get_name(),
                                        "pin": str(PINS.get_pin_name(other))}
                                       for other in PINS.list_connected_pins(pin)]})
            nodes.append({"name": node.get_name(), "class": node.get_class().get_path_name(),
                          "title": BEL.get_node_title(node), "position": [position.x, position.y],
                          "pins": pins})
        data = {"blueprint": self.bp.get_path_name(), "graph": self.name, "members": members, "nodes": nodes}
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


def export_t3d(obj, filename):
    """Export generic Unreal object text for inspection/CK migration experiments.

    UE5 binary assets are not compatible with Creator Kit. This textual export
    also needs deliberate type/function conversion and editor import validation.
    """
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    task = unreal.AssetExportTask()
    task.object = obj
    task.filename = str(filename)
    task.exporter = unreal.ObjectExporterT3D()
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    if not unreal.Exporter.run_asset_export_task(task):
        raise RuntimeError("Object text export failed: " + str(filename))
    return str(filename)
