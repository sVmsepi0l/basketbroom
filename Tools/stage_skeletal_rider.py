"""UE5.8-only skeletal rider authoring; importing this module changes nothing.

inspect() reads installed Epic template files only (also works outside Unreal).
build() explicitly stages the bounded stock package set and authors one original
seated flight animation. It never changes maps, actors, runtime code, or rules.
Stock meshes/materials remain Epic assets; only the flight pose is ours.

First execution needs editor/render validation. Do not describe source validation
or geometric pose checks as an approved character render or gameplay integration.
"""

from pathlib import Path
import hashlib
import json
import math
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "DevelopmentHarness"
ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8")
SOURCE = ENGINE / "Templates/TemplateResources/High/Characters/Content"
PREFIX = "/Game/Characters/Mannequins/"
MESH_PACKAGE = PREFIX + "Meshes/SKM_Quinn_Simple"
SKELETON_PACKAGE = PREFIX + "Meshes/SK_Mannequin"
ANIMATION_PACKAGE = "/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn"
GENERATOR = "Basketbroom.SeatedFlight.v1"
FPS, FRAMES = 30, 60

# These are serialized text references in Epic's installed body Control Rig, not
# proven hard dependencies. Report them; never copy another developer's content.
KNOWN_EDITOR_TEXT_REFERENCES = {
    "/Game/Developers/Jeremie/MetaHuman/FootRoll/FootRoll_A",
    "/Game/Developers/Jeremie/MetaHuman/IKSpine/IKSpine_A_003",
    "/Game/Developers/Jeremie/MetaHuman/MetaHuman_ControlRig_Functions",
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect():
    """Conservative serialized-name inventory, not an Asset Registry substitute."""
    pending, rows, text_only = [MESH_PACKAGE], {}, set()
    while pending:
        package = pending.pop()
        if package in rows:
            continue
        if not package.startswith(PREFIX):
            if package in KNOWN_EDITOR_TEXT_REFERENCES:
                text_only.add(package)
                continue
            raise RuntimeError("Unexpected external stock package reference: " + package)
        source = SOURCE / (package.removeprefix("/Game/Characters/") + ".uasset")
        if not source.is_file():
            raise RuntimeError("Installed UE5.8 template dependency missing: " + str(source))
        data = source.read_bytes()
        refs = sorted({value.decode("ascii") for value in
                       re.findall(rb"/Game/[A-Za-z0-9_/]+", data)})
        files = [source] + [source.with_suffix(suffix) for suffix in (".ubulk", ".uexp")
                            if source.with_suffix(suffix).is_file()]
        rows[package] = {
            "package": package, "source": str(source), "bytes": sum(p.stat().st_size for p in files),
            "sha256": hashlib.sha256(data).hexdigest(), "serialized_package_names": refs,
            "files": [str(p) for p in files],
        }
        pending.extend(ref for ref in refs if ref not in rows)
    return {"status": "source_inventory_only", "engine": str(ENGINE),
            "package_count": len(rows), "bytes": sum(row["bytes"] for row in rows.values()),
            "packages": [rows[key] for key in sorted(rows)],
            "unresolved_editor_text_references": sorted(text_only),
            "asset_registry_validation": "not_run", "assets_copied": 0,
            "animation_authored": False, "runtime_integrated": False}


def _editor():
    import unreal
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("This authoring tool targets installed Unreal Engine 5.8 only")
    current = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if current != PROJECT.resolve():
        raise RuntimeError("Open BasketbroomDev in UE5.8; refusing to author in " + str(current))
    if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("Stop PIE before authoring skeletal rider assets")
    return unreal


def _stage_stock(ue, inventory):
    """Keep original /Game mount paths; never overwrite a differing local asset."""
    copies = []
    for row in inventory["packages"]:
        for filename in row["files"]:
            source = Path(filename)
            relative = source.relative_to(SOURCE)
            target = PROJECT / "Content/Characters" / relative
            if target.exists() and _sha(target) != _sha(source):
                raise RuntimeError("Existing stock asset differs; inspect before replacing: " + str(target))
            copies.append((source, target))
    created = []
    for source, target in copies:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            created.append(str(target))
    registry = ue.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([PREFIX.rstrip("/")], force_rescan=True)
    options = ue.AssetRegistryDependencyOptions(
        include_soft_package_references=False, include_hard_package_references=True,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False)
    packages = {row["package"] for row in inventory["packages"]}
    for package in sorted(packages):
        for dependency in registry.get_dependencies(package, options):
            name = str(dependency)
            if name.startswith("/Game/") and name not in packages:
                raise RuntimeError("Stock hard dependency was not staged: " + name)
    return created


# Small explicit quaternion/vector operations avoid assuming mannequin bone axes.
def _v(value):
    return (float(value.x), float(value.y), float(value.z))


def _q(value):
    return (float(value.x), float(value.y), float(value.z), float(value.w))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _mul(a, scalar):
    return tuple(x * scalar for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    size = _length(a)
    if size < 1e-8:
        raise RuntimeError("Degenerate direction in seated pose authoring")
    return _mul(a, 1.0 / size)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _qmul(a, b):
    av, bv = a[:3], b[:3]
    xyz = _add(_add(_mul(bv, a[3]), _mul(av, b[3])), _cross(av, bv))
    return _unit((*xyz, a[3]*b[3]-_dot(av, bv)))


def _axis_angle(axis, degrees):
    angle = math.radians(degrees) / 2.0
    return (*_mul(_unit(axis), math.sin(angle)), math.cos(angle))


def _between(a, b):
    a, b = _unit(a), _unit(b)
    dot = max(-1.0, min(1.0, _dot(a, b)))
    if dot < -0.99999:
        axis = _cross(a, (0.0, 0.0, 1.0))
        if _length(axis) < 1e-5:
            axis = _cross(a, (0.0, 1.0, 0.0))
        return _axis_angle(axis, 180.0)
    return _unit((*_cross(a, b), 1.0 + dot))


class _Pose:
    """Keep the reflected in/out struct returned by the Python binding."""
    def __init__(self, value):
        self.value = value


def _transform(ue, pose, bone, local=False):
    space = ue.AnimPoseSpaces.LOCAL if local else ue.AnimPoseSpaces.WORLD
    return ue.AnimPoseExtensions.get_bone_pose(pose.value, bone, space)


def _position(ue, pose, bone):
    return _v(_transform(ue, pose, bone).translation)


def _set_world(ue, pose, bone, rotation=None, translation=None):
    transform = _transform(ue, pose, bone)
    if rotation is not None:
        transform.rotation = ue.Quat(*rotation)
    if translation is not None:
        transform.translation = ue.Vector(*translation)
    # Preserve the returned in/out value; Python may marshal this struct by value.
    result = ue.AnimPoseExtensions.set_bone_pose(pose.value, transform, bone, ue.AnimPoseSpaces.WORLD)
    if result is not None:
        pose.value = result


def _rotate(ue, pose, bone, delta):
    current = _q(_transform(ue, pose, bone).rotation)
    _set_world(ue, pose, bone, rotation=_qmul(delta, current))


def _aim(ue, pose, bone, child, target):
    start = _position(ue, pose, bone)
    delta = _between(_sub(_position(ue, pose, child), start), _sub(target, start))
    _rotate(ue, pose, bone, delta)


def _two_bone(ue, pose, first, middle, end, target, pole):
    start = _position(ue, pose, first)
    a = _length(_sub(_position(ue, pose, middle), start))
    b = _length(_sub(_position(ue, pose, end), _position(ue, pose, middle)))
    to_target = _sub(target, start)
    requested = _length(to_target)
    distance = max(abs(a-b)+.1, min(requested, (a+b)*.985))
    axis = _unit(to_target)
    bend = _unit(_sub(pole, _mul(axis, _dot(pole, axis))))
    along = (a*a - b*b + distance*distance) / (2.0*distance)
    height = math.sqrt(max(0.0, a*a-along*along))
    joint = _add(start, _add(_mul(axis, along), _mul(bend, height)))
    achieved_target = _add(start, _mul(axis, distance))
    _aim(ue, pose, first, middle, joint)
    _aim(ue, pose, middle, end, achieved_target)
    error = _length(_sub(_position(ue, pose, end), target))
    if error > 8.0:
        raise RuntimeError("Grip/foot target exceeds anatomical reach: " + json.dumps({
            "bone": end, "error_cm": error, "start": start, "target": target,
            "segment_lengths_cm": (a, b), "requested_distance_cm": requested}))
    return error


def _seated_pose(ue, skeleton, frame):
    pose = _Pose(ue.AnimPoseExtensions.get_reference_pose(skeleton))
    if not ue.AnimPoseExtensions.is_valid(pose.value):
        raise RuntimeError("Mannequin reference pose is invalid")
    bones = [str(name) for name in ue.AnimPoseExtensions.get_bone_names(pose.value)]
    required = ["root", "pelvis", "head"] + [name+side for side in ("_l", "_r")
        for name in ("thigh", "calf", "foot", "ball", "upperarm", "lowerarm", "hand")]
    missing = sorted(set(required)-set(bones))
    if missing:
        raise RuntimeError("Mannequin bones missing: " + ", ".join(missing))
    # Derive facing from the reference feet instead of guessing +/-X or +/-Y.
    feet_forward = _add(_sub(_position(ue, pose, "ball_l"), _position(ue, pose, "foot_l")),
                        _sub(_position(ue, pose, "ball_r"), _position(ue, pose, "foot_r")))
    _rotate(ue, pose, "root", _between((feet_forward[0], feet_forward[1], 0), (1, 0, 0)))
    _set_world(ue, pose, "pelvis", translation=(0, 0, 8))
    original_feet = {side: _q(_transform(ue, pose, "foot"+side).rotation) for side in ("_l", "_r")}
    breath = math.sin(2.0*math.pi*frame/FRAMES)
    spines = [bone for bone in ("spine_01", "spine_02", "spine_03", "spine_04", "spine_05") if bone in bones]
    if not spines:
        raise RuntimeError("Mannequin has no spine chain")
    for bone in spines:
        _rotate(ue, pose, bone, _axis_angle((0, 1, 0), (30.0 + .65*breath)/len(spines)))
    _rotate(ue, pose, "head", _axis_angle((0, 1, 0), -26.0 - .4*breath))
    errors = {}
    for side in ("_l", "_r"):
        sign = -1.0 if _position(ue, pose, "thigh"+side)[1] < 0 else 1.0
        errors["foot"+side] = _two_bone(ue, pose, "thigh"+side, "calf"+side, "foot"+side,
            (26, sign*22, -53), (1, sign*.12, 0))
        _set_world(ue, pose, "foot"+side,
                   rotation=_qmul(_axis_angle((0, 1, 0), -8), original_feet[side]))
        errors["hand"+side] = _two_bone(ue, pose, "upperarm"+side, "lowerarm"+side, "hand"+side,
            (46, sign*9, 10), (0, sign, -.25))
    return pose, bones, errors


def _check_pose(ue, pose):
    checks = {}
    for side in ("_l", "_r"):
        hip, knee, foot = [_position(ue, pose, name+side) for name in ("thigh", "calf", "foot")]
        angle = math.degrees(math.acos(max(-1, min(1, _dot(_unit(_sub(hip, knee)), _unit(_sub(foot, knee)))))))
        checks["knee_angle_degrees"+side] = angle
        checks["knee_forward_cm"+side] = knee[0]-hip[0]
        if not 45 < angle < 145 or knee[0]-hip[0] < 15 or hip[2]-foot[2] < 25:
            raise RuntimeError("Generated pose is not a bent-knee seated flight pose: " + str(checks))
    checks["pelvis_cm"] = _position(ue, pose, "pelvis")
    checks["head_cm"] = _position(ue, pose, "head")
    checks["hand_l_cm"] = _position(ue, pose, "hand_l")
    checks["hand_r_cm"] = _position(ue, pose, "hand_r")
    return checks


def _team_materials(ue):
    """Derived stock material instances: team paint, restrained metal, no UE logo."""
    outputs = {}
    lib = ue.MaterialEditingLibrary
    for team, color in (("Teal", (.03, .34, .40)), ("Copper", (.56, .20, .065))):
        outputs[team] = []
        for index in (1, 2):
            parent = ue.EditorAssetLibrary.load_asset(PREFIX + "Materials/Quinn/MI_Quinn_0" + str(index))
            name = "MI_BB_Quinn_" + team + "_0" + str(index)
            directory = "/Basketbroom/Art/Characters"
            path = directory + "/" + name
            material = ue.EditorAssetLibrary.load_asset(path) if ue.EditorAssetLibrary.does_asset_exist(path) else None
            if material and ue.EditorAssetLibrary.get_metadata_tag(material, "BB.Generator") != GENERATOR:
                raise RuntimeError("Refusing to replace unrelated material: " + path)
            if material is None:
                material = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, directory,
                    ue.MaterialInstanceConstant, ue.MaterialInstanceConstantFactoryNew())
            if not isinstance(material, ue.MaterialInstanceConstant):
                raise RuntimeError("Could not create derived team material: " + path)
            # The newer uniform author owns this material's appearance while
            # preserving the original runtime paths and instance ownership.
            # Rebuilding the seated loop must not repaint those garments.
            if ue.EditorAssetLibrary.get_metadata_tag(material, "BB.UniformGenerator") == "Basketbroom.PlayerUniform.v1":
                uniform_parent = material.get_editor_property("parent")
                if uniform_parent is None or uniform_parent.get_path_name().split(".")[0] != "/Basketbroom/Art/Characters/M_BB_WovenFlightUniform":
                    raise RuntimeError("Uniform instance has an unexpected parent: " + path)
                outputs[team].append(path)
                continue
            ue.EditorAssetLibrary.set_metadata_tag(material, "BB.Generator", GENERATOR)
            lib.set_material_instance_parent(material, parent)
            if "Paint Tint" not in [str(v) for v in lib.get_vector_parameter_names(parent)]:
                raise RuntimeError("Stock material paint parameter missing")
            # UE5.8's vector setter returns false unconditionally in its C++
            # implementation. Verify the resulting value instead of that flag.
            lib.set_material_instance_vector_parameter_value(material, "Paint Tint", ue.LinearColor(*color, 1))
            actual = lib.get_material_instance_vector_parameter_value(material, "Paint Tint")
            if max(abs(a-b) for a, b in zip((actual.r, actual.g, actual.b), color)) > 1e-5:
                raise RuntimeError("Team paint value did not persist")
            for parameter, value in (("MetalPaintRoughness", .68), ("MetalPaintMetallic", .18)):
                if parameter not in [str(v) for v in lib.get_scalar_parameter_names(parent)]:
                    raise RuntimeError("Stock material scalar parameter missing: " + parameter)
                lib.set_material_instance_scalar_parameter_value(material, parameter, value)
                if abs(lib.get_material_instance_scalar_parameter_value(material, parameter)-value) > 1e-5:
                    raise RuntimeError("Material scalar did not persist: " + parameter)
            if "Logo?" not in [str(v) for v in lib.get_static_switch_parameter_names(parent)]:
                raise RuntimeError("Stock material logo switch missing")
            lib.set_material_instance_static_switch_parameter_value(material, "Logo?", False)
            if lib.get_material_instance_static_switch_parameter_value(material, "Logo?"):
                raise RuntimeError("Stock logo switch did not turn off")
            lib.update_material_instance(material)
            if not ue.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
                raise RuntimeError("Could not save team material: " + path)
            outputs[team].append(path)
    return outputs


def build(replace_generated=False):
    """Explicit editor mutation: stock packages + one owned seated animation only."""
    ue = _editor()
    inventory = inspect()
    existing = ue.EditorAssetLibrary.load_asset(ANIMATION_PACKAGE) if ue.EditorAssetLibrary.does_asset_exist(ANIMATION_PACKAGE) else None
    if existing and (not replace_generated or
                     ue.EditorAssetLibrary.get_metadata_tag(existing, "BB.Generator") != GENERATOR):
        raise RuntimeError("Animation exists; only explicitly replace this generator's own output")
    copied = _stage_stock(ue, inventory)
    mesh = ue.EditorAssetLibrary.load_asset(MESH_PACKAGE)
    skeleton = ue.EditorAssetLibrary.load_asset(SKELETON_PACKAGE)
    if not isinstance(mesh, ue.SkeletalMesh) or not isinstance(skeleton, ue.Skeleton):
        raise RuntimeError("Installed Simple mannequin mesh/skeleton did not load")
    if mesh.get_editor_property("skeleton") != skeleton:
        raise RuntimeError("Selected mesh has an unexpected skeleton")
    # Compute/validate every pose before mutating the animation package.
    tracks, sample_checks, max_reach_error = {}, {}, 0.0
    for frame in range(FRAMES+1):
        pose, bones, errors = _seated_pose(ue, skeleton, frame)
        max_reach_error = max(max_reach_error, *errors.values())
        checks = _check_pose(ue, pose)
        if frame in (0, FRAMES//4, FRAMES//2, FRAMES):
            sample_checks[str(frame)] = checks
        for bone in bones:
            transform = _transform(ue, pose, bone, local=True)
            values = (_v(transform.translation), _q(transform.rotation), _v(transform.scale3d))
            if not all(math.isfinite(value) for group in values for value in group):
                raise RuntimeError("Non-finite transform for " + bone)
            tracks.setdefault(bone, []).append(values)
    for bone, keys in tracks.items():
        if max(abs(a-b) for left, right in zip(keys[0], keys[-1]) for a, b in zip(left, right)) > 1e-4:
            raise RuntimeError("Flight loop has a discontinuity at " + bone)
    if any(keys != tracks["root"][0] for keys in tracks["root"]):
        raise RuntimeError("Flight loop unexpectedly animates the root")
    animation = existing
    if animation is None:
        factory = ue.AnimSequenceFactory()
        factory.set_editor_property("target_skeleton", skeleton)
        factory.set_editor_property("preview_skeletal_mesh", mesh)
        directory, name = ANIMATION_PACKAGE.rsplit("/", 1)
        animation = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, directory, ue.AnimSequence, factory)
    if not isinstance(animation, ue.AnimSequence):
        raise RuntimeError("Could not create the seated AnimSequence")
    # Mark ownership immediately, so a failed first authoring pass can be retried.
    ue.EditorAssetLibrary.set_metadata_tag(animation, "BB.Generator", GENERATOR)
    controller = animation.get_editor_property("controller")
    if controller is None:
        raise RuntimeError("AnimSequence factory did not initialize its data controller")
    controller.open_bracket("Author Basketbroom seated flight", False)
    try:
        controller.remove_all_bone_tracks(False)
        controller.set_frame_rate(ue.FrameRate(FPS, 1), False)
        controller.set_number_of_frames(ue.FrameNumber(FRAMES), False)
        for bone, keys in tracks.items():
            if not controller.add_bone_curve(bone, False):
                raise RuntimeError("Could not add bone curve: " + bone)
            positions = [ue.Vector(*key[0]) for key in keys]
            rotations = [ue.Quat(*key[1]) for key in keys]
            scales = [ue.Vector(*key[2]) for key in keys]
            if not controller.set_bone_track_keys(bone, positions, rotations, scales, False):
                raise RuntimeError("Could not populate bone curve: " + bone)
        # AnimSequenceFactory already initialized/notified this data model.
        # Closing the bracket broadcasts the edits and requests recompression.
    finally:
        controller.close_bracket(False)
    animation.set_editor_property("enable_root_motion", False)
    ue.EditorAssetLibrary.set_metadata_tag(animation, "BB.Generator", GENERATOR)
    ue.EditorAssetLibrary.set_metadata_tag(animation, "BB.SourceMesh", MESH_PACKAGE)
    ue.EditorAssetLibrary.set_metadata_tag(animation, "BB.Pose", "Original seated flight; Epic stock mesh")
    # Evaluate the actual authored animation through the public pose API.
    options = ue.AnimPoseEvaluationOptions()
    options.set_editor_property("should_retarget", False)
    options.set_editor_property("optional_skeletal_mesh", mesh)
    evaluated = _Pose(ue.AnimPoseExtensions.get_anim_pose_at_time(animation, .5, options))
    evaluated_checks = _check_pose(ue, evaluated)
    if not ue.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False):
        raise RuntimeError("Could not save the generated seated animation")
    team_materials = _team_materials(ue)
    report = {"status": "authored_pending_render_review", "engine": ue.SystemLibrary.get_engine_version(),
              "source_package_count": inventory["package_count"], "stock_files_copied": copied,
              "stock_source": str(SOURCE), "stock_mesh": MESH_PACKAGE, "animation": ANIMATION_PACKAGE,
              "frames": FRAMES, "keys_per_bone": FRAMES+1, "fps": FPS, "bone_tracks": len(tracks),
              "max_reach_error_cm": max_reach_error, "pose_samples": sample_checks,
              "evaluated_animation_pose": evaluated_checks, "maps_saved": 0, "runtime_integrated": False,
              "team_materials": team_materials,
              "finger_grip_authored": False, "render_review": "not_run", "packaged_validation": "not_run",
              "unresolved_editor_text_references": inventory["unresolved_editor_text_references"]}
    output = ROOT / ".local/skeletal-rider-staging.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    ue.log("BASKETBROOM SKELETAL RIDER: " + report["status"] + "; report=" + str(output))
    return report


def dispatch(args=None):
    """Bridge-safe default inventory; authoring requires operation='build'."""
    args = {} if args is None else args
    if not isinstance(args, dict):
        raise ValueError("BRIDGE_ARGS must be an object")
    operation = args.get("operation", "inspect")
    if operation == "inspect":
        report = inspect()
        return {key: value for key, value in report.items() if key != "packages"}
    if operation == "build":
        replace = args.get("replace_generated", False)
        if not isinstance(replace, bool):
            raise ValueError("replace_generated must be a boolean")
        report = build(replace_generated=replace)
        return {"status": report["status"], "animation": report["animation"],
                "stock_package_count": report["source_package_count"],
                "stock_files_copied": len(report["stock_files_copied"]),
                "bone_tracks": report["bone_tracks"], "max_reach_error_cm": report["max_reach_error_cm"],
                "report": str(ROOT / ".local/skeletal-rider-staging.json"),
                "render_review": report["render_review"], "runtime_integrated": False}
    raise ValueError("Unknown operation; choose inspect or explicitly build: " + str(operation))


if __name__ == "__main__":
    RESULT = dispatch(globals().get("BRIDGE_ARGS", {}))
    if "BRIDGE_ARGS" not in globals():
        print(json.dumps(RESULT, indent=2))
