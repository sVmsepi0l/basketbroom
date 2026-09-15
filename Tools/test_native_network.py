"""Two-world, one-process PIE networking checks for BasketbroomRuntime.

Run through editor_bridge.py with BB_Arena_Regulation staged and PIE stopped.
The asynchronous report is .local/native-network-test-results.json. Settings
controlled by this script are restored during cleanup. If this engine omits
the Python net-mode enum, configure Play As Listen Server before the run and
pass settings_already_configured=True. settings_source="editor_ui" (default)
records the UI route. settings_source="editor_config" records the normal
[/Script/UnrealEd.LevelEditorPlaySettings] PlayNetMode=PIE_ListenServer entry in
EditorPerProjectUserSettings.ini, prepared with the editor closed and restored
with it closed afterward. Both routes still require actual connected authority
and client PIE worlds. This suite does not read/write the absent enum wrapper.
This suite owns and
ends its PIE session. No editor map or gameplay defaults are saved or changed.
Outside Unreal, --list describes the plan without claiming it ran.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import traceback

try:
    import unreal
except ImportError:
    unreal = None

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "native-network-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})
_receipt_spec = importlib.util.spec_from_file_location("_bb_network_receipts", ROOT / "Tools/native_test_receipts.py")
_receipts = importlib.util.module_from_spec(_receipt_spec)
_receipt_spec.loader.exec_module(_receipts)
write_json_atomic = _receipts.write_json_atomic
MODULE = "/Script/BasketbroomRuntime."
ROLES = (0, 1, 1, 2, 3, 4, 4, 5)
TESTS = (
    "distinct_listen_server_and_client_worlds", "sixteen_slots_replicated",
    "two_distinct_human_owners_replicated", "client_role_request_replicated",
    "client_held_input_rpc_replicated", "client_cannot_start_match",
    "host_start_replicates", "client_cannot_pause_match",
    "client_ball_fixture_rejected", "server_goal_awards_and_replicates_13",
    "goal_is_not_scored_twice", "host_stoppage_replicates",
    "both_worlds_agree_at_stoppage", "client_flight_reaches_server",
    "client_pickup_replicates_possession", "client_throw_replicates_release",
    "managed_play_settings_restored_and_pie_ended",
)


def aliases(name):
    result = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        result.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    return result


def property_slot(obj, name):
    error = None
    for alias in aliases(name):
        try:
            return alias, obj.get_editor_property(alias)
        except Exception as exc:
            error = exc
    raise error


def prop(obj, name):
    return property_slot(obj, name)[1]


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def net_mode_restore_actions(provenance):
    """Report the externally configured setting honestly; never claim its restore."""
    if provenance.get("net_mode_configuration_source") == "editor_config":
        return ["After closing the editor, restore the backed-up EditorPerProjectUserSettings.ini PlayNetMode setting"]
    if provenance.get("net_mode_configured_in_editor"):
        return ["Restore the prior Play Net Mode through the editor UI"]
    return []


class NativeNetworkTests:
    def __init__(self):
        self.started = time.monotonic()
        self.phase = "preflight"
        self.done = False
        self.handle = None
        self.owns_play = False
        self.settings = None
        self.saved_settings = {}
        self.settings_restored = False
        self.results = {}
        self.events = []
        self.provenance = {}
        self.classes = {}
        self.host = self.client = None
        self.sequence = self.waiting = None
        self.final_status = "not_run"
        self.reason = None
        self.last_startup_report = 0.0
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem) if unreal else None
        self.write("not_run")

    def write(self, status):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        report = {
            "status": status, "phase": self.phase,
            "scope": "same-process local listen-server/client PIE networking",
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "provenance": self.provenance, "events": self.events,
            "settings_restored": self.settings_restored, "reason": self.reason,
            "external_restore_required": net_mode_restore_actions(self.provenance),
            "not_covered": ["separate processes or remote machines", "internet/LAN discovery and sessions",
                            "latency, packet loss, disconnect or reconnect", "late joining",
                            "16 human connections", "movement reconciliation under adverse latency or loss",
                            "contested possession", "Hogwarts Legacy multiplayer"],
        }
        write_json_atomic(REPORT, report)

    def record(self, name, passed, **detail):
        if name not in TESTS or name in self.results:
            raise RuntimeError("Unknown or repeated case: " + name)
        self.results[name] = {"status": "passed" if passed else "failed", "detail": detail}
        unreal.log("BASKETBROOM NETWORK TEST %s: %s" % (self.results[name]["status"].upper(), name))
        self.write("running")

    @staticmethod
    def require(condition, message):
        if not condition:
            raise RuntimeError("Network test prerequisite: " + message)

    @staticmethod
    def worlds():
        return list(unreal.EditorLevelLibrary.get_pie_worlds(include_dedicated_server=True))

    def restore_settings(self):
        if self.settings is None:
            return
        for key, value in self.saved_settings.items():
            self.settings.set_editor_property(key, value)
        self.settings_restored = all(self.settings.get_editor_property(key) == value
                                     for key, value in self.saved_settings.items())
        self.require(self.settings_restored, "Play settings readback differs after restoration")

    def begin(self):
        if unreal is None:
            self.finish("not_run", "Run in the compiled UE5.8 editor; no network test was executed.")
            return False
        self.provenance["engine"] = unreal.SystemLibrary.get_engine_version()
        self.require(self.provenance["engine"].startswith("5.8."), "UE5.8 is required")
        if self.level.is_in_play_in_editor() or self.worlds():
            self.finish("not_run", "Stop the existing PIE session before running this suite.")
            return False
        for name in ("_basketbroom_native_test", "_basketbroom_native_network_test"):
            runner = getattr(unreal, name, None)
            if runner and not runner.done:
                self.finish("not_run", "Another native integration runner is active.")
                return False
        for name in ("BBGameMode", "BBMatchState", "BBRiderCharacter", "BBBall"):
            self.classes[name] = unreal.load_class(None, MODULE + name)
            if self.classes[name] is None:
                self.finish("not_run", "Native module is not loaded: " + MODULE + name)
                return False
        for name, methods in (("BBRiderCharacter", ("development_request_action", "development_set_interaction")),
                              ("BBBall", ("development_set_flight_fixture",))):
            cdo = unreal.get_default_object(self.classes[name])
            if not all(callable(getattr(cdo, method, None)) for method in methods):
                self.finish("not_run", "Rebuild the native PIE test hooks: " + name)
                return False
        settings_class = unreal.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings")
        self.require(settings_class is not None, "LevelEditorPlaySettings is not reflected")
        self.settings = unreal.get_default_object(settings_class)
        wanted = {"RunUnderOneProcess": True, "PlayNumberOfClients": 2, "bLaunchSeparateServer": False}
        if ARGS.get("settings_already_configured", False):
            # UE5.8 exposes these config/EditAnywhere settings but may omit
            # PlayNetMode's Python enum wrapper. The declared external source
            # records ordinary editor configuration, never raw-memory writes.
            # Header: UCLASS(config=EditorPerProjectUserSettings), line213;
            # PlayNetMode UPROPERTY(config, EditAnywhere), line385.
            source = str(ARGS.get("settings_source", "editor_ui"))
            self.require(source in ("editor_ui", "editor_config"), "Unknown preconfigured Play Net Mode source")
            self.provenance["net_mode_configuration_source"] = source
            self.provenance["net_mode_configured_in_editor"] = source == "editor_ui"
            if source == "editor_config":
                self.provenance["net_mode_config_entry"] = {
                    "file": "EditorPerProjectUserSettings.ini", "section": "/Script/UnrealEd.LevelEditorPlaySettings",
                    "key": "PlayNetMode", "declared_value": "PIE_ListenServer",
                    "verification": "Subsequent native world authority and owning-client checks; no absent enum readback is claimed",
                }
        else:
            net_mode = getattr(getattr(unreal, "PlayNetMode", None), "PIE_LISTEN_SERVER", None)
            if net_mode is None:
                self.finish("not_run", "Python net-mode enum is unavailable. Record the current editor Play Net Mode, "
                            "configure Play As Listen Server through its UI or the normal editor config with the editor closed, "
                            "then run with settings_already_configured=True and settings_source='editor_ui' or 'editor_config'. "
                            "Restore the original external setting afterward. No PIE session was started.")
                return False
            wanted["PlayNetMode"] = net_mode
        resolved = {}
        # These are UPROPERTY(EditAnywhere) in LevelEditorPlaySettings.h;
        # no protected engine or gameplay field is written by this suite.
        for name, value in wanted.items():
            key, old = property_slot(self.settings, name)
            self.saved_settings[key] = old
            resolved[key] = value
        self.provenance["original_play_settings"] = dict(self.saved_settings)
        self.provenance["requested_play_settings"] = dict(resolved)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        for key, value in resolved.items():
            self.settings.set_editor_property(key, value)
            self.require(self.settings.get_editor_property(key) == value, "Play setting did not change: " + key)
        self.owns_play = True
        self.phase = "waiting_for_two_worlds"
        # Keep settings stable across the entire asynchronous startup, despite
        # RequestPlaySession's native copy. Cleanup restores even failed runs.
        self.level.editor_request_begin_play()
        self.write("running")
        return True

    def actors(self, world, class_name):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, self.classes[class_name]))

    def context(self, world):
        matches = self.actors(world, "BBMatchState")
        riders = self.actors(world, "BBRiderCharacter")
        locals_ = [rider for rider in riders if rider.is_player_controlled() and rider.is_locally_controlled()]
        balls = self.actors(world, "BBBall")
        if len(matches) != 1 or len(riders) != 16 or len(locals_) != 1 or len(balls) != 7:
            return None
        if sum(rider.is_player_controlled() for rider in riders) != 2:
            return None
        return {"world": world, "match": matches[0], "pawn": locals_[0], "riders": riders,
                "balls": {int(prop(ball, "BallIndex")): ball for ball in balls}}

    @staticmethod
    def player_id(rider):
        state = prop(rider, "PlayerState")
        # BlueprintGetter UFUNCTIONs may become Python properties rather than
        # callable methods. PlayerId is the public reflected read-only field.
        return int(prop(state, "PlayerId")) if state else None

    def roster(self, side):
        return sorted((int(prop(r, "RosterIndex")), int(prop(r, "TeamIndex")), int(prop(r, "Position")))
                      for r in self.actors(side["world"], "BBRiderCharacter"))

    def human_roster(self, side):
        return sorted((self.player_id(r), int(prop(r, "RosterIndex")))
                      for r in self.actors(side["world"], "BBRiderCharacter") if r.is_player_controlled())

    def client_on_server(self):
        found = [r for r in self.host["riders"] if self.player_id(r) == self.player_id(self.client["pawn"])]
        self.require(len(found) == 1, "Client identity does not have exactly one server pawn")
        return found[0]

    def setup(self):
        worlds = self.worlds()
        observed = []
        for world in worlds:
            riders = self.actors(world, "BBRiderCharacter")
            matches = self.actors(world, "BBMatchState")
            observed.append({"world": world.get_path_name(), "native_riders": len(riders),
                             "humans": sum(r.is_player_controlled() for r in riders),
                             "local_humans": sum(r.is_player_controlled() and r.is_locally_controlled() for r in riders),
                             "native_matches": len(matches),
                             "authoritative": matches[0].has_authority() if matches else None})
        self.provenance["observed_worlds"] = observed
        if len(worlds) != 2:
            return False
        contexts = [self.context(world) for world in worlds]
        if any(side is None for side in contexts):
            return False
        servers = [side for side in contexts if side["match"].has_authority()]
        clients = [side for side in contexts if not side["match"].has_authority()]
        if len(servers) != 1 or len(clients) != 1:
            return False
        self.host, self.client = servers[0], clients[0]
        if self.player_id(self.host["pawn"]) == self.player_id(self.client["pawn"]):
            return False
        self.provenance["worlds"] = {name: side["world"].get_path_name()
                                     for name, side in (("server", self.host), ("client", self.client))}
        self.provenance["human_player_ids"] = [self.player_id(self.host["pawn"]), self.player_id(self.client["pawn"])]
        self.phase = "running_cases"
        self.sequence = self.scenarios()
        self.advance()
        return True

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.host["world"]))

    @staticmethod
    def scores(side):
        return [int(prop(side["match"], "TealScore")), int(prop(side["match"], "CopperScore"))]

    @staticmethod
    def live(side):
        return bool(prop(side["match"], "bLive"))

    def snapshot(self, side):
        return {name: prop(side["match"], name) for name in
                ("Phase", "Status", "Quarter", "bLive", "TealScore", "CopperScore", "SecondsLeft")}

    def request(self, side, action, value=0):
        self.require(side["pawn"].development_request_action(action, value), "PIE input bridge rejected submission")
        self.events.append({"input": action, "value": value, "player_id": self.player_id(side["pawn"]),
                            "server_time": round(self.now(), 3)})

    @staticmethod
    def wait(seconds=0.6, predicate=None, fixture=None):
        return {"seconds": seconds, "predicate": predicate, "fixture": fixture}

    def isolate_server(self):
        # Only this owned PIE world is arranged. Keep CPUs within relevancy,
        # above all scoring equipment, and disable their movement component.
        # Rules, scores, ownership and all replicated fields remain untouched.
        for rider in self.host["riders"]:
            if rider.is_player_controlled():
                continue
            movement = rider.get_component_by_class(unreal.CharacterMovementComponent)
            self.require(movement is not None, "CPU CharacterMovement component is missing")
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
            rider.set_actor_tick_enabled(False)
            rider.consume_movement_input_vector()
            slot = int(prop(rider, "RosterIndex"))
            rider.set_actor_location(vec(-1400 + slot * 175, 2300, 5700), False, True)
        for ball in self.host["balls"].values():
            ball.set_actor_tick_enabled(False)

    def scenarios(self):
        native_server = unreal.GameplayStatics.get_game_mode(self.host["world"])
        native_client = unreal.GameplayStatics.get_game_mode(self.client["world"])
        self.record(TESTS[0], self.host["world"] != self.client["world"] and native_server is not None
                    and native_server.get_class() == self.classes["BBGameMode"] and native_client is None
                    and self.host["pawn"].has_authority() and not self.client["pawn"].has_authority(),
                    worlds=self.provenance["worlds"])
        expected = [(slot, slot // 8, ROLES[slot % 8]) for slot in range(16)]
        self.record(TESTS[1], self.roster(self.host) == self.roster(self.client) == expected,
                    server=self.roster(self.host), client=self.roster(self.client))
        self.record(TESTS[2], self.human_roster(self.host) == self.human_roster(self.client)
                    and len({row[0] for row in self.human_roster(self.host)}) == 2,
                    server=self.human_roster(self.host), client=self.human_roster(self.client))
        self.require(not self.live(self.host) and not self.live(self.client), "Fresh match must be in lobby")
        self.request(self.client, 2, 1)
        role_ok = lambda: int(prop(self.client["pawn"], "Position")) == int(prop(self.client_on_server(), "Position")) == 1
        yield self.wait(6, role_ok)
        self.record(TESTS[3], role_ok() and self.roster(self.host) == self.roster(self.client) == expected,
                    client_position=prop(self.client["pawn"], "Position"), server_position=prop(self.client_on_server(), "Position"))
        self.require(role_ok(), "Client role RPC must work before testing rejection of host-only requests")
        self.require(self.client["pawn"].development_set_interaction(True), "Client interaction submission")
        held = lambda: bool(prop(self.client_on_server(), "bInteractHeld")) and bool(prop(self.client["pawn"], "bInteractHeld"))
        yield self.wait(5, held)
        held_ok = held()
        self.client["pawn"].development_set_interaction(False)
        released = lambda: not prop(self.client_on_server(), "bInteractHeld") and not prop(self.client["pawn"], "bInteractHeld")
        yield self.wait(5, released)
        self.record(TESTS[4], held_ok and released(), held_replicated=held_ok, release_replicated=released())
        before = float(prop(self.host["match"], "SecondsLeft"))
        self.request(self.client, 4)
        yield self.wait(1)
        self.record(TESTS[5], not self.live(self.host) and not self.live(self.client)
                    and abs(float(prop(self.host["match"], "SecondsLeft")) - before) < .02,
                    server=self.snapshot(self.host), client=self.snapshot(self.client))
        self.require(not self.live(self.host), "Unauthorized client started match")
        self.isolate_server()
        self.request(self.host, 4)
        both_live = lambda: self.live(self.host) and self.live(self.client)
        yield self.wait(6, both_live)
        self.record(TESTS[6], both_live() and float(prop(self.host["match"], "SecondsLeft")) < before,
                    server=self.snapshot(self.host), client=self.snapshot(self.client))
        self.require(both_live(), "Host could not start both network worlds")
        self.isolate_server()  # Kickoff moves CPU riders back to their legal marks.
        before_pause = float(prop(self.host["match"], "SecondsLeft"))
        self.request(self.client, 5)
        yield self.wait(1)
        self.record(TESTS[7], both_live() and float(prop(self.host["match"], "SecondsLeft")) < before_pause - .2,
                    server=self.snapshot(self.host), client=self.snapshot(self.client))
        self.require(both_live(), "Unauthorized client stopped match")
        # Feed real client movement input. CharacterMovement sends its own
        # saved moves from native Tick, outside the reflected Python guard.
        remote = self.client_on_server()
        client_pawn = self.client["pawn"]
        origin = remote.get_actor_location()
        start = vec(origin.x, origin.y, origin.z)
        yield self.wait(.65, fixture=lambda: client_pawn.add_movement_input(vec(0,1,0), 1.0, False))
        yield self.wait(.8)
        server_position = remote.get_actor_location()
        client_position = client_pawn.get_actor_location()
        travelled = (server_position - start).length()
        disagreement = (server_position - client_position).length()
        self.record("client_flight_reaches_server", travelled > 150 and disagreement < 150,
                    server_distance_cm=travelled, client_server_distance_cm=disagreement,
                    input="client AddMovementInput through CharacterMovement saved moves")
        self.require(travelled > 150, "Client movement never reached authority")

        # Wait for both predicted movement and its authority to settle before
        # placing pickup equipment. This also works under editor throttling.
        settled = lambda: remote.get_velocity().length() < 5 and client_pawn.get_velocity().length() < 5
        yield self.wait(5, settled)
        self.require(settled(), "Client movement did not settle before the pickup fixture")
        server_position = remote.get_actor_location()

        # Place an unheld Quark nearby on authority, then request ordinary
        # pickup and throw from its owning client. Never set Holder directly.
        quark, client_quark = self.host["balls"][1], self.client["balls"][1]
        self.require(prop(quark,"Holder") is None and prop(quark,"bActive"), "Pickup needs free active Quark")
        self.require(quark.development_set_flight_fixture(server_position + vec(-200,0,0), vec(0,0,0)), "Quark fixture rejected")
        # Opening ResetBall sets a pickup grace period. Let normal ball Tick
        # expire it; freezing all equipment would otherwise preserve it forever.
        quark.set_actor_tick_enabled(True)
        yield self.wait(.4)
        self.require(client_pawn.development_set_interaction(True), "Client pickup input rejected")
        owned = lambda: prop(quark,"Holder") == remote and prop(client_quark,"Holder") == client_pawn
        yield self.wait(6, owned)
        self.record("client_pickup_replicates_possession", owned(),
                    server_holder_matches=prop(quark,"Holder") == remote,
                    client_holder_matches=prop(client_quark,"Holder") == client_pawn,
                    server_distance_cm=(quark.get_actor_location()-remote.get_actor_location()).length(),
                    server_interact=bool(prop(remote,"bInteractHeld")),
                    client_interact=bool(prop(client_pawn,"bInteractHeld")),
                    server_role=int(prop(remote,"Position")),
                    ball_active=bool(prop(quark,"bActive")),
                    ball_status=str(prop(quark,"BallStatus")))
        self.require(owned(), "Client pickup did not replicate possession")
        client_pawn.development_set_interaction(False)
        yield self.wait(.4, lambda: not prop(remote,"bInteractHeld"))
        self.request(self.client, 1)
        thrown = lambda: prop(quark,"Holder") is None and prop(client_quark,"Holder") is None and quark.get_flight_velocity().length() > 1000 and client_quark.get_flight_velocity().length() > 1000
        yield self.wait(6, thrown)
        self.record("client_throw_replicates_release", thrown(),
                    server_speed_cm_s=quark.get_flight_velocity().length(),
                    client_speed_cm_s=client_quark.get_flight_velocity().length())
        self.require(thrown(), "Client throw did not reach authority and replicate")
        before = self.scores(self.host)
        client_attempt = self.client["balls"][0].development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 2103.12), vec(2000, 0, 0))
        yield self.wait(.5)
        self.record(TESTS[8], not client_attempt and self.scores(self.host) == self.scores(self.client) == before,
                    fixture_return=client_attempt, server_scores=self.scores(self.host), client_scores=self.scores(self.client))
        ball = self.host["balls"][0]
        self.require(prop(ball, "Holder") is None and prop(ball, "bActive"), "Goal fixture needs an active, free Quaffle")
        self.require(ball.development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 2103.12), vec(2000, 0, 0)), "Server flight fixture rejected")
        ball.set_actor_tick_enabled(True)
        self.events.append({"fixture": "server Quaffle 2000 cm/s through positive-X large hoop", "scores_before": before})
        expected_scores = [before[0] + 13, before[1]]
        scored = lambda: self.scores(self.host) == self.scores(self.client) == expected_scores
        yield self.wait(6, scored)
        self.record(TESTS[9], scored(), expected=expected_scores,
                    server=self.scores(self.host), client=self.scores(self.client))
        self.require(scored(), "Actual server ball crossing did not score and replicate")
        ball.set_actor_tick_enabled(False)
        yield self.wait(1)
        self.record(TESTS[10], scored(), server=self.scores(self.host), client=self.scores(self.client))
        self.request(self.host, 5)
        stopped = lambda: not self.live(self.host) and not self.live(self.client) and str(prop(self.client["match"], "Status")) == "STOPPAGE"
        yield self.wait(6, stopped)
        self.record(TESTS[11], stopped(), server=self.snapshot(self.host), client=self.snapshot(self.client))
        stop_time = float(prop(self.host["match"], "SecondsLeft"))
        yield self.wait(1)
        server, client = self.snapshot(self.host), self.snapshot(self.client)
        self.record(TESTS[12], stopped() and server == client and abs(server["SecondsLeft"] - stop_time) < .02
                    and self.roster(self.host) == self.roster(self.client) == expected and scored(),
                    server=server, client=client)

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            self.waiting.update(start=self.now(), wall=time.monotonic(), samples=0)
        except StopIteration:
            self.finish("passed" if all(row["status"] == "passed" for row in self.results.values()) else "failed")

    def tick(self, delta):
        if self.done:
            return
        try:
            if self.phase == "ending_pie":
                if not self.worlds() and not self.level.is_in_play_in_editor():
                    self.complete()
                elif time.monotonic() - self.cleanup_started > 20:
                    self.final_status = "error"
                    self.reason = (self.reason or "") + " PIE did not end within 20 seconds."
                    self.complete()
                return
            elapsed = time.monotonic() - self.started
            if elapsed > float(ARGS.get("max_wall_seconds", 180)):
                raise TimeoutError("Local network suite exceeded its wall-time limit")
            if self.phase == "waiting_for_two_worlds":
                if not self.setup() and elapsed > 60:
                    self.finish("failed", "Two complete connected native PIE worlds did not appear within 60 seconds.")
                elif self.phase == "waiting_for_two_worlds" and elapsed - self.last_startup_report > 5:
                    self.last_startup_report = elapsed
                    self.write("running")
                return
            if len(self.worlds()) != 2 or not self.level.is_in_play_in_editor():
                raise RuntimeError("A network PIE world ended before testing completed")
            if self.waiting:
                wait = self.waiting
                if wait.get("fixture"):
                    wait["fixture"]()
                wait["samples"] += 1
                elapsed_game = self.now() - wait["start"]
                satisfied = wait["predicate"] is not None and elapsed_game >= .15 and wait["predicate"]()
                if wait["samples"] >= 3 and (satisfied or elapsed_game >= wait["seconds"]):
                    self.advance()
                elif time.monotonic() - wait["wall"] > 30:
                    raise TimeoutError("Network PIE simulation time stalled")
        except Exception:
            self.finish("error", traceback.format_exc())

    def finish(self, status, reason=None):
        self.final_status, self.reason = status, reason
        try:
            self.restore_settings()
            for side in (self.host, self.client):
                if side:
                    side["pawn"].development_set_interaction(False)
        except Exception:
            self.final_status = "error"
            self.reason = (self.reason or "") + "\nCleanup: " + traceback.format_exc()
        if self.owns_play:
            self.phase = "ending_pie"
            self.cleanup_started = time.monotonic()
            self.level.editor_request_end_play()
            self.write("running")
        else:
            self.complete()

    def complete(self):
        ended = unreal is not None and not self.worlds() and not self.level.is_in_play_in_editor()
        if self.owns_play:
            self.record(TESTS[-1], self.settings_restored and ended,
                        settings_restored=self.settings_restored, no_pie_worlds=ended)
            if not self.settings_restored or not ended:
                self.final_status = "error"
        self.done = True
        if unreal and self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if self.final_status == "passed" and len(self.results) != len(TESTS):
            self.final_status = "failed"
        self.phase = "complete"
        self.write(self.final_status)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "scope": "two local PIE worlds in one editor process",
                "planned_tests": list(TESTS), "count": len(TESTS)}
    runner = NativeNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(REPORT), "planned_cases": len(TESTS)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
