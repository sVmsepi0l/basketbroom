"""Bounded disposable-PIE inventory setup and genuine native broom activation.

Default read-only preflight; {"execute": true} runs staged setup and activation,
restores the two observed locks and the exact granted quantity, then ends only
the retained owned dungeon PIE. No save, SQL edit, forced flight/input or travel.
Optional request_native_mount invokes the documented native transition once, only
after ordinary item use has produced the exact real House broom tool component.
Native attachment/get_broom/get_mount_type establish mount association only.
Generic is_flying and controller possession remain diagnostics. No flight input
is tested; observe_seconds holds the observation window open up to 20 seconds.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import time
import uuid
import unreal

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path("C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject")
KEY = "_bb_native_broom_inventory_test_v1"
WORLD_RE = r"/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap"
ITEM = "BroomHouse"
HOLDER = "BroomStorage"
# GetCount(Player0, ..., ActorBackpack) is a combined player-holder query in
# native InventoryManager (GetCount RVA 0x1610280, branch RVA 0x161080e).
# Its result overlaps ActiveBroom. Only these explicit physical broom holders
# belong in quantity/cleanup accounting; keep backpack as a separate diagnostic.
HOLDERS = ("ActiveBroom", HOLDER)
LOCKS = ("Vendor_Broom_Acquired", "BroomAvailable")
RECORD = "/Game/Gameplay/ToolSet/Items/InventoryItems/Broom/DA_BroomHouseItem.DA_BroomHouseItem"


def utc():
    return datetime.now(timezone.utc).isoformat()


def path(obj):
    return obj.get_path_name() if obj is not None else None


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def dirty():
    return sorted(path(p) for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def reflected_value(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if callable(getattr(obj, "get_path_name", None)):
        return obj.get_path_name()
    names = re.findall(r"- ``([a-z_0-9]+)``", str(type(obj).__doc__ or ""))
    if names and callable(getattr(obj, "get_editor_property", None)):
        return {name: str(obj.get_editor_property(name)) for name in names}
    if type(obj).__name__ == "Array":
        return [reflected_value(part) for part in obj]
    return str(obj)


def diagnostic_read(function, *args, **kwargs):
    try:
        return {"value": reflected_value(function(*args, **kwargs))}
    except Exception as exc:
        return {"error": type(exc).__name__ + ": " + str(exc)}


def gate_diagnostics(character, world):
    api = unreal.InventoryManagerInterface
    result = {
        "item_properties": diagnostic_read(unreal.InventoryObjectManagerBPInterface.get_item_properties, ITEM),
        "player_capacity": diagnostic_read(api.get_player_available_capacity, ITEM),
        "limited_holders": diagnostic_read(api.get_player_limited_holders),
        "unlimited_holders": diagnostic_read(api.get_player_unlimited_holders),
        "holders": {}, "mount_classes": {}, "mount_zones": [],
    }
    for holder in HOLDERS + ("ActorBackpack",):
        result["holders"][holder] = {
            "count": diagnostic_read(api.get_count, character, ITEM, holder_id=holder),
            "can_add_one": diagnostic_read(api.can_add_item, character, ITEM, holder, "None", 1),
            "max_slots": diagnostic_read(api.get_holder_max_slots_bp, holder),
            "items": diagnostic_read(api.get_inventory_text_bp, character, "Broom", unreal.InventoryFilter(),
                                      holder_id=holder, specified_holder_only=True),
        }
    for name in ("PlayerMountOverlapManager", "MountZoneVolumeBase", "NoMountZoneVolume", "BroomNoFlyControl"):
        cls = getattr(unreal, name, None)
        if cls is None:
            continue
        methods = {method: str(getattr(cls, method).__doc__ or "") for method in dir(cls)
                   if not method.startswith("_") and callable(getattr(cls, method, None))
                   and any(word in method for word in ("mount", "broom", "fly", "singleton", "manager", "overlap", "allow"))}
        result["mount_classes"][name] = {"doc": str(cls.__doc__ or ""), "api": methods}
        if name == "NoMountZoneVolume":
            for zone in unreal.GameplayStatics.get_all_actors_of_class(world, cls):
                names = re.findall(r"- ``([a-z_0-9]+)``", str(cls.__doc__ or ""))
                result["mount_zones"].append({
                    "path": path(zone), "overlaps_player": diagnostic_read(zone.is_overlapping_actor,
                        unreal.GameplayStatics.get_player_pawn(world, 0)),
                    "properties": {key: str(zone.get_editor_property(key)) for key in names
                                   if any(word in key for word in ("mount", "broom", "fly", "allow", "active", "enabled"))},
                })
    return result


def protected_files():
    files = [PROJECT.parent / "Content/SQLiteDB" / name for name in
             ("PhoenixGameData.sqlite", "PhoenixShipData.sqlite", "PhoenixDynData.sqlite")]
    files.append(ROOT / "Mod/Basketbroom/Content/ModEdits.sql")
    return {str(file): hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None for file in files}


class InventoryBroomTest:
    def __init__(self, execute, mount_active_tool=False, observe_seconds=20.):
        self.execute = execute
        self.mount_active_tool = mount_active_tool
        self.observe_seconds = observe_seconds
        self.mount_calls = 0
        self.handle = None
        self.world = self.player = self.controller = self.inventory = self.broom = None
        self.initial_locks = {}
        self.initial_count = None
        self.initial_counts = {}
        self.use_holder = None
        self.granted = 0
        self.grant_requested = False
        self.phase = "preflight"
        self.started = time.monotonic()
        self.phase_start = self.started
        self.phase_world = 0.
        self.last_sample = 0.
        self.mount_since = None
        self.done = False
        folder = ROOT / ".local/hlck/native-broom-inventory-tests" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
        folder.mkdir(parents=True, exist_ok=False)
        self.report = folder / "result.json"
        self.result = {"status": "preflight", "started_utc": utc(), "pid": os.getpid(),
                       "execute": execute, "assets_saved": False, "sql_edits_requested": False,
                       "mount_active_tool_requested": mount_active_tool, "native_mount_calls": 0,
                       "flight_input_tested": False,
                       "observe_seconds": observe_seconds,
                       "verification_limitations": "Native association is checked through get_broom, get_mount_type and attachment to the capsule. Controller possession/is_flying are diagnostics only. Movement input, responsive flight and dismount remain unverified.",
                       "input_injected": False, "forced_flight_flags": False, "events": [],
                       "samples": [], "checks": {}, "scope": "Native inventory gates and actual broom mount, not complete flight controls or persistent mod integration."}

    def save(self):
        self.result["phase"] = self.phase
        self.result["elapsed_seconds"] = time.monotonic() - self.started
        # Match native_test_receipts' bounded retry protocol, retaining the
        # Creator Kit's older Python compatibility (no Path.unlink missing_ok).
        temporary = self.report.with_name("." + self.report.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps(self.result, indent=2) + "\n", encoding="utf-8")
            for attempt, delay in enumerate((0., .01, .02, .04, .08, .16)):
                if delay:
                    time.sleep(delay)
                try:
                    os.replace(str(temporary), str(self.report))
                    return
                except PermissionError:
                    if attempt == 5:
                        raise
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass

    def event(self, name, **values):
        self.result["events"].append(dict(name=name, utc=utc(), **values))
        self.save()

    def summary(self):
        return {"status": self.result["status"], "phase": self.phase, "report": str(self.report), "execute": self.execute}

    def guard(self):
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != PROJECT.resolve() or not unreal.SystemLibrary.get_engine_version().startswith("4.27."):
            raise RuntimeError("Expected native Creator Kit")
        if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()) != "Basketbroom":
            raise RuntimeError("Wrong active mod")
        worlds = list(unreal.EditorLevelLibrary.get_pie_worlds(True))
        if len(worlds) != 1 or not re.fullmatch(WORLD_RE, worlds[0].get_path_name()):
            raise RuntimeError("Expected single owned dungeon PIE")
        if self.world is not None and worlds[0] != self.world:
            raise RuntimeError("Retained PIE changed; no mutation or stop of another world")
        return worlds[0]

    def counts(self):
        return {holder: int(unreal.InventoryManagerInterface.get_count(self.character, ITEM, holder_id=holder))
                for holder in HOLDERS}

    def count(self):
        return sum(self.counts().values())

    def snapshot(self):
        associated_broom = unreal.MountZoneVolumeBase.get_broom(self.player)
        native_mount_type = unreal.MountZoneVolumeBase.get_mount_type(self.player)
        attach_parent = self.player.get_attach_parent_actor()
        brooms = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.FlyingBroom))
        rows = []
        for broom in brooms:
            movement = broom.get_movement_component()
            rows.append({"path": path(broom), "class": broom.get_class().get_path_name(),
                         "location": xyz(broom.get_actor_location()), "velocity": xyz(broom.get_velocity()),
                         "movement_class": movement.get_class().get_path_name() if movement else None,
                         "is_flying": bool(movement.is_flying()) if isinstance(movement, unreal.FlyingBroomMovementComponent) else False,
                         "controller_possesses": self.controller.get_controlled_pawn() == broom})
        counts = self.counts()
        return {"world_seconds": float(unreal.GameplayStatics.get_time_seconds(self.world)),
                "phase": self.phase, "count": sum(counts.values()), "holder_counts": counts,
                "aggregate_backpack_count_not_added": int(unreal.InventoryManagerInterface.get_count(
                    self.character, ITEM, holder_id="ActorBackpack")),
                "locks": {name: {"state": str(unreal.LockManagerInterface.get_state(name)),
                                 "locked": bool(unreal.LockManagerInterface.is_locked(name))} for name in LOCKS},
                "can_use_broom": bool(unreal.UIBlueprintFunctionLibrary.can_use_broom(True)),
                "can_use_without_avatar": bool(unreal.UIBlueprintFunctionLibrary.can_use_broom(False)),
                "mounted_or_transitioning": bool(self.player.get_is_on_a_mount_or_in_transition()),
                "native_associated_broom": path(associated_broom),
                "native_mount_type": str(native_mount_type) if native_mount_type is not None else None,
                "player_attach_parent": path(attach_parent),
                "controlled_pawn": path(self.controller.get_controlled_pawn()),
                "active_tool": path(self.inventory.get_active_tool()), "brooms": rows}

    def start(self):
        if getattr(unreal, KEY, None) is not None:
            raise RuntimeError("Native inventory observer already active")
        self.world = self.guard()
        if dirty():
            raise RuntimeError("Unsaved editor work exists")
        self.player = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        self.controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        if not self.player or not self.controller or self.controller.get_controlled_pawn() != self.player:
            raise RuntimeError("Expected possessed native player")
        if self.player.get_class().get_path_name() != "/Game/Pawn/Player/BP_Biped_Player.BP_Biped_Player_C":
            raise RuntimeError("Expected native player class")
        self.character = self.player.get_character_id()
        if str(self.character) != "Player0":
            raise RuntimeError("Expected observed Player0 inventory identity")
        ui = unreal.UIManager.get_ui_manager_pure()
        if not ui or ui.get_editor_property("game_player_controller") != self.controller:
            raise RuntimeError("UI manager does not belong to retained PIE")
        if ui.in_pause_mode() or ui.get_in_menu_transition() or unreal.GameplayStatics.is_game_paused(self.world):
            raise RuntimeError("Close menu/unpause before inventory test")
        slots = [c for c in self.player.get_components_by_class(unreal.ToolSetComponent) if c.get_name() == "InventoryToolSetComponent"]
        if len(slots) != 1:
            raise RuntimeError("Expected exact native inventory component")
        self.inventory = slots[0]
        records = [r for r in self.inventory.get_tool_records() if r.get_path_name() == RECORD]
        if len(records) != 1 or not self.inventory.is_tool_usage_allowed(records[0]):
            raise RuntimeError("Expected allowed native House broom record")
        if self.inventory.get_active_tool() is not None or self.player.get_is_on_a_mount_or_in_transition():
            raise RuntimeError("Existing active tool/mount preserved")
        if unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.FlyingBroom):
            raise RuntimeError("Existing native broom preserved")
        self.initial_counts = self.counts()
        self.initial_count = sum(self.initial_counts.values())
        if self.initial_count not in (0, 1):
            raise RuntimeError("Expected zero or one House broom; preserving larger inventory")
        active_records = unreal.InventoryManagerInterface.get_inventory_text_bp(
            self.character, "Broom", unreal.InventoryFilter(), holder_id="ActiveBroom", specified_holder_only=True)
        if any(str(row.get_editor_property("item_name")) != ITEM for row in active_records):
            raise RuntimeError("A different equipped broom exists; preserving it")
        self.initial_locks = {name: unreal.LockManagerInterface.get_state(name) for name in LOCKS}
        self.result.update(world=path(self.world), player=path(self.player), controller=path(self.controller),
                           initial=self.snapshot(), protected_files_before=protected_files(),
                           gate_diagnostics=gate_diagnostics(self.character, self.world))
        self.result["api_evidence_sha256"] = hashlib.sha256((ROOT / ".local/hlck/native-broom-gates.json").read_bytes()).hexdigest()
        if not self.execute:
            self.result["status"] = "ready"
            self.save()
            return self.summary()
        self.result["status"] = "running"
        setattr(unreal, KEY, self)
        self.advance("settle")
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        return self.summary()

    def advance(self, phase):
        self.phase = phase
        self.phase_start = time.monotonic()
        self.phase_world = float(unreal.GameplayStatics.get_time_seconds(self.world))
        self.save()

    def settled(self, seconds=1.):
        return float(unreal.GameplayStatics.get_time_seconds(self.world)) - self.phase_world >= seconds

    def cleanup(self, error=None):
        if error:
            self.result["error"] = error
        self.guard()
        self.result["before_cleanup"] = self.snapshot()
        # Restore exactly the native runtime quantities/lock states we changed.
        current_counts = self.counts()
        if self.grant_requested and 0 <= sum(current_counts.values()) - self.initial_count <= 1:
            self.granted = sum(current_counts.values()) - self.initial_count
        if sum(current_counts.values()) != self.initial_count + self.granted:
            raise RuntimeError("Inventory changed independently; refusing broad reset")
        if self.granted:
            source = next((holder for holder in HOLDERS if current_counts[holder] > self.initial_counts[holder]), None)
            if source is None:
                raise RuntimeError("Granted broom holder could not be identified")
            unreal.InventoryManagerInterface.adjust_count(self.character, ITEM, -self.granted,
                holder_id=source, suppress_hud_notification=True)
            self.granted = 0
        # If ordinary item use moved a preexisting broom to ActiveBroom, return
        # that same observed InventoryResult to its original holder, not a clone.
        for unused in range(len(HOLDERS)):
            current_counts = self.counts()
            if current_counts == self.initial_counts:
                break
            source = next((holder for holder in HOLDERS if current_counts[holder] > self.initial_counts[holder]), None)
            target = next((holder for holder in HOLDERS if current_counts[holder] < self.initial_counts[holder]), None)
            if source is None or target is None:
                raise RuntimeError("Exact holder restoration failed; refusing broad inventory reset")
            rows = unreal.InventoryManagerInterface.get_inventory_text_bp(
                self.character, "Broom", unreal.InventoryFilter(), holder_id=source, specified_holder_only=True)
            matches = [row for row in rows if str(row.get_editor_property("item_name")) == ITEM]
            if len(matches) != 1:
                raise RuntimeError("Cannot identify exact existing broom inventory result for restoration")
            moved = unreal.InventoryManagerInterface.transfer_item_to_container_bp(matches[0], self.character, target, 1)
            self.event("existing_broom_holder_restored", source=source, target=target, result=bool(moved))
            if not moved:
                raise RuntimeError("Native inventory transfer refused exact holder restoration")
        for name, state in self.initial_locks.items():
            if unreal.LockManagerInterface.get_state(name) != state:
                unreal.LockManagerInterface.set_lock(name, state)
        self.result["checks"]["inventory_quantity_restored"] = self.count() == self.initial_count
        self.result["checks"]["exact_inventory_holders_restored"] = self.counts() == self.initial_counts
        self.result["checks"]["lock_states_restored"] = all(unreal.LockManagerInterface.get_state(name) == state for name, state in self.initial_locks.items())
        self.result["protected_files_after"] = protected_files()
        self.result["checks"]["installed_databases_and_mod_sql_unchanged"] = self.result["protected_files_before"] == self.result["protected_files_after"]
        self.result["dirty_packages_before_stop"] = dirty()
        self.result["checks"]["no_dirty_packages"] = not self.result["dirty_packages_before_stop"]
        self.advance("ending")
        self.event("same_owned_disposable_pie_end_requested")
        unreal.EditorLevelLibrary.editor_end_play()

    def finish(self, error=None):
        if error:
            self.result["error"] = error
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if getattr(unreal, KEY, None) is self:
            delattr(unreal, KEY)
        self.done = True
        checks = self.result["checks"]
        self.result["mount_association_result"] = "passed" if checks.get("actual_native_mount_association_settled") else "not_verified"
        self.result["status"] = "passed" if not self.result.get("error") and checks.get("actual_native_mount_association_settled") and all(checks.values()) else "failed"
        self.result["finished_utc"] = utc()
        self.save()

    def tick(self, unused_delta):
        try:
            now = time.monotonic()
            if self.phase == "ending":
                if not unreal.EditorLevelLibrary.get_pie_worlds(True):
                    self.result["checks"]["owned_pie_stopped"] = True
                    return self.finish()
                if now - self.phase_start > 15:
                    return self.finish("Owned PIE did not stop")
                return
            self.guard()
            if now - self.started > 55:
                return self.cleanup("Native inventory/mount test timed out")
            if now - self.last_sample >= .25:
                self.last_sample = now
                self.result["samples"].append(self.snapshot())
                self.save()
            if not self.settled():
                return
            if self.phase == "settle":
                if self.initial_count == 0:
                    self.grant_requested = True
                    result = unreal.InventoryManagerInterface.adjust_count(self.character, ITEM, 1,
                        holder_id=HOLDER, suppress_hud_notification=True)
                    self.granted = self.count() - self.initial_count
                    self.event("house_broom_grant", returned_remainder=int(result), observed_delta=self.granted,
                               holder_counts=self.counts())
                    if self.granted not in (0, 1):
                        raise RuntimeError("Unexpected inventory grant quantity")
                self.advance("grant_observe")
            elif self.phase == "grant_observe":
                if self.grant_requested:
                    self.granted = self.count() - self.initial_count
                if self.count() < 1:
                    return self.cleanup("Native grant did not produce House broom inventory")
                self.result["after_grant"] = self.snapshot()
                self.result["after_grant_inventory_records"] = {
                    holder: diagnostic_read(unreal.InventoryManagerInterface.get_inventory_text_bp,
                        self.character, "Broom", unreal.InventoryFilter(), holder_id=holder,
                        specified_holder_only=True) for holder in HOLDERS
                }
                self.use_holder = next(holder for holder, count in self.counts().items() if count > 0)
                if unreal.LockManagerInterface.is_locked(LOCKS[0]):
                    unreal.LockManagerInterface.unlock(LOCKS[0])
                    self.event("vendor_lock_unlocked")
                self.advance("vendor_observe")
            elif self.phase == "vendor_observe":
                self.result["after_vendor_unlock"] = self.snapshot()
                if unreal.LockManagerInterface.is_locked(LOCKS[1]):
                    unreal.LockManagerInterface.unlock(LOCKS[1])
                    self.event("availability_lock_unlocked")
                self.advance("availability_observe")
            elif self.phase == "availability_observe":
                sample = self.snapshot()
                self.result["after_availability_unlock"] = sample
                self.result["checks"]["inventory_present"] = sample["count"] >= 1
                self.result["checks"]["native_can_use_broom"] = sample["can_use_broom"]
                # Loading selects the real inventory item. Let the native use
                # method enforce its own gates; do not force a spawn or flag.
                loaded = bool(self.player.load_inventory_item_by_name(ITEM, self.use_holder))
                self.event("native_player_load_inventory_item", result=loaded, holder=self.use_holder)
                self.result["checks"]["native_inventory_load_succeeded"] = loaded
                self.advance("load_observe")
            elif self.phase == "load_observe":
                self.result["after_load"] = self.snapshot()
                used = bool(self.player.use_inventory_item_by_name(ITEM, self.use_holder))
                self.event("native_player_use_inventory_item", result=used, holder=self.use_holder)
                self.result["checks"]["native_inventory_use_succeeded"] = used
                self.advance("mount_observe")
            elif self.phase == "mount_observe":
                sample = self.snapshot()
                if (self.mount_active_tool and not self.mount_calls and self.settled(3.)
                        and not sample["brooms"] and not sample["mounted_or_transitioning"]):
                    tool = self.inventory.get_active_tool()
                    if tool is not None:
                        if not isinstance(tool, unreal.BroomItemTool):
                            return self.cleanup("Unexpected active item; preserving it without invoking mount")
                        if path(tool.get_tool_record()) != RECORD or tool.get_our_tool_set_component() != self.inventory:
                            return self.cleanup("Active native broom ownership/record mismatch")
                        if not path(tool).startswith(path(self.world) + ":PersistentLevel."):
                            return self.cleanup("Active native broom tool belongs to another world")
                        self.mount_calls = 1
                        self.result["native_mount_calls"] = 1
                        self.event("documented_native_mount_transition_requested", tool=path(tool),
                                   tool_class=tool.get_class().get_path_name(), use_transition=True,
                                   tool_record=path(tool.get_tool_record()), tool_set=path(tool.get_our_tool_set_component()))
                        tool.spawn_and_mount_broom(True, True)
                        return
                matches = [b for b in sample["brooms"]
                           if b["path"] == sample["native_associated_broom"] == sample["player_attach_parent"]
                           and b["movement_class"] == "/Script/Phoenix.FlyingBroomMovementComponent"]
                if len(matches) == 1 and sample["mounted_or_transitioning"] and sample["native_mount_type"] is not None:
                    if self.mount_since is None:
                        self.mount_since = sample["world_seconds"]
                    if sample["world_seconds"] - self.mount_since >= 2.:
                        if not self.result["checks"].get("actual_native_mount_association_settled"):
                            self.result["checks"]["actual_native_mount_association_settled"] = True
                            self.result["associated_broom"] = matches[0]
                            self.event("actual_native_mount_association_settled", broom=matches[0]["path"],
                                       native_mount_type=sample["native_mount_type"], player=path(self.player))
                        if now - self.phase_start >= self.observe_seconds:
                            return self.cleanup()
                else:
                    self.mount_since = None
                    if self.result["checks"].get("actual_native_mount_association_settled"):
                        self.result["checks"]["actual_native_mount_association_settled"] = False
                        self.event("native_mount_association_lost")
                if now - self.phase_start >= 20:
                    return self.cleanup("20-second observation ended without sustained native mount association; actual flight input was not tested")
        except Exception as exc:
            message = type(exc).__name__ + ": " + str(exc)
            try:
                if self.phase == "ending":
                    return self.finish(message)
                self.cleanup(message)
            except Exception as cleanup_exc:
                self.finish(message + "; cleanup failed: " + str(cleanup_exc))


def run(args=None):
    args = args or {}
    if set(args) - {"execute", "request_native_mount", "observe_seconds"}:
        raise ValueError("Only execute, request_native_mount and observe_seconds are accepted")
    if any(type(args.get(key, False)) is not bool for key in ("execute", "request_native_mount")):
        raise ValueError("execute and request_native_mount must be booleans")
    observe_seconds = args.get("observe_seconds", 20.)
    if type(observe_seconds) not in (int, float) or not 0. <= observe_seconds <= 20.:
        raise ValueError("observe_seconds must be a finite number between 0 and 20")
    observer = InventoryBroomTest(args.get("execute", False), args.get("request_native_mount", False), float(observe_seconds))
    try:
        return observer.start()
    except Exception as exc:
        observer.result.update(status="not_run", error=type(exc).__name__ + ": " + str(exc))
        observer.save()
        return observer.summary()


if __name__ == "__main__":
    RESULT = run(globals().get("BRIDGE_ARGS", {}))
