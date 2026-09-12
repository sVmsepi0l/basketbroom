"""Public UE 5.8 authoring helpers for replicated Blueprint state.

These functions configure replication metadata; they do not turn existing local
gameplay into multiplayer. Use only for the standalone UE 5.8 project. Reliable
custom-event RPC flags and event parameters have no public Python setter in the
installed BlueprintEditorLibrary; see Docs/networking.md for the native route.
No protected-property edits, memory patches, or editor-only runtime logic.
"""
import unreal

from bp_graph import Graph


BEL = unreal.BlueprintEditorLibrary
_NO_DEFAULT = object()


def capabilities():
    """Describe the inspected installed API, without creating or editing assets."""
    return {
        "replicated_members": hasattr(BEL, "set_blueprint_variable_replication"),
        "rep_notify_members": hasattr(unreal, "BlueprintVariableReplication"),
        "actor_replication_defaults": True,
        "custom_event_rpc_flags_via_public_python": False,
        "custom_event_parameters_via_public_python": False,
        "multiplayer_runtime_validated": False,
        "rpc_authoring_routes": ["Blueprint editor Details UI",
                                 "compiled editor helper or native runtime class"],
    }


def set_member_replication(blueprint, name, notify=False):
    """Replicate an existing locally declared member; optionally create OnRep_.

    RepNotify auto-creates its function graph through BlueprintEditorLibrary.
    Author its presentation logic separately. The authoritative server must own
    writes to gameplay state; setting this metadata does not enforce that rule.
    """
    names = {str(item) for item in BEL.list_member_variable_names(blueprint, False)}
    if name not in names:
        raise ValueError("No locally declared Blueprint member: " + name)
    descriptor = BEL.get_member_variable_type(blueprint, name)
    # Use supported struct export rather than protected EdGraphPinType fields.
    exported = descriptor.export_text()
    if "ContainerType=Map" in exported or "ContainerType=Set" in exported:
        raise ValueError("Blueprint map/set replication is unsupported here: " + name)
    mode = (unreal.BlueprintVariableReplication.REP_NOTIFY if notify
            else unreal.BlueprintVariableReplication.REPLICATED)
    BEL.set_blueprint_variable_replication(blueprint, name, mode)
    observed = BEL.get_blueprint_variable_replication(blueprint, name)
    if observed != mode:
        raise RuntimeError("Could not configure replication for " + name)
    if notify:
        graph = BEL.find_graph(blueprint, "OnRep_" + name)
        if graph is None:
            raise RuntimeError("RepNotify graph was not created for " + name)
    return name


def replicated_member(graph, name, kind, default=_NO_DEFAULT, notify=False,
                      editable=False, category="Basketbroom|Network"):
    """Declare and configure a replicated member on a bp_graph.Graph."""
    if default is _NO_DEFAULT:
        graph.var(name, kind, editable=editable, category=category)
    else:
        graph.var(name, kind, default, editable=editable, category=category)
    return set_member_replication(graph.bp, name, notify=notify)


def on_rep_graph(blueprint, name):
    """Return the auto-created RepNotify graph for presentation-only handling."""
    mode = BEL.get_blueprint_variable_replication(blueprint, name)
    if mode != unreal.BlueprintVariableReplication.REP_NOTIFY:
        raise ValueError("Member does not use RepNotify: " + name)
    return Graph(blueprint, "OnRep_" + name)


def configure_actor_replication(blueprint, movement=False, always_relevant=False,
                                owner_only=False, save=False):
    """Compile and set public Actor CDO replication defaults, then read them back.

    movement=True replicates authoritative actor transforms. It does not add
    prediction or client-to-server movement to DefaultPawn. Network players
    should use ACharacter/CharacterMovement's native movement protocol.
    """
    if always_relevant and owner_only:
        raise ValueError("Choose always_relevant or owner_only, not both")
    Graph(blueprint).compile()
    cdo = unreal.get_default_object(blueprint.generated_class())
    if not isinstance(cdo, unreal.Actor):
        raise TypeError("Actor replication requires an Actor-derived Blueprint")
    blueprint.modify()
    cdo.modify()
    settings = {
        "bReplicates": True,
        "bReplicateMovement": bool(movement),
        "bAlwaysRelevant": bool(always_relevant),
        "bOnlyRelevantToOwner": bool(owner_only),
    }
    for name, value in settings.items():
        cdo.set_editor_property(name, value)
        if bool(cdo.get_editor_property(name)) != value:
            raise RuntimeError("Actor replication default did not persist in memory: " + name)
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(blueprint):
        raise RuntimeError("Could not save replicated Blueprint " + blueprint.get_path_name())
    return {"blueprint": blueprint.get_path_name(), "defaults": settings,
            "runtime_network_tested": False}
