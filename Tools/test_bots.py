"""Verify compiled bot gameplay in a real UE 5.8 Play In Editor world.

Run through editor_bridge.py after stage_bots.py. The script returns promptly;
Slate callbacks write .local/bot-test-results.json. Default duration is about
30 game seconds: live scrimmage, isolated native shot cycles, and guard checks.
Python only arranges PIE test fixtures and observes Blueprint behavior; it never
assigns possession, velocity, or scores during an observed shot cycle.
"""
import json
from pathlib import Path
import re
import time
import traceback

import unreal


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "bot-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})


def prop(actor, name, value=...):
    names = (name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
    last_error = None
    for candidate in names:
        try:
            if value is ...:
                return actor.get_editor_property(candidate)
            actor.set_editor_property(candidate, value)
            return value
        except Exception as error:
            last_error = error
    raise last_error


def vector(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def xyz(value):
    return [round(value.x, 3), round(value.y, 3), round(value.z, 3)]


class BotTests:
    def __init__(self):
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.started = time.monotonic()
        self.phase = "waiting_for_world"
        self.phase_started = 0.0
        self.phase_wall_started = self.started
        self.world = None
        self.manager = None
        self.pawn = None
        self.bots = []
        self.balls = []
        self.hazards = []
        self.results = []
        self.events = []
        self.snapshot = None
        self.handle = None
        self.may_manage_play = False
        self.done = False
        self.shot = None
        self.last_ball_samples = {}
        self.scrimmage_seconds = max(5.0, min(45.0, float(ARGS.get("scrimmage_seconds", 20.0))))
        self.write_report("running")

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def set_phase(self, phase):
        self.phase = phase
        self.phase_started = self.now()
        self.phase_wall_started = time.monotonic()
        self.write_report("running")

    def scores(self):
        return [int(prop(self.manager, "TealScore")), int(prop(self.manager, "CopperScore"))]

    def write_report(self, status, error=None):
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "status": status, "phase": self.phase,
            "engine": unreal.SystemLibrary.get_engine_version(),
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 2),
            "scrimmage_seconds": self.scrimmage_seconds,
            "passed": sum(row["passed"] for row in self.results),
            "failed": sum(not row["passed"] for row in self.results),
            "tests": self.results, "observed_native_events": self.events,
            "scope": "PIE Blueprint bots, possession, ballistic scoring, and match guards",
            "limitations": ["Hurleybacks and Scouts are patrol-only in this slice",
                            "Human is designated Teal Ranger by the staging contract"],
        }
        if error:
            data["error"] = error
        REPORT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def record(self, name, passed, detail):
        self.results.append({"name": name, "passed": bool(passed), "detail": detail})
        unreal.log("BASKETBROOM BOT TEST {}: {} | {}".format(
            "PASS" if passed else "FAIL", name, detail))
        self.write_report("running")

    def event(self, kind, **detail):
        if len(self.events) < 120:
            self.events.append({"phase": self.phase, "game_seconds": round(self.now(), 3),
                                "kind": kind, **detail})

    def begin(self):
        if self.level.is_in_play_in_editor() and not ARGS.get("reuse_play", False):
            raise RuntimeError("A PIE session exists; end it or set reuse_play=True")
        self.may_manage_play = True
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        if not self.level.is_in_play_in_editor():
            self.level.editor_request_begin_play()

    def setup_world(self):
        self.world = self.editor.get_game_world()
        if self.world is None:
            return
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.Actor)
        managers = [a for a in actors if a.get_class().get_name().startswith("BP_BBMatch")]
        self.bots = [a for a in actors if a.get_class().get_name().startswith("BP_BBBot")]
        self.balls = [a for a in actors if a.get_class().get_name().startswith("BP_BBBall")]
        self.hazards = [a for a in actors if a.get_class().get_name().startswith(
            ("BP_BBBludger", "BP_BBHazard"))]
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if not managers or not self.pawn:
            return
        self.manager = managers[0]
        self.set_phase("warmup")

    def snapshot_world(self):
        manager_fields = ("TealScore", "CopperScore", "HasBall", "MatchOver", "SecondsLeft",
                          "Elapsed", "Stun", "Message")
        ball_fields = ("Kind", "Held", "Cooldown", "CatchTime", "P", "OldP", "Velocity", "Home",
                       "BotOwner", "BotPosition")
        # Only snapshot fields the fixture mutates. Rest and Match are runtime
        # state and cannot be assigned on Blueprint instances through Python.
        bot_fields = ("Team", "Slot", "PlayerRole", "Home", "Target")
        actor_rows = []
        for actor, fields in ([(a, ball_fields) for a in self.balls]
                              + [(a, bot_fields) for a in self.bots]
                              + [(a, ()) for a in self.hazards] + [(self.pawn, ())]):
            actor_rows.append({"actor": actor, "location": actor.get_actor_location(),
                               "rotation": actor.get_actor_rotation(),
                               "tick": actor.is_actor_tick_enabled(),
                               "fields": {name: prop(actor, name) for name in fields}})
        self.snapshot = {"manager": {name: prop(self.manager, name) for name in manager_fields},
                         "actors": actor_rows}

    def initialize(self):
        self.snapshot_world()
        self.record("fifteen_native_cpu_riders", len(self.bots) == 15,
                    {"bots": len(self.bots), "pawn_class": self.pawn.get_class().get_name()})
        roster = [{"slot": int(prop(a, "Slot")), "team": int(prop(a, "Team")),
                   "role": int(prop(a, "PlayerRole"))} for a in self.bots]
        counts = {team: {role: sum(r["team"] == team and r["role"] == role for r in roster)
                        for role in range(6)} for team in (0, 1)}
        # Teal's human occupies the Ranger slot; Copper's Ranger is a bot.
        expected = {0: {0: 1, 1: 2, 2: 1, 3: 0, 4: 2, 5: 1},
                    1: {0: 1, 1: 2, 2: 1, 3: 1, 4: 2, 5: 1}}
        human = self.pawn.get_class().get_name().startswith("BP_BBBroom")
        self.record("eight_per_side_including_human_ranger", human and counts == expected,
                    {"cpu_role_counts": counts, "expected": expected,
                     "human_team": 0, "human_role": 3})
        slots = [row["slot"] for row in roster]
        self.record("unique_nonhuman_possession_slots", sorted(slots) == list(range(1, 16)), slots)
        targets_valid = all(prop(a, "Target") in self.balls and prop(a, "Match") == self.manager
                            and int(prop(prop(a, "Target"), "Kind")) in (0, 1) for a in self.bots)
        self.record("bot_target_and_match_references", bool(self.bots) and targets_valid,
                    {"balls": len(self.balls), "valid": targets_valid})
        if not self.bots or not targets_valid:
            raise RuntimeError("Staging is incomplete; native bot scenarios require valid targets")
        self.slot_to_bot = {int(prop(a, "Slot")): a for a in self.bots}
        self.start_positions = {int(prop(a, "Slot")): a.get_actor_location() for a in self.bots}
        self.moved_slots = set()
        self.live_flags = {"claim": False, "carry": False, "release": False}
        self.live_start_scores = self.scores()
        self.pawn.set_actor_tick_enabled(False)
        self.pawn.set_actor_location(vector(0, -2300, 3700), False, True)
        prop(self.manager, "MatchOver", False)
        prop(self.manager, "SecondsLeft", 300.0)
        self.set_phase("live_scrimmage")

    def observe_live(self):
        for bot in self.bots:
            slot = int(prop(bot, "Slot"))
            if (bot.get_actor_location() - self.start_positions[slot]).length() > 150:
                self.moved_slots.add(slot)
        for ball in self.balls:
            if int(prop(ball, "Kind")) not in (0, 1):
                continue
            name = ball.get_name()
            owner = int(prop(ball, "BotOwner"))
            pos = ball.get_actor_location()
            previous = self.last_ball_samples.get(name)
            if owner >= 0 and (not previous or previous[0] != owner):
                self.live_flags["claim"] = True
                self.event("cpu_claim", ball=name, slot=owner)
            if owner >= 0 and previous and previous[0] == owner:
                if (pos - previous[1]).length() > 1:
                    self.live_flags["carry"] = True
            if owner < 0 and previous and previous[0] >= 0:
                velocity = prop(ball, "Velocity")
                if abs(velocity.x) > 300 and not bool(prop(ball, "Held")):
                    self.live_flags["release"] = True
                    self.event("cpu_shot", ball=name, slot=previous[0], velocity=xyz(velocity))
            self.last_ball_samples[name] = (owner, pos)

    def finish_scrimmage(self):
        score_delta = [a - b for a, b in zip(self.scores(), self.live_start_scores)]
        self.record("autonomous_riders_move", len(self.moved_slots) >= 10,
                    {"moved_slots": sorted(self.moved_slots), "threshold_cm": 150})
        self.record("live_scrimmage_native_possession_cycle", all(self.live_flags.values()),
                    self.live_flags.copy())
        self.record("live_scrimmage_scores_without_injection", any(n > 0 for n in score_delta),
                    {"score_delta": score_delta, "observed_game_seconds": self.scrimmage_seconds})
        self.prepare_shot(team=0, kind=0)

    def reset_isolated(self):
        for name, value in {"TealScore": 0, "CopperScore": 0, "HasBall": False,
                            "MatchOver": False, "SecondsLeft": 300.0, "Stun": 0.0,
                            "Message": "CPU INTEGRATION TEST"}.items():
            prop(self.manager, name, value)
        for actor in self.bots + self.balls + self.hazards:
            actor.set_actor_tick_enabled(False)
        for ball in self.balls:
            prop(ball, "Held", False)
            prop(ball, "BotOwner", -1)
            prop(ball, "Cooldown", 1000.0)
            prop(ball, "Velocity", vector(0, 0, 0))
        self.pawn.set_actor_location(vector(0, -2300, 3700), False, True)

    def prepare_shot(self, team, kind):
        self.reset_isolated()
        bot = next(a for a in self.bots if int(prop(a, "Team")) == team
                   and int(prop(a, "PlayerRole")) == 1)
        ball = next(a for a in self.balls if int(prop(a, "Kind")) == kind)
        sign = 1 if team == 0 else -1
        goal_z = 2103.12 if kind == 0 else 3048.0
        bot_pos = vector(sign * 1000, 0, goal_z - 60)
        ball_pos = vector(sign * 1200, 0, goal_z)
        bot.set_actor_location(bot_pos, False, True)
        prop(bot, "Home", bot_pos)
        prop(bot, "Target", ball)
        ball.set_actor_location(ball_pos, False, True)
        for name in ("P", "OldP", "Home", "BotPosition"):
            prop(ball, name, ball_pos)
        prop(ball, "Cooldown", 0.0)
        prop(ball, "CatchTime", 0.0)
        bot.set_actor_tick_enabled(True)
        ball.set_actor_tick_enabled(True)
        self.shot = {"bot": bot, "ball": ball, "team": team, "kind": kind,
                     "slot": int(prop(bot, "Slot")), "sign": sign, "start": bot_pos,
                     "initial_rest": float(prop(bot, "Rest")), "claim_position": None,
                     "claim": False, "carry": False, "release": False, "score": False,
                     "max_carry_distance": 0.0, "release_velocity": None,
                     "expected_score": 13 if kind == 0 else 37}
        self.set_phase("teal_quaffle_cycle" if team == 0 else "copper_quark_cycle")

    def observe_shot(self):
        case = self.shot
        ball, bot = case["ball"], case["bot"]
        owner = int(prop(ball, "BotOwner"))
        if owner == case["slot"]:
            if not case["claim"]:
                self.event("isolated_cpu_claim", slot=owner, ball=ball.get_name())
                case["claim_position"] = bot.get_actor_location()
            case["claim"] = True
            distance = (bot.get_actor_location() - case["claim_position"]).length()
            case["max_carry_distance"] = max(case["max_carry_distance"], distance)
            pocket = prop(ball, "BotPosition")
            attached = (ball.get_actor_location() - pocket).length() < 250
            case["carry"] = case["carry"] or (distance > 150 and attached)
        velocity = prop(ball, "Velocity")
        if (case["claim"] and owner == -1 and velocity.x * case["sign"] > 500
                and float(prop(bot, "Rest")) > 0 and not bool(prop(ball, "Held"))):
            if not case["release"]:
                self.event("isolated_cpu_release", slot=case["slot"], velocity=xyz(velocity))
                case["release_velocity"] = xyz(velocity)
            case["release"] = True
        expected = [0, 0]
        expected[case["team"]] = case["expected_score"]
        case["score"] = case["score"] or self.scores() == expected
        return all(case[name] for name in ("claim", "carry", "release", "score"))

    def finish_shot(self):
        case = self.shot
        name = self.phase
        detail = {"slot": case["slot"], "claim": case["claim"], "carry": case["carry"],
                  "release": case["release"], "score": case["score"],
                  "max_carry_distance_cm": round(case["max_carry_distance"], 2),
                  "initial_rest_seconds": case["initial_rest"],
                  "release_velocity": case["release_velocity"], "scores": self.scores(),
                  "expected_points": case["expected_score"]}
        self.record(name + "_claims_and_carries", case["claim"] and case["carry"], detail)
        self.record(name + "_releases_ballistic_shot", case["release"], detail)
        self.record(name + "_scores_correct_goal", case["release"] and case["score"], detail)
        if case["team"] == 0:
            self.prepare_shot(team=1, kind=1)
        else:
            self.prepare_human_held()

    def prepare_human_held(self):
        self.reset_isolated()
        self.guard_ball = next(a for a in self.balls if int(prop(a, "Kind")) == 0)
        self.guard_bot = next(a for a in self.bots if int(prop(a, "PlayerRole")) == 1)
        self.pawn.set_actor_location(vector(0, 0, 1800), False, True)
        self.guard_ball.set_actor_location(vector(50, 0, 1800), False, True)
        prop(self.guard_ball, "Held", True)
        prop(self.guard_ball, "Cooldown", 0.0)
        prop(self.manager, "HasBall", True)
        self.guard_bot.set_actor_location(vector(50, 0, 1740), False, True)
        prop(self.guard_bot, "Home", vector(50, 0, 1740))
        prop(self.guard_bot, "Target", self.guard_ball)
        self.guard_bot.set_actor_tick_enabled(True)
        self.guard_ball.set_actor_tick_enabled(True)
        self.human_guard_ok = True
        self.guard_samples = 0
        self.guard_eligible_samples = 0
        self.guard_ready_time = None
        self.set_phase("human_held_protection")

    def finish_human_held(self):
        self.record("cpu_cannot_acquire_human_held_ball", self.human_guard_ok and self.guard_eligible_samples >= 2,
                    {"samples": self.guard_samples, "bot_owner": int(prop(self.guard_ball, "BotOwner")),
                     "samples_after_native_rest_expired": self.guard_eligible_samples,
                     "held": bool(prop(self.guard_ball, "Held")), "scores": self.scores(),
                     "fixture": "candidate repeatedly placed within 60 cm of held target"})
        # Enable every bot before the stop guard. Read the native Rest timers;
        # they cannot be assigned through editor properties on instances.
        for bot in self.bots:
            bot.set_actor_tick_enabled(True)
        prop(self.manager, "MatchOver", True)
        self.frozen = [(a, a.get_actor_location(), a.get_actor_rotation(), float(prop(a, "Rest")))
                       for a in self.bots]
        self.freeze_ok = True
        self.freeze_samples = 0
        self.set_phase("match_over_freeze")

    def tick(self, delta):
        if self.done:
            return
        try:
            if time.monotonic() - self.started > 240:
                raise TimeoutError("Bot integration tests exceeded 240 wall seconds")
            if self.phase == "waiting_for_world":
                self.setup_world()
                return
            if not self.level.is_in_play_in_editor():
                raise RuntimeError("PIE ended before native bot verification finished")
            elapsed = self.now() - self.phase_started
            if time.monotonic() - self.phase_wall_started > 90 and elapsed < 0.1:
                raise TimeoutError("PIE game time did not advance")
            if self.phase == "warmup" and elapsed >= 0.4:
                self.initialize()
            elif self.phase == "live_scrimmage":
                self.observe_live()
                if elapsed >= self.scrimmage_seconds:
                    self.finish_scrimmage()
            elif self.phase in ("teal_quaffle_cycle", "copper_quark_cycle"):
                complete = self.observe_shot()
                # A prior native shot can leave up to two seconds of Rest.
                # Let the actual bot timer expire instead of assigning it.
                if complete or elapsed >= 14.0:
                    self.finish_shot()
            elif self.phase == "human_held_protection":
                self.guard_samples += 1
                if float(prop(self.guard_bot, "Rest")) < 0.001:
                    self.guard_eligible_samples += 1
                    if self.guard_ready_time is None:
                        self.guard_ready_time = self.now()
                self.human_guard_ok = self.human_guard_ok and (
                    int(prop(self.guard_ball, "BotOwner")) == -1
                    and bool(prop(self.guard_ball, "Held")) and bool(prop(self.manager, "HasBall"))
                    and self.scores() == [0, 0])
                # Keep the candidate in pickup range despite its fallback
                # patrol. This fixture tests the Held guard, not pursuit speed.
                self.guard_bot.set_actor_location(
                    self.guard_ball.get_actor_location() - vector(0, 0, 60), False, True)
                if ((self.guard_ready_time is not None and self.now() - self.guard_ready_time >= 1.5)
                        or elapsed >= 5.0):
                    self.finish_human_held()
            elif self.phase == "match_over_freeze":
                self.freeze_samples += 1
                for bot, pos, rot, rest in self.frozen:
                    current_rot = bot.get_actor_rotation()
                    self.freeze_ok = self.freeze_ok and (
                        (bot.get_actor_location() - pos).length() < 0.01
                        and abs(float(prop(bot, "Rest")) - rest) < 0.00001
                        and abs(current_rot.pitch - rot.pitch) < 0.001
                        and abs(current_rot.yaw - rot.yaw) < 0.001
                        and abs(current_rot.roll - rot.roll) < 0.001)
                if elapsed >= 1.0:
                    self.record("match_over_stops_all_native_bot_updates",
                                self.freeze_ok and self.freeze_samples >= 2,
                                {"bots": len(self.bots), "samples": self.freeze_samples,
                                 "positive_rest_bots": sum(row[3] > 0 for row in self.frozen),
                                 "checked": ["location", "rotation", "Rest timer"]})
                    self.finish()
        except Exception:
            self.finish(traceback.format_exc())

    def restore(self):
        for name, value in self.snapshot["manager"].items():
            prop(self.manager, name, value)
        for row in self.snapshot["actors"]:
            actor = row["actor"]
            for name, value in row["fields"].items():
                prop(actor, name, value)
            actor.set_actor_location(row["location"], False, True)
            actor.set_actor_rotation(row["rotation"], True)
            actor.set_actor_tick_enabled(row["tick"])

    def finish(self, error=None):
        self.done = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        try:
            if ARGS.get("leave_play", False) and self.snapshot and not error:
                self.restore()
            elif self.may_manage_play and self.level.is_in_play_in_editor():
                self.level.editor_request_end_play()
        except Exception:
            error = (error or "") + "\nPIE cleanup: " + traceback.format_exc()
            if self.may_manage_play and self.level.is_in_play_in_editor():
                self.level.editor_request_end_play()
        status = "error" if error else (
            "passed" if self.results and all(row["passed"] for row in self.results) else "failed")
        self.write_report(status, error)
        unreal.log("BASKETBROOM BOT TESTS {}: {}".format(status.upper(), REPORT))


previous = getattr(unreal, "_basketbroom_bot_test", None)
if previous and not previous.done:
    raise RuntimeError("A Basketbroom bot test is already running")
other = getattr(unreal, "_basketbroom_playable_test", None)
if other and not other.done:
    raise RuntimeError("The playable integration test is still running")
test = BotTests()
try:
    test.begin()
except Exception:
    test.finish(traceback.format_exc())
    raise
unreal._basketbroom_bot_test = test
RESULT = {"status": "started", "report": str(REPORT), "expected_cases": 15}
