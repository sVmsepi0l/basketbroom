"""Bounded +45% native arena amendment; default dry run, never a map rebuild.

Only the plan's original OBJ meshes and two owned maps may be saved. Actors are
moved in place; materials, native entry/exit and registration are preserved.
Immutable receipts extend, rather than overwrite, the earlier roof proof.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
import shutil
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "Mod/Basketbroom/Content"
MAPS = ("/Basketbroom/Maps/BB_Arena_Port", "/Basketbroom/Maps/Basketbroom_DungeonMap")
SUCCESS = ROOT / ".local/hlck/arena-expansion-success.json"
GENERATED_TAG = "BB.HLCK.ArenaPort.Generated.v1"
ENTRY_TAG = "BB.HLCK.Dungeon.Entry.v1"
DIM_KEYS = ("half_x", "half_y", "eave", "apex", "goal_x")


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.025 * (attempt + 1))


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_plan(plan):
    if plan.get("schema_version") != 1:
        raise ValueError("Unsupported native expansion plan")
    dimensions = module("_bb_expansion_dimensions", "Tools/arena_dimensions.py")
    for key, expected in (("dimensions_before", dimensions.dimensions(1.0)),
                          ("dimensions_after", dimensions.dimensions())):
        values = plan.get(key, {})
        if set(values) != set(DIM_KEYS) or any(not math.isfinite(values[name]) or abs(values[name] - expected[name]) > 0.0001 for name in DIM_KEYS):
            raise ValueError("Expansion plan dimensions differ from the reviewed +45% contract")
    ratio = dimensions.enclosed_volume_cm3(plan["dimensions_after"]) / dimensions.enclosed_volume_cm3(plan["dimensions_before"])
    if abs(ratio - 1.45) > 1e-9 or abs(plan.get("volume_ratio", 0) - ratio) > 1e-9:
        raise ValueError("Expansion does not add exactly 45% enclosed volume")
    entries = plan.get("changed_meshes", [])
    names = [entry["name"] for entry in entries]
    if not entries or len(names) != len(set(names)) or "SM_BB_PyramidCollision" not in names:
        raise ValueError("Expansion needs unique changed source meshes and its roof shell")
    for entry in entries:
        name = entry["name"]
        if not name.startswith("SM_BB_") or not name.replace("_", "").isalnum():
            raise ValueError("Invalid expansion mesh name")
        if entry["source"] != "SourceArt/Arena/" + name + ".obj" or entry["destination"] != "/Basketbroom/Art/Meshes/" + name:
            raise ValueError("Expansion source or destination is outside its original-mesh scope")
        if entry["sha256_before"] == entry["sha256_after"] or any(len(entry[key]) != 64 for key in ("sha256_before", "sha256_after")):
            raise ValueError("Each changed mesh needs distinct old/new source hashes")
    actors = plan.get("actors", [])
    labels = [entry["label"] for entry in actors]
    if len(actors) != 905 or len(labels) != len(set(labels)):
        raise ValueError("Plan must describe all 905 unique owned arena actors")
    for entry in actors:
        if not entry.get("class") or not isinstance(entry.get("tags"), list):
            raise ValueError("Actor identity must include class and authored tags")
        for phase in ("old", "new"):
            value = entry[phase]
            for key in ("location", "rotation", "scale"):
                if len(value[key]) != 3 or any(not math.isfinite(number) for number in value[key]):
                    raise ValueError("Actor transform is not finite")
            if any(number <= 0 for number in value["scale"]):
                raise ValueError("Refusing zero or inverted geometry scale")
        if entry["class"].endswith("PlayerStart") and entry["old"] != entry["new"]:
            raise ValueError("Native PlayerStart must retain its proved location")
    return plan


def build_plan():
    return validate_plan(module("_bb_native_expansion_plan", "Tools/arena_expansion_plan.py").build_plan())


def asset_file(package, plan):
    destinations = {entry["destination"] for entry in plan["changed_meshes"]}
    for destination in destinations:
        name = destination.rsplit("/", 1)[-1]
        if destination != "/Basketbroom/Art/Meshes/" + name or not name.startswith("SM_BB_") or not name.replace("_", "").isalnum():
            raise ValueError("Expansion package list contains a non-owned mesh destination")
    allowed = set(MAPS) | destinations
    if package not in allowed:
        raise ValueError("Package is outside the exact expansion allowlist: " + package)
    path = (CONTENT / (package[len("/Basketbroom/"):] + (".umap" if package in MAPS else ".uasset"))).resolve()
    path.relative_to(CONTENT.resolve())
    return path


def allowed_files(plan):
    return [asset_file(package, plan) for package in list(MAPS) + [entry["destination"] for entry in plan["changed_meshes"]]]


def map_file(path):
    if path not in MAPS:
        raise ValueError("Not an owned native expansion map")
    return CONTENT / (path[len("/Basketbroom/"):] + ".umap")


def _receipt(pointer, kind, seen):
    roots = {"resize": ".local/hlck/arena-resize-stage", "expansion": ".local/hlck/arena-expansion-stage",
             "roof": ".local/hlck/pyramid-net-stage"}
    if kind not in roots:
        raise RuntimeError("Unknown native amendment kind")
    root = (ROOT / roots[kind]).resolve()
    path = Path(pointer["report"]).resolve()
    path.relative_to(root)
    if path in seen or digest(path) != pointer["sha256"]:
        raise RuntimeError("Invalid or cyclic native map amendment receipt")
    seen.add(path)
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != "staged" or not report.get("preservation_verified"):
        raise RuntimeError("Only a completed, preserved native amendment is evidence")
    if kind == "resize":
        planner = module("_bb_verified_resize_plan", "Tools/arena_resize_plan.py")
        if (report.get("amendment_kind") != "arena_floor_area2_20260925"
                or report.get("materials_preserved") is not True
                or report.get("plan_sha256") != plan_hash(report["plan"])
                or report["plan"].get("engine") != "hlck" or not report.get("saved_package_hashes")
                or report.get("registration_before") != report.get("registration_after")
                or report.get("installed_assets_modified") is not False):
            raise RuntimeError("Resize lacks its exact plan/material/registration preservation contract")
        planner.validate_plan(report["plan"])
    elif kind == "expansion":
        if report.get("amendment_kind") != "arena_volume_45_percent" or report.get("materials_preserved") is not True or report.get("plan_sha256") != plan_hash(report["plan"]) or not report.get("saved_package_hashes"):
            raise RuntimeError("Expansion lacks its exact plan/material preservation contract")
    return path, report


def verified_resize_predecessor(item, predecessor, predecessor_plan):
    """Bridge a saved editor resave only when its complete snapshot is preserved.

    A different package hash alone is never sufficient. The hash-verified
    resize receipt must identify the exact earlier amendment, whose captured
    actor/component/material state must still match after its planned moves.
    """
    if item.get("prior_expansion_map_sha256") != predecessor.get("sha256_after"):
        raise RuntimeError("Resize does not identify its exact predecessor map")
    if item["sha256_before"] == predecessor["sha256_after"]:
        return False
    if (item.get("preexisting_saved_changes_since_expansion") is not True
            or item.get("game_mode_before") != predecessor.get("game_mode_before")):
        raise RuntimeError("Unproved pre-resize map change")
    prior = predecessor["actors_before"]
    selected = match_plan(prior, predecessor_plan, "old")
    compare_preservation(prior, item["actors_before"], selected)
    return True


def verified_amendment(path, original_sha256):
    """Verify resize -> expansion -> immutable roof backups to the original map.

    Roof-only worlds return None for the original roof verifier. Every linked
    predecessor map requires its verified byte backup, never just a claimed hash.
    """
    resize_success = ROOT / ".local/hlck/arena-resize-success.json"
    success = resize_success if resize_success.is_file() else SUCCESS
    if path not in MAPS or not success.is_file():
        return None
    pointer = json.loads(success.read_text(encoding="utf-8"))
    current_hash = digest(map_file(path))
    saved_hash = current_hash
    kind = "resize" if success == resize_success else "expansion"
    seen, expansions, roofs, resizes, resaves = set(), 0, 0, 0, 0
    latest = None
    while pointer:
        receipt_path, report = _receipt(pointer, kind, seen)
        items = [item for item in report["maps"] if item["path"] == path]
        if len(items) != 1 or items[0]["sha256_after"] != current_hash:
            raise RuntimeError("Saved native map differs from the exact amendment chain")
        item = items[0]
        backup = Path(item["backup"]).resolve()
        backup.relative_to(receipt_path.parent / "backups")
        if digest(backup) != item["sha256_before"] or not item.get("unrelated_actors_preserved"):
            raise RuntimeError("Amendment predecessor backup or preservation proof is invalid")
        if kind in ("resize", "expansion"):
            if not item.get("actor_identity_and_components_preserved") or not item.get("saved_reloaded") or not item.get("geometry_after", {}).get("passed"):
                raise RuntimeError("Expansion lacks saved actor/component and real collision proof")
            if kind == "resize":
                selected = match_plan(item["actors_before"], report["plan"], "old")
                compare_preservation(item["actors_before"], item["actors_after"], selected)
                match_plan(item["actors_after"], report["plan"], "new")
                resizes += 1
            else:
                expansions += 1
            if latest is None:
                expected_files = allowed_files(report["plan"])
                actual_files = report["saved_package_hashes"]
                if set(actual_files) != {str(file) for file in expected_files} or any(digest(file) != actual_files[str(file)] for file in expected_files):
                    raise RuntimeError("A saved expansion mesh/map differs from its verified package bytes")
                latest = {"report": str(receipt_path), "dimensions": report["plan"]["dimensions_after"],
                          "volume_ratio": report["plan"]["volume_ratio"], "plan_sha256": report["plan_sha256"]}
        else:
            roofs += 1
        if item["sha256_before"] == original_sha256:
            latest.update(current_sha256=saved_hash, original_sha256=original_sha256,
                          verified_expansions=expansions, verified_roof_amendments=roofs,
                          verified_resizes=resizes, verified_preserved_resaves=resaves)
            return latest
        current_hash = item["sha256_before"]
        if kind == "resize":
            pointer = report.get("prior_expansion_success")
            if pointer is None:
                raise RuntimeError("Resize lacks its verified expansion predecessor")
            # Verify now, then let the normal chain loop verify its backup and
            # earlier links. Use a detached seen set to preserve cycle checks.
            unused, prior = _receipt(pointer, "expansion", set(seen))
            prior_items = [row for row in prior["maps"] if row["path"] == path]
            if len(prior_items) != 1:
                raise RuntimeError("Resize predecessor map is ambiguous")
            predecessor = prior_items[0]
            resaves += int(verified_resize_predecessor(item, predecessor, prior["plan"]))
            current_hash = predecessor["sha256_after"]
            kind = "expansion"
        elif kind == "expansion":
            pointer = report.get("previous_success")
            if pointer is None:
                pointer, kind = report.get("predecessor_roof_success"), "roof"
        else:
            pointer = report.get("previous_success")
    return None


def roof_helper(dimensions):
    result = module("_bb_expansion_roof_audit", "Tools/stage_hlck_pyramid_net.py")
    result.HALF_X, result.HALF_Y = dimensions["half_x"], dimensions["half_y"]
    result.EAVE, result.APEX = dimensions["eave"], dimensions["apex"]
    return result


def snapshot(unreal, actors):
    helper = roof_helper(module("_bb_expansion_snapshot_dimensions", "Tools/arena_dimensions.py").dimensions())
    helper.targeted = lambda unused: False
    records = helper.snapshot(unreal, actors)
    for actor in actors:
        record = records[actor.get_path_name()]
        record["components_identity"] = sorted((component.get_name(), component.get_class().get_path_name())
                                                for component in actor.get_components_by_class(unreal.ActorComponent))
        if isinstance(actor, unreal.StaticMeshActor):
            component = actor.static_mesh_component
            record["static_component_settings"] = {key: str(component.get_editor_property(key)) for key in
                ("mobility", "cast_shadow", "visible", "hidden_in_game")}
            physical = component.get_editor_property("body_instance").get_editor_property("phys_material_override")
            record["physical_material"] = physical.get_path_name() if physical else None
        if isinstance(actor, unreal.TextRenderActor):
            component = actor.get_component_by_class(unreal.TextRenderComponent)
            record["text_settings"] = {key: str(component.get_editor_property(key)) for key in
                ("text", "world_size", "horizontal_alignment", "vertical_alignment")}
            color = component.get_editor_property("text_render_color")
            record["text_settings"]["text_render_color"] = {name: int(getattr(color, name)) for name in ("r", "g", "b", "a")}
    return records


def near(actual, expected, tolerance=0.02, angular=False):
    if len(actual) != len(expected):
        return False
    return all(abs(((a - b + 180) % 360 - 180) if angular else a - b) <= tolerance for a, b in zip(actual, expected))


def match_plan(records, plan, phase="old"):
    """Exact identity/legacy transform guard; a label alone never owns an actor."""
    generated = {path: record for path, record in records.items() if GENERATED_TAG in record["tags"]}
    if len(generated) != len(plan["actors"]):
        raise RuntimeError("Unexpected owned actor count; no broad arena rebuild is permitted")
    by_label = {}
    for path, record in generated.items():
        by_label.setdefault(record["label"], []).append((path, record))
    selected = {}
    for source_entry in plan["actors"]:
        entry = source_entry
        # DirectionalLight's native spawn default has scale 2.5, absent from
        # the source recorder. The immutable successful roof snapshots confirm
        # this exact one-actor default in both maps. Preserve it while moving
        # the light; geometry actors retain the unmodified source contract.
        if entry["label"] == "Twilight amber key" and entry["class"] == "/Script/Engine.DirectionalLight":
            if entry["old"]["scale"] != [1, 1, 1] or entry["new"]["scale"] != [1, 1, 1]:
                raise RuntimeError("Source key-light scale changed outside the native-default contract")
            entry = dict(entry)
            entry["old"], entry["new"] = dict(entry["old"]), dict(entry["new"])
            entry["old"]["scale"], entry["new"]["scale"] = [2.5, 2.5, 2.5], [2.5, 2.5, 2.5]
        candidates = list(by_label.get(entry["label"], []))
        if entry["label"] == "Continuous closed-arena rebound net":
            candidates += by_label.get("Continuous open-crown rebound net", [])
        legacy_beacons = {"Eave beacon %s %s" % (side, index): "Crown beacon %s %s" % (side, index)
                          for side in (-1, 1) for index in range(9)}
        if entry["label"] in legacy_beacons:
            candidates += by_label.get(legacy_beacons[entry["label"]], [])
        if len(candidates) != 1:
            raise RuntimeError("Expected a unique owned actor: " + entry["label"])
        path, record = candidates[0]
        if record["class"] != entry["class"]:
            raise RuntimeError("Unexpected native actor class: " + entry["label"])
        # The registered dungeon's verified original stage placed its fog at
        # origin. Preserve that exact native adaptation; do not move it back
        # to the standalone/port builder's -800 cm presentation setting.
        if entry["label"] == "Aerial depth" and entry["class"] == "/Script/Engine.ExponentialHeightFog":
            if (entry["old"]["location"] != [0, 0, -800] or entry["new"]["location"] != [0, 0, -800]
                    or record["location"] not in ([0, 0, -800], [0, 0, 0])):
                raise RuntimeError("Source fog moved outside the reviewed native reload adaptation")
            entry = dict(entry)
            entry["old"], entry["new"] = dict(entry["old"]), dict(entry["new"])
            entry["old"]["location"], entry["new"]["location"] = list(record["location"]), list(record["location"])
        expected_tags = {GENERATED_TAG} | set(entry["tags"])
        if record["class"].endswith("PlayerStart") and path.startswith(MAPS[1] + "."):
            expected_tags.add(ENTRY_TAG)
        if set(record["tags"]) != expected_tags:
            raise RuntimeError("Unexpected actor ownership/tags: " + entry["label"])
        for field in ("location", "rotation", "scale"):
            if not near(record[field], entry[phase][field], angular=field == "rotation"):
                raise RuntimeError("Unexpected %s %s for %s: %s vs %s" % (phase, field, entry["label"], record[field], entry[phase][field]))
        if entry.get("mesh"):
            expected_mesh = ("/Engine/BasicShapes/" if not entry["mesh"].startswith("SM_BB_") else "/Basketbroom/Art/Meshes/") + entry["mesh"]
            if record.get("mesh", "").split(".")[0] != expected_mesh:
                raise RuntimeError("Unexpected source mesh: " + entry["label"])
        selected[path] = entry
    return selected


def canonical_snapshot(records):
    """Stable values and precisely observed native editor-only state changes.

    Keep raw snapshots in receipts. The six color structs previously included
    temporary Python wrapper addresses; parse only their four actual channels.
    Native reload can reset this one fog actor to origin and create one empty
    SceneRig camera manager. Neither is deleted or restored by this helper.
    """
    records = json.loads(json.dumps(records))
    for path, record in list(records.items()):
        color = record.get("text_settings", {}).get("text_render_color")
        if isinstance(color, str):
            match = re.fullmatch(r"<Struct 'Color' \(0x[0-9A-Fa-f]+\) \{b: (\d+), g: (\d+), r: (\d+), a: (\d+)\}>", color)
            if match is None or any(int(value) > 255 for value in match.groups()):
                raise RuntimeError("Unrecognized historical color representation")
            b, g, r, a = (int(value) for value in match.groups())
            record["text_settings"]["text_render_color"] = {"r": r, "g": g, "b": b, "a": a}
        if (record["class"] == "/Script/Engine.ExponentialHeightFog" and record["label"] == "Aerial depth"
                and GENERATED_TAG in record["tags"] and record["location"] in ([0, 0, -800], [0, 0, 0])):
            record["location"] = [0, 0, 0]
        if (record["class"] == "/Script/SceneRig.SceneRigCameraManager" and record["label"] == "SceneRigCameraManager"
                and path.endswith(":PersistentLevel.SceneRigCameraManager_0")
                and record["tags"] == [] and record.get("components_identity") == []
                and record["location"] == [0, 0, 0] and record["rotation"] == [0, 0, 0]
                and record["scale"] == [1, 1, 1] and record["folder"] == "None"):
            del records[path]
    return records


def mesh_slots(mesh):
    result = []
    for slot in mesh.get_editor_property("static_materials"):
        material = slot.get_editor_property("material_interface")
        result.append({"material": material.get_path_name() if material else None,
                       "name": str(slot.get_editor_property("material_slot_name")),
                       "imported_name": str(slot.get_editor_property("imported_material_slot_name"))})
    return result


def compare_preservation(before, after, selected, phase="new"):
    before, after = canonical_snapshot(before), canonical_snapshot(after)
    if set(before) != set(after):
        raise RuntimeError("An actor was created, destroyed or renamed during expansion")
    changed = 0
    for path, original in before.items():
        current = after[path]
        entry = selected.get(path)
        allowed = ("location", "rotation", "scale") if entry and entry["old"] != entry["new"] else ()
        if any(original.get(key) != current.get(key) for key in set(original) | set(current) if key not in allowed):
            raise RuntimeError("An identity, component, material or unrelated property changed: " + path)
        if allowed:
            changed += 1
            if any(not near(current[key], entry[phase][key], angular=key == "rotation") for key in allowed):
                raise RuntimeError("A planned actor transform did not persist: " + path)
    return changed


def geometry_audit(unreal, world, actors, dimensions):
    roof = roof_helper(dimensions).collision_audit(unreal, world, actors)
    def unique(tag, count):
        values = [actor for actor in actors if actor.actor_has_tag(tag)]
        if len(values) != count:
            raise RuntimeError("Unexpected native arena collision/goal count: " + tag)
        return values
    floors = unique("BB.Floor", 1)
    sides, ends = unique("BB.Net.Side", 2), unique("BB.Net.End", 2)
    traces = []
    def bracket(actor, start, clear, blocked, label):
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if str(component.get_collision_profile_name()) != "BlockAll" or component.get_collision_enabled() != unreal.CollisionEnabled.QUERY_AND_PHYSICS:
            raise RuntimeError("Native enclosing surface does not block pawn and physics queries")
        ignored = [other for other in actors if other != actor]
        def hit(end):
            return unreal.SystemLibrary.line_trace_single_by_profile(world, unreal.Vector(*start), unreal.Vector(*end),
                "Pawn", False, ignored, unreal.DrawDebugTrace.NONE, True) is not None
        result = {"actor": actor.get_path_name(), "sample": label, "clear_before_surface": not hit(clear), "blocked_after_surface": hit(blocked)}
        if not result["clear_before_surface"] or not result["blocked_after_surface"]:
            raise RuntimeError("Native boundary collision bracket failed: " + json.dumps(result))
        traces.append(result)
    hx, hy, eave = dimensions["half_x"], dimensions["half_y"], dimensions["eave"]
    for x, y in ((0, 0), (-hx + 100, 0), (hx - 100, 0), (0, -hy + 100), (0, hy - 100), (-3000, 0), (-3600, 0)):
        bracket(floors[0], (x, y, 100), (x, y, 1), (x, y, -1), "floor")
    for walls, axis, plane in ((ends, 0, hx), (sides, 1, hy)):
        for wall in walls:
            side = -1 if (wall.get_actor_location().x if axis == 0 else wall.get_actor_location().y) < 0 else 1
            for height in (100, eave / 2, eave - 20):
                start, clear, blocked = [0, 0, height], [0, 0, height], [0, 0, height]
                start[axis], clear[axis], blocked[axis] = side * (plane - 100), side * (plane - 1), side * (plane + 1)
                bracket(wall, start, clear, blocked, "wall")
    goals = []
    for tag, count, height, positions in (("BB.Goal.Large", 6, 2103.12, (-1066.8, 0, 1066.8)), ("BB.Goal.Small", 2, 3048.0, (0,))):
        actual = unique(tag, count)
        for side in (-1, 1):
            for y in positions:
                wanted = [side * dimensions["goal_x"], y, height]
                matches = [actor for actor in actual if near([actor.get_actor_location().x, actor.get_actor_location().y, actor.get_actor_location().z], wanted)]
                if len(matches) != 1 or not near([matches[0].get_actor_scale3d().x, matches[0].get_actor_scale3d().y, matches[0].get_actor_scale3d().z], [1, 1, 1]):
                    raise RuntimeError("A goal center or sporting aperture scale changed unexpectedly")
                actor = matches[0]
                start, finish = list(wanted), list(wanted)
                start[0] -= 100
                finish[0] += 100
                # Query the actual rim padding and confirm the center is open.
                ignored = [other for other in actors if not other.actor_has_tag("BB.Goal.Rim")]
                hit = unreal.SystemLibrary.line_trace_single_by_profile(world, unreal.Vector(*start), unreal.Vector(*finish),
                    "Pawn", False, ignored, unreal.DrawDebugTrace.NONE, True)
                if hit is not None:
                    raise RuntimeError("A native hoop scoring aperture is unexpectedly blocked")
                free_shot = [side * (dimensions["goal_x"] - 1341.12), y, height]
                restart = [side * (dimensions["goal_x"] - 670.56), y, height]
                if abs(abs(wanted[0] - free_shot[0]) - 1341.12) > 0.0001 or free_shot[1] != y or free_shot[2] != height:
                    raise RuntimeError("The fixed 44-foot free-shot geometry contract changed")
                goals.append({"actor": actor.get_path_name(), "center": wanted, "free_shot_44ft": free_shot,
                              "restart_22ft": restart, "aperture_center_clear": True})
    # Native anchor locations remain fixed; query floor support and headroom.
    anchor_clearance = []
    for x, label in ((-3000, "PlayerStart"), (-3600, "native exit")):
        ignored = [actor for actor in actors if actor.actor_has_tag("BB.HLCK.Dungeon.Exit.v1")]
        blocked = unreal.SystemLibrary.line_trace_single_by_profile(world, unreal.Vector(x, 0, 110), unreal.Vector(x, 0, 400),
            "Pawn", False, ignored, unreal.DrawDebugTrace.NONE, True) is not None
        if blocked:
            raise RuntimeError("Native entry/exit vertical clearance became blocked")
        anchor_clearance.append({"anchor": label, "xy": [x, 0], "vertical_clearance_cm": [110, 400], "clear": True})
    return {"passed": True, "dimensions": dimensions, "roof": roof, "boundary_brackets": traces,
            "goals": goals, "anchor_clearance": anchor_clearance,
            "native_trace_calls": roof["native_trace_calls"] + 2 * len(traces) + len(goals) + len(anchor_clearance),
            "sporting_distances_preserved": True, "sporting_geometry_only": True, "gameplay_tested": False}


def source_provenance(plan, manifest):
    """Accept only LF/CRLF byte variants proved against the captured old source.

    Git checkouts changed line endings between the initial native import and
    the roof import. The audited sidecar records both hashes, not loose names
    or modified numeric OBJ content. Neither unchanged assets nor source bytes
    are rewritten to compensate for this historical transport difference.
    """
    baseline_path = ROOT / "SourceArt/Arena/arena_expansion_baseline.json"
    path = ROOT / "SourceArt/Arena/arena_expansion_source_hashes.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if (record.get("schema_version") != 1 or record.get("baseline_file_sha256") != digest(baseline_path)
            or record["baseline_file_sha256"] != plan["baseline_sha256"]):
        raise RuntimeError("Native source newline provenance differs from the captured baseline")
    expected_meshes = {Path(entry["source"]).stem for entry in manifest["source_imports"] if entry["asset_type"] == "StaticMesh"}
    if set(record["meshes"]) != expected_meshes or set(baseline["meshes"]) != expected_meshes:
        raise RuntimeError("Source newline provenance must cover exactly the existing 18 arena meshes")
    changed = {entry["name"]: entry for entry in plan["changed_meshes"]}
    for entry in manifest["source_imports"]:
        if entry["asset_type"] != "StaticMesh":
            continue
        name = Path(entry["source"]).stem
        item, original = record["meshes"][name], baseline["meshes"][name]
        expected_before = changed.get(name, {}).get("sha256_before", entry["sha256"])
        variants = item["text_variants"]
        if (item["source"] != entry["source"] or original["source"] != entry["source"]
                or item["baseline_sha256"] != original["sha256"] or expected_before != original["sha256"]
                or set(variants) != {"lf", "crlf"} or expected_before not in variants.values()
                or item["git_source_sha256"] not in variants.values()
                or any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value) for value in variants.values())):
            raise RuntimeError("Invalid exact old-source newline provenance: " + name)
    return record


def _validate_sources(plan):
    importer = module("_bb_expansion_source_guard", "Mod/Tools/import_sources.py")
    manifest = importer.validate_sources()
    source_provenance(plan, manifest)
    indexed = {entry["destination"]: entry for entry in manifest["source_imports"]}
    for entry in plan["changed_meshes"]:
        source = indexed.get(entry["destination"], {})
        if source.get("asset_type") != "StaticMesh" or source.get("source") != entry["source"] or source.get("sha256") != entry["sha256_after"]:
            raise RuntimeError("Changed mesh differs from the exact prepared import manifest")
        if digest(ROOT / entry["source"]) != entry["sha256_after"]:
            raise RuntimeError("Expansion source bytes no longer match the plan")
    return manifest


def run(dry_run=True):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / ".local/hlck/arena-expansion-stage" / stamp
    receipt = directory / "result.json"
    report = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
              "amendment_kind": "arena_volume_45_percent", "maps": [], "registration_invoked": False,
              "travel_invoked": False, "runtime_python": False, "gameplay_tested": False,
              "materials_rebuilt": False, "installed_assets_modified": False}
    try:
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be a JSON boolean")
        plan = build_plan()
        manifest = _validate_sources(plan)
        report.update(plan=plan, plan_sha256=plan_hash(plan))
        import unreal
        guard = module("_bb_expansion_editor_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_expansion_native_stage", "Tools/stage_hlck_dungeon.py")
        registrar = module("_bb_expansion_registration", "Tools/register_hlck_dungeon.py")
        roof = module("_bb_expansion_prior_roof", "Tools/stage_hlck_pyramid_net.py")
        port = module("_bb_expansion_import_port", "Mod/Tools/build_arena_port.py")
        importer = port.import_sources
        report["active_mod"] = guard.require_editor(unreal)
        report["dirty_before"] = guard.require_clean(unreal)
        active = Path(unreal.Paths.convert_relative_path_to_full(str(unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
        if active != CONTENT.resolve():
            raise RuntimeError("Active mod does not resolve to this repository's native Content")
        levels = unreal.EditorLevelLibrary
        original = roof.world_path(levels.get_editor_world())
        if original not in MAPS:
            raise RuntimeError("Open an existing owned native arena map before expansion")
        report.update(original_world=original, engine=str(unreal.SystemLibrary.get_engine_version()))
        report["registration_before"] = registrar.verified_saved_registration(unreal, stage)
        content_before = registrar.hashes(CONTENT, digest)
        installed_before = registrar.metadata(registrar.KIT_CONTENT, ".umap")
        protected_before = {str(path): digest(path) for path in (registrar.KIT_CONTENT / "SQLiteDB").glob("*.sqlite")}
        material_before = {path: value for path, value in content_before.items() if path.replace("\\", "/").startswith("Art/Materials/")}
        report.update(content_before=content_before, material_hashes_before=material_before,
                      installed_map_metadata_before=installed_before, installed_database_hashes_before=protected_before)
        if SUCCESS.is_file():
            raise RuntimeError("This one-time baseline-to-45% amendment has a success receipt; inspect it instead of scaling twice")
        report["predecessor_roof_success"] = json.loads(roof.SUCCESS.read_text(encoding="utf-8"))
        for path in MAPS:
            baseline_path = ROOT / (".local/hlck/arena-port-result.json" if path == MAPS[0] else ".local/hlck/dungeon-anchor-result.json")
            baseline_key = "map_sha256" if path == MAPS[0] else "map_sha256_after"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))[baseline_key]
            if roof.verified_amendment(path, baseline) is None:
                raise RuntimeError("Expansion requires the exact previously verified roof map")
            if not levels.load_level(path):
                raise RuntimeError("Could not open exact owned map for expansion preflight")
            guard.require_clean(unreal)
            world, actors = roof.validate_map_ownership(unreal, path)
            before = snapshot(unreal, actors)
            item = {"path": path, "sha256_before": digest(map_file(path)), "actors_before": before,
                    "game_mode_before": str(world.get_world_settings().get_editor_property("default_game_mode"))}
            report["maps"].append(item)
            selected = match_plan(before, plan, "old")
            item["selected_paths"] = {actor_path: entry["label"] for actor_path, entry in selected.items()}
            item["geometry_before"] = geometry_audit(unreal, world, actors, plan["dimensions_before"])
        changed_lookup = {entry["destination"]: entry for entry in plan["changed_meshes"]}
        provenance = source_provenance(plan, manifest)
        report["source_provenance_sha256"] = digest(ROOT / "SourceArt/Arena/arena_expansion_source_hashes.json")
        report["native_source_provenance"] = []
        mesh_materials = {}
        report["mesh_slots_before"] = {}
        for entry in manifest["source_imports"]:
            if entry["asset_type"] != "StaticMesh":
                continue
            asset = unreal.EditorAssetLibrary.load_asset(entry["destination"])
            if not isinstance(asset, unreal.StaticMesh):
                raise RuntimeError("Expected an existing importer-owned native source mesh")
            importer._owned(unreal, asset)
            expected_hash = changed_lookup.get(entry["destination"], {}).get("sha256_before", entry["sha256"])
            actual_hash = unreal.EditorAssetLibrary.get_metadata_tag(asset, importer.META_HASH)
            variants = provenance["meshes"][Path(entry["source"]).stem]["text_variants"]
            if (actual_hash not in variants.values()
                    or unreal.EditorAssetLibrary.get_metadata_tag(asset, importer.META_REVISION) != importer.REVISION):
                raise RuntimeError("Native source metadata differs from verified original LF/CRLF bytes: " + entry["destination"])
            report["native_source_provenance"].append({"asset": entry["destination"], "native_source_sha256": actual_hash,
                "captured_baseline_sha256": expected_hash, "matching_line_endings": [key for key, value in variants.items() if value == actual_hash]})
            if entry["destination"] in changed_lookup:
                mesh_materials[entry["destination"]] = list(asset.get_editor_property("static_materials"))
                report["mesh_slots_before"][entry["destination"]] = mesh_slots(asset)
        if not dry_run:
            backups = directory / "backups"
            report["package_backups"] = []
            for path in allowed_files(plan):
                if not path.is_file():
                    raise RuntimeError("An expected native expansion package is missing")
                destination = backups / path.relative_to(CONTENT.resolve())
                destination.parent.mkdir(parents=True, exist_ok=True)
                expected = digest(path)
                shutil.copy2(str(path), str(destination))
                if digest(destination) != expected or digest(path) != expected:
                    raise RuntimeError("Exact pre-expansion package backup did not verify")
                report["package_backups"].append({"path": str(path), "backup": str(destination), "sha256": expected})
            for item in report["maps"]:
                item["backup"] = str(backups / map_file(item["path"]).relative_to(CONTENT))
            report["status"] = "backed_up"
            write(receipt, report)
            guard.require_clean(unreal)
            unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
            imported = importer.build(create_materials=False, asset_names=[entry["name"] for entry in plan["changed_meshes"]])
            if imported.get("status") != "complete":
                raise RuntimeError("Targeted original-source expansion import failed")
            for entry in plan["changed_meshes"]:
                mesh = unreal.EditorAssetLibrary.load_asset(entry["destination"])
                mesh.set_editor_property("static_materials", mesh_materials[entry["destination"]])
                if mesh_slots(mesh) != report["mesh_slots_before"][entry["destination"]]:
                    raise RuntimeError("Native material slot names or interfaces changed after restoration")
                if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
                    raise RuntimeError("Could not preserve native mesh material slots")
            collision_builder = port.ArenaPortBuilder(manifest, report)
            collision_builder.meshes = {"SM_BB_PyramidCollision": unreal.EditorAssetLibrary.load_asset("/Basketbroom/Art/Meshes/SM_BB_PyramidCollision")}
            collision_builder.configure_pyramid_collision()
            for item in report["maps"]:
                guard.require_clean(unreal)
                if not levels.load_level(item["path"]):
                    raise RuntimeError("Could not reopen exact owned expansion map")
                world, actors = roof.validate_map_ownership(unreal, item["path"])
                before = snapshot(unreal, actors)
                if canonical_snapshot(before) != canonical_snapshot(item["actors_before"]):
                    raise RuntimeError("A native actor/component changed on reload before transformation")
                selected = match_plan(before, plan, "old")
                indexed = {actor.get_path_name(): actor for actor in actors}
                for path, entry in selected.items():
                    if entry["old"] == entry["new"]:
                        continue
                    actor = indexed[path]
                    target = entry["new"]
                    if target["location"] != entry["old"]["location"]:
                        actor.set_actor_location(unreal.Vector(*target["location"]), False, True)
                    if target["rotation"] != entry["old"]["rotation"]:
                        actor.set_actor_rotation(unreal.Rotator(pitch=target["rotation"][0], yaw=target["rotation"][1], roll=target["rotation"][2]), True)
                    if target["scale"] != entry["old"]["scale"]:
                        actor.set_actor_scale3d(unreal.Vector(*target["scale"]))
                current = list(levels.get_all_level_actors())
                after = snapshot(unreal, current)
                changed = compare_preservation(before, after, selected)
                match_plan(after, plan, "new")
                if str(world.get_world_settings().get_editor_property("default_game_mode")) != item["game_mode_before"]:
                    raise RuntimeError("Native game mode changed; current map remains unsaved")
                item["geometry_pre_save"] = geometry_audit(unreal, world, current, plan["dimensions_after"])
                dirty_maps = [package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
                if any(path != item["path"] for path in dirty_maps) or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
                    raise RuntimeError("Unexpected dirty packages; unrelated work will not be saved")
                if not levels.save_current_level() or not levels.load_level(item["path"]):
                    raise RuntimeError("Could not save/reload exact expanded map")
                world, actors = roof.validate_map_ownership(unreal, item["path"])
                saved = snapshot(unreal, actors)
                compare_preservation(before, saved, selected)
                match_plan(saved, plan, "new")
                if str(world.get_world_settings().get_editor_property("default_game_mode")) != item["game_mode_before"]:
                    raise RuntimeError("Native game mode changed after saved reload")
                item.update(sha256_after=digest(map_file(item["path"])), unrelated_actors_preserved=True,
                    actor_identity_and_components_preserved=True, preserved_actor_count=len(before), transformed_actor_count=changed,
                    game_mode_preserved=True, saved_reloaded=True, geometry_after=geometry_audit(unreal, world, actors, plan["dimensions_after"]))
                write(receipt, report)
        if not levels.load_level(original):
            raise RuntimeError("Could not restore original clean native world")
        report["dirty_after"] = guard.require_clean(unreal)
        content_after = registrar.hashes(CONTENT, digest)
        changed = sorted(path for path in set(content_before) | set(content_after) if content_before.get(path) != content_after.get(path))
        allowed = {str(path.relative_to(CONTENT.resolve())) for path in allowed_files(plan)}
        if any(path not in allowed for path in changed) or (dry_run and changed):
            raise RuntimeError("An asset outside the exact expansion package allowlist changed")
        if any(content_after.get(path) != expected for path, expected in material_before.items()):
            raise RuntimeError("An existing material changed during native expansion")
        if registrar.metadata(registrar.KIT_CONTENT, ".umap") != installed_before:
            raise RuntimeError("Installed map metadata changed during native expansion")
        if any(digest(Path(path)) != expected for path, expected in protected_before.items()):
            raise RuntimeError("Installed database bytes changed during native expansion")
        report["registration_after"] = registrar.verified_saved_registration(unreal, stage)
        if report["registration_after"] != report["registration_before"]:
            raise RuntimeError("Saved/live registration changed during expansion")
        if not dry_run:
            for entry in plan["changed_meshes"]:
                if mesh_slots(unreal.EditorAssetLibrary.load_asset(entry["destination"])) != report["mesh_slots_before"][entry["destination"]]:
                    raise RuntimeError("Native material slots changed after saved map reload")
            report["mesh_slots_preserved"] = True
            report["saved_package_hashes"] = {str(path): digest(path) for path in allowed_files(plan)}
        report.update(changed_content_files=changed, preservation_verified=True, materials_preserved=True,
                      original_world_restored=True, finished_utc=datetime.now(timezone.utc).isoformat(), status="ready" if dry_run else "staged")
        write(receipt, report)
        if not dry_run:
            write(SUCCESS, {"report": str(receipt), "sha256": digest(receipt)})
    except Exception:
        report.update(status="failed", error=traceback.format_exc(),
            recovery="Inspect this attempt and open editor. Verified package backups are retained; no automatic rollback or unsaved-work discard occurs.")
        write(receipt, report)
    return {"status": report["status"], "report": str(receipt), "dry_run": dry_run,
            "runtime_tested": False, "registration_invoked": False}


if __name__ == "__main__":
    if "BRIDGE_ARGS" in globals():
        RESULT = run(dry_run=BRIDGE_ARGS.get("dry_run", True))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--validate-sources", action="store_true")
        args = parser.parse_args()
        if not args.validate_sources:
            parser.error("Use --validate-sources outside Unreal, or the authenticated native editor bridge")
        plan = build_plan()
        _validate_sources(plan)
        print(json.dumps({"status": "sources_valid", "volume_ratio": plan["volume_ratio"],
                          "changed_meshes": len(plan["changed_meshes"]), "owned_actors": len(plan["actors"]), "unreal_called": False}))
