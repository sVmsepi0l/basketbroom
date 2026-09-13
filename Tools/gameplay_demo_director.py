"""Direct an actual native Basketbroom prototype take in disposable Practice PIE.

Bridge operations: prepare, start, inspect, stop. Prepare requires the capture
helper's fresh Practice lobby; start synchronizes its public start_capture hook.
The normal take is 180 game seconds, at the capture helper's fixed frame rate.
duration_seconds (5..180) permits a short camera/capture smoke test.

All gameplay results come from the native game. The director submits ordinary
guarded local input and arranges physical transforms/ball launch velocities.
It never writes scores, clocks, ball custody/availability, spell effects, hit
receipts, penalties, or rules. CPU positions and camera paths are staged;
native rider flight is driven by AddMovementInput. The final 1-second chase
holds use a disclosed proximity fixture, not an assertion of autonomous skill.
No editor-world actor or asset is changed or saved. This is not a multiplayer
or Hogwarts Legacy integration demonstration. Keep the manifest with the take.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
import traceback

import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/gameplay-demo-director.json"
RUNNER = "_basketbroom_gameplay_demo_director"
ARGS = globals().get("BRIDGE_ARGS", {})
MODULE = "/Script/BasketbroomRuntime."

SHOTS = [
    (0, 12, "WELCOME TO BASKETBROOM", "A playable Unreal Engine 5.8 prototype", "arena crane"),
    (12, 28, "OWN THE AIR", "Six positions. Three dimensions.", "tracking flight / cockpit"),
    (28, 47, "QUAFFLE  /  13 POINTS", "Collect. Line up. Put the whole ball through a large hoop.", "approach / native throw"),
    (47, 63, "QUARK  /  37 POINTS", "The smaller, higher hoop rewards precision.", "goal profile / ball follow"),
    (63, 80, "SNIPE  /  69 POINTS", "Ranger: hold catch within 3.8 metres for one continuous second.", "chase close-up / catch HUD"),
    (80, 95, "THE HURLEYBACK", "Switch positions at an official stoppage. Control and release a Bludger.", "role guide / release"),
    (95, 109, "WANDWORK IN FLIGHT", "Protego, Lumos and offensive spell adaptations.", "cockpit / opposing rider"),
    (109, 120, "MOVE THE OPPOSITION", "Real pull, push and lift effects within the flight arena.", "rider profile / native cast"),
    (120, 139, "BB-0  /  APPLY THE HIT, THEN PENALIZE", "A confirmed impediment followed by a stun triggers a double-tap review.", "native HUD / referee resolution"),
    (139, 151, "NO CROWN", "A scoring ball crossing the open crown becomes dead and returns.", "high tracking shot / return"),
    (151, 170, "SNITCH  /  150 POINTS", "Scout: secure the catch. Practice release follows 60 live seconds.", "wing detail / pursuit / catch"),
    (170, 180, "THE MATCH-ENDING CATCH", "Actual prototype gameplay. Automated and staged for this showcase.", "result HUD / arena pullback"),
]


def prop(obj, name):
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for key in aliases:
        try:
            return obj.get_editor_property(key)
        except Exception:
            pass
    raise RuntimeError("Native property unavailable: " + name)


def presentation_property(obj, name, value):
    for key in (name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower(),
                re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower() if name.startswith("b") else name):
        try:
            obj.set_editor_property(key, value)
            return
        except Exception:
            pass
    raise RuntimeError("Presentation property unavailable: " + name)


def vec(point):
    return point if isinstance(point, unreal.Vector) else unreal.Vector(*point)


def xyz(point):
    return [round(float(point.x), 3), round(float(point.y), 3), round(float(point.z), 3)]


def add(a, b):
    return unreal.Vector(a.x+b[0], a.y+b[1], a.z+b[2])


def look(start, target):
    x, y, z = target.x-start.x, target.y-start.y, target.z-start.z
    return unreal.Rotator(pitch=math.degrees(math.atan2(z, math.hypot(x, y))),
                          yaw=math.degrees(math.atan2(y, x)), roll=0)


def context():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.is_in_play_in_editor():
        raise RuntimeError("Prepare native Practice PIE with the capture helper first")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None or not re.fullmatch(r"/Basketbroom/Maps/UEDPIE_\d+_BB_Regulation\.BB_Regulation", world.get_path_name()):
        raise RuntimeError("Only disposable BB_Regulation PIE is supported")
    match = unreal.GameplayStatics.get_game_state(world)
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if not match or match.get_class().get_path_name() != MODULE+"BBMatchState" or not pawn or not controller:
        raise RuntimeError("Native match, pawn and controller must be loaded")
    if not unreal.GameplayStatics.get_game_mode(world):
        raise RuntimeError("The director needs a local authority PIE world")
    return world, match, pawn, controller


class Director:
    def __init__(self, args):
        self.args = dict(args)
        requested_duration = float(args.get("duration_seconds", 180))
        if not 5 <= requested_duration <= 180:
            raise ValueError("duration_seconds must be between 5 and 180")
        self.time_scale = .55 if args.get("rehearsal", False) else 1.0
        self.duration = requested_duration*self.time_scale
        self.full_take = requested_duration >= 180
        self.world, self.match, self.pawn, self.controller = context()
        if (not bool(prop(self.match, "bPractice")) or prop(self.match, "bLive")
                or str(prop(self.match, "Status")) != "LOBBY" or self.scores() != [0, 0]):
            raise RuntimeError("A fresh, unstarted 0-0 Practice lobby is required")
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(
            self.world, unreal.load_class(None, MODULE+"BBRiderCharacter")))
        self.balls = {int(prop(ball, "BallIndex")): ball for ball in unreal.GameplayStatics.get_all_actors_of_class(
            self.world, unreal.load_class(None, MODULE+"BBBall"))}
        if len(self.riders) != 16 or len(self.balls) != 7:
            raise RuntimeError("Expected sixteen native riders and seven balls")
        cameras = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.CameraActor))
        if not cameras:
            raise RuntimeError("The staged arena has no PIE presentation CameraActor")
        self.camera = next((a for a in cameras if a.get_actor_label() == "BB Hero Camera"), cameras[0])
        self.camera_component = self.camera.get_component_by_class(unreal.CameraComponent)
        self.hud = self.controller.get_hud()
        self.target = next(r for r in self.riders if int(prop(r, "TeamIndex")) != int(prop(self.pawn, "TeamIndex"))
                           and int(prop(r, "Position")) == 3)
        self.original = {"camera_location": self.camera.get_actor_location(),
                         "camera_rotation": self.camera.get_actor_rotation(),
                         "camera_fov": prop(self.camera_component, "FieldOfView"),
                         "hud": bool(prop(self.hud, "bShowHUD")),
                         "controller_tick": bool(self.controller.is_actor_tick_enabled())}
        self.tick_states = [(r, bool(r.is_actor_tick_enabled()), self.movement(r),
                             bool(self.movement(r).is_component_tick_enabled())) for r in self.riders]
        self.ball_ticks = [(b, bool(b.is_actor_tick_enabled())) for b in self.balls.values()]
        self.handle = None
        self.done = False
        self.phase = "prepared"
        self.origin = None
        self.wall_started = None
        self.sequence = None
        self.waiting = None
        self.last_time = None
        self.camera_update = None
        self.native_view = False
        self.last_publish = -1
        self.last_snitch_active = bool(prop(self.balls[4], "bActive"))
        self.data = {"status": "prepared", "duration_seconds": self.duration,
                     "rehearsal": bool(args.get("rehearsal", False)),
                     "requested_utc": datetime.now(timezone.utc).isoformat(),
                     "engine": unreal.SystemLibrary.get_engine_version(), "world": self.world.get_path_name(),
                     "capture_origin_game_seconds": None, "elapsed_seconds": 0, "events": [], "checks": [],
                     "shots": [{"start_seconds": a*self.time_scale, "end_seconds": min(b*self.time_scale, self.duration), "title": c,
                                "caption": d, "camera": e} for a, b, c, d, e in SHOTS if a*self.time_scale < self.duration],
                     "staging": ["Disposable Practice PIE with the genuine compiled native game and HUD.",
                                 "CPU movement is parked; native main-rider flight uses movement input.",
                                 "Scoring-ball trajectories and spell target transforms are arranged.",
                                 "The local selected-spell HUD slot is staged before ordinary native cast input; effects and hit receipts remain native.",
                                 "Force-shot targets temporarily have zero input acceleration so CPU steering cannot masquerade as a spell impulse.",
                                 "Final chase holds maintain physical proximity for the real 1-second capture rule.",
                                 "Scores, rule clocks, custody, effects, receipts and referee outcomes are never assigned.",
                                 "Cameras are cinematic presentation of the same running PIE world."],
                     "limitations": ["Prototype art and sporting spell adaptations, not final AAA assets.",
                                     "Not internet multiplayer, physical-controller certification or Hogwarts Legacy integration.",
                                     "Practice clocks compress release timing; regulation Snitch release is later.",
                                     "Audio, when added by the mixer, is an edit using original prototype cues."]}
        self.orbit_camera(0)
        self.publish()

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def elapsed(self):
        return max(0.0, self.now()-self.origin) if self.origin is not None else 0.0

    def scores(self):
        return [int(prop(self.match, "TealScore")), int(prop(self.match, "CopperScore"))]

    def movement(self, rider=None):
        return (rider or self.pawn).get_component_by_class(unreal.CharacterMovementComponent)

    def event(self, event, **detail):
        if event not in ("input_action", "physical_staging"):
            detail.setdefault("featured", True)
        self.data["events"].append({"time_seconds": round(self.elapsed(), 5), "event": event, **detail})

    def check(self, name, condition, **detail):
        self.data["checks"].append({"name": name, "passed": bool(condition), "time_seconds": round(self.elapsed(), 5), **detail})
        if not condition:
            raise RuntimeError("Showcase outcome did not occur: " + name)

    def publish(self):
        self.data.update(status=self.phase, elapsed_seconds=round(self.elapsed(), 5),
                         scores=self.scores(), live_seconds=round(float(prop(self.match, "LiveSeconds")), 4),
                         match_status=str(prop(self.match, "Status")))
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(self.data, indent=2, default=str)+"\n", encoding="utf-8")

    def move(self, location, rider=None):
        rider = rider or self.pawn
        self.movement(rider).stop_movement_immediately()
        rider.consume_movement_input_vector()
        rider.set_actor_location(vec(location), False, True)

    def park_cpus(self):
        # Keep teams visible along the sidelines, outside the chase ball's
        # 2300cm Y path plus its 380cm capture range. Match AI remains untouched.
        for rider in self.riders:
            if rider == self.pawn:
                continue
            slot = int(prop(rider, "RosterIndex"))
            self.movement(rider).set_component_tick_enabled(False)
            # Native rider Tick owns stun recovery and presentation. Only its
            # flight component is parked; MatchState still owns AI decisions.
            rider.set_actor_tick_enabled(True)
            self.move((-5400+(slot % 8)*1450, -2900 if slot < 8 else 2900, 1300+(slot % 3)*320), rider)
        self.event("physical_staging", detail="CPU marks at side perimeter; movement ticks suspended")

    def request(self, action, value=0):
        if action == 6:
            # This is the local loadout/HUD selection, not spell simulation.
            # The ordinary server action below still checks and applies casts.
            presentation_property(self.pawn, "SelectedSpell", int(value))
            self.event("cast_geometry", featured=False, spell_index=int(value),
                       caster_cm=xyz(self.pawn.get_actor_location()), caster_velocity=xyz(self.pawn.get_velocity()),
                       target_cm=xyz(self.target.get_actor_location()), target_velocity=xyz(self.target.get_velocity()),
                       native_aim=xyz(self.pawn.get_aim_direction()),
                       target_movement_enabled=bool(self.movement(self.target).is_component_tick_enabled()))
        if not self.pawn.development_request_action(action, value):
            raise RuntimeError("Guarded ordinary input was not queued")
        self.event("input_action", action=action, value=value)

    def interact(self, held):
        if not self.pawn.development_set_interaction(held):
            raise RuntimeError("Guarded hold input was not queued")
        self.event("input_action", action="hold_catch", value=bool(held))

    def seed(self, index, location, velocity=(0, 0, 0)):
        ball = self.balls[index]
        if prop(ball, "Holder") is not None or not prop(ball, "bActive"):
            raise RuntimeError("Physical launch requires a free active ball: " + str(index))
        if not ball.development_set_flight_fixture(vec(location), vec(velocity)):
            raise RuntimeError("PIE physical ball fixture rejected")
        ball.set_actor_tick_enabled(True)
        self.event("physical_staging", ball_index=index, location_cm=list(location), velocity_cm_s=list(velocity))
        return ball

    def view(self, native, hud=None):
        self.native_view = native
        self.controller.set_view_target_with_blend(self.pawn if native else self.camera, 0.0)
        presentation_property(self.hud, "bShowHUD", bool(native if hud is None else hud))
        if native:
            self.camera_update = None

    def camera_at(self, location, target, fov=66):
        self.camera.set_actor_location(vec(location), False, True)
        self.camera.set_actor_rotation(look(vec(location), vec(target)), True)
        self.camera_component.set_field_of_view(float(fov))
        if self.native_view:
            self.view(False)

    def orbit_camera(self, t):
        self.view(False)
        a = math.radians(-143+min(t, 12)*2.6)
        p = (math.cos(a)*9300, math.sin(a)*7100, 5700-90*min(t, 12))
        self.camera_at(p, (0, 0, 1550), 60)

    def tracking_camera(self, target=None, offset=(-1100, -620, 450), fov=68):
        point = (target or self.pawn).get_actor_location()
        self.camera_at(add(point, offset), add(point, (250, 0, 90)), fov)

    def fly_to(self, target):
        start = self.pawn.get_actor_location()
        target = vec(target)
        delta = vec((target.x-start.x, target.y-start.y, target.z-start.z))
        length = math.sqrt(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z)
        if length > 35:
            self.pawn.add_movement_input(vec((delta.x/length, delta.y/length, delta.z/length)), min(1., length/500), True)
            self.controller.set_control_rotation(look(add(start, (0, 0, 72)), target))

    def chase(self, index, secure=False):
        ball = self.balls[index]
        if not prop(ball, "bActive"):
            return
        point = ball.get_actor_location()
        if secure:
            self.move(add(point, (-210, 0, -25)))
            self.controller.set_control_rotation(look(add(self.pawn.get_actor_location(), (0, 0, 72)), point))
        else:
            self.fly_to(add(point, (-240, 0, -25)))

    def wait(self, seconds, predicate=None, update=None):
        return {"seconds": max(0, seconds), "predicate": predicate, "update": update}

    def at(self, seconds, update=None):
        return self.wait(max(0, seconds*self.time_scale-self.elapsed()), update=update)

    def ready_to_cast(self):
        return float(prop(self.pawn, "SpellCooldownRemaining")) <= 0 and float(prop(self.pawn, "StunRemaining")) <= 0

    def anchor_spell(self):
        self.view(True)
        self.movement().set_component_tick_enabled(False)
        self.movement(self.target).set_component_tick_enabled(False)
        self.movement().stop_movement_immediately()
        self.move((-1300, 0, 1850))
        self.move((-450, 0, 1922), self.target)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))

    def switch_role(self, role):
        self.movement().set_component_tick_enabled(True)
        self.interact(False)
        if prop(self.match, "bLive"):
            self.request(5)
            yield self.wait(2, lambda: not prop(self.match, "bLive"))
        self.check("official_stoppage_for_role_"+str(role), not prop(self.match, "bLive"))
        self.request(2, role)
        yield self.wait(2, lambda: int(prop(self.pawn, "Position")) == role)
        self.check("role_"+str(role)+"_accepted", int(prop(self.pawn, "Position")) == role)
        self.event("position_change", role=role)
        yield self.wait(.15)
        self.request(4)
        yield self.wait(2, lambda: bool(prop(self.match, "bLive")))
        self.check("role_"+str(role)+"_resume", bool(prop(self.match, "bLive")))
        self.event("resume")
        self.park_cpus()

    def observed_score(self, before, points, index, event="goal"):
        delta = [a-b for a, b in zip(self.scores(), before)]
        self.check(event+"_"+str(points), sum(delta) == points and max(delta) == points, delta=delta)
        self.event(event, ball_index=index, points=points, team=delta.index(points), score=self.scores())

    def scenarios(self):
        if int(prop(self.pawn, "Position")) != 3:
            self.request(2, 3)
            yield self.wait(2, lambda: int(prop(self.pawn, "Position")) == 3)
        yield self.at(1)
        self.request(4)
        yield self.wait(2, lambda: bool(prop(self.match, "bLive")))
        self.check("kickoff_live", bool(prop(self.match, "bLive")))
        self.event("kickoff")
        self.park_cpus()
        for index in (0, 1, 2, 5, 6):
            self.seed(index, (0, -700+index*210, 1700))
            self.balls[index].set_actor_tick_enabled(False)
        self.move((-5200, -1100, 1800))
        self.camera_update = lambda: self.orbit_camera(self.elapsed())
        yield self.at(12)
        self.camera_update = lambda: self.tracking_camera(offset=(-1050, -650, 450))
        yield self.at(19, lambda: self.fly_to((4500, -900, 2550)))
        self.view(True)
        yield self.at(26, lambda: self.fly_to((-1000, 1100, 3400)))
        self.camera_update = lambda: self.tracking_camera(offset=(800, -950, 330))
        yield self.at(28, lambda: self.fly_to((2000, 0, 2200)))

        # Actual pickup and normal 4400cm/s release into the large hoop.
        self.view(True)
        self.move((3300, -35, 2130))
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))
        yield self.at(32)
        self.seed(0, (3510, -35, 2130))
        # Frozen opening balls retain their real .25-second reset cooldown.
        # Let native Tick expire it before this one-shot possession request.
        yield self.wait(.35)
        self.interact(True)
        yield self.wait(2, lambda: prop(self.balls[0], "Holder") == self.pawn)
        self.check("quaffle_actual_pickup", prop(self.balls[0], "Holder") == self.pawn)
        self.event("quaffle_pickup", ball_index=0)
        self.interact(False)
        self.move((3800, -35, 2130))
        yield self.at(37)
        before = self.scores()
        self.request(1)
        yield self.wait(.3, lambda: prop(self.balls[0], "Holder") is None)
        self.check("quaffle_actual_release", prop(self.balls[0], "Holder") is None)
        self.event("throw", ball_index=0)
        yield self.wait(3, lambda: self.scores() != before)
        self.observed_score(before, 13, 0)
        yield self.at(43)
        self.camera_update = lambda: self.camera_at((4900, -2250, 2600), (6400, 0, 2103), 57)
        yield self.at(47)

        # A physically launched Quark arcs through the genuine small-hoop sweep.
        self.move((-3500, -2000, 1850))
        self.camera_update = lambda: self.camera_at((-4900, -1950, 3650), (-6300, 0, 3080), 64)
        yield self.at(51)
        before = self.scores()
        self.seed(1, (-4300, 0, 3620), (-1200, 0, 0))
        yield self.wait(4, lambda: self.scores() != before)
        self.observed_score(before, 37, 1)
        yield self.at(57)
        self.view(True)
        self.move((-4300, -1500, 2600))
        self.controller.set_control_rotation(unreal.Rotator(pitch=4, yaw=175, roll=0))
        yield self.at(63)

        self.camera_update = lambda: self.tracking_camera(self.balls[3], (-700, -420, 310), 58)
        self.move(add(self.balls[3].get_actor_location(), (-1200, -200, -80)))
        yield self.at(70, lambda: self.chase(3))
        self.view(True)
        yield self.at(73, lambda: self.chase(3, True))
        before = self.scores()
        self.interact(True)
        yield self.wait(3, lambda: not prop(self.balls[3], "bActive"), lambda: self.chase(3, True))
        self.observed_score(before, 69, 3, "snipe_catch")
        self.check("snipe_real_return_timer", 178 <= float(prop(self.balls[3], "ReturnIn")) <= 180,
                   return_seconds=float(prop(self.balls[3], "ReturnIn")))
        self.interact(False)
        yield self.at(80)

        yield from self.switch_role(4)
        self.move((-2000, -900, 1750))
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))
        yield self.at(84)
        self.seed(5, (-1780, -900, 1750))
        yield self.wait(.35)
        self.interact(True)
        yield self.wait(2, lambda: prop(self.balls[5], "Holder") == self.pawn)
        self.check("bludger_actual_pickup", prop(self.balls[5], "Holder") == self.pawn)
        self.event("bludger_pickup", ball_index=5)
        self.interact(False)
        yield self.wait(.2)
        self.request(1)
        yield self.wait(.3, lambda: prop(self.balls[5], "Holder") is None)
        self.check("bludger_actual_release", prop(self.balls[5], "Holder") is None)
        self.event("throw", ball_index=5)
        self.camera_update = lambda: self.tracking_camera(self.balls[5], (-950, -550, 350), 72)
        yield self.at(90)
        self.balls[5].set_actor_tick_enabled(False)
        self.view(True)
        yield self.at(95)

        self.anchor_spell()
        yield self.wait(.25)
        self.request(7)
        yield self.wait(.4, lambda: float(prop(self.pawn, "ShieldRemaining")) > 0)
        self.check("protego_native_effect", float(prop(self.pawn, "ShieldRemaining")) > 0)
        self.event("protego")
        yield self.at(99)
        yield self.wait(4, self.ready_to_cast)
        self.check("lumos_cast_ready", self.ready_to_cast())
        self.request(6, 19)
        yield self.wait(.4, lambda: float(prop(self.pawn, "LumosRemaining")) > 0)
        self.check("lumos_native_effect", float(prop(self.pawn, "LumosRemaining")) > 0)
        self.event("lumos")
        yield self.at(102)
        yield self.wait(4, self.ready_to_cast)
        self.check("basic_cast_ready", self.ready_to_cast())
        before_vitality = float(prop(self.target, "Vitality"))
        self.request(6, 0)
        yield self.wait(.6, lambda: float(prop(self.target, "Vitality")) < before_vitality-2)
        self.check("basic_cast_real_hit", float(prop(self.target, "Vitality")) < before_vitality-2)
        self.event("spell_hit", spell_index=0, spell_name="Basic Cast")
        yield self.at(109)

        for start, spell, name, axis, sign in ((109, 6, "Accio", "x", -1),
                                               (113, 7, "Depulso", "x", 1),
                                               (117, 12, "Levioso", "z", 1)):
            self.anchor_spell()
            yield self.wait(.25)
            yield self.wait(4, self.ready_to_cast)
            self.check(name+"_cast_ready", self.ready_to_cast())
            yield self.wait(1, lambda: self.pawn.get_aim_direction().x > .999)
            self.check(name+"_native_aim_aligned", self.pawn.get_aim_direction().x > .999,
                       aim=xyz(self.pawn.get_aim_direction()))
            movement = self.movement(self.target)
            # Resolve the genuine cast while both flight components remain
            # parked. Then let the already-applied native impulse move its
            # target; this avoids a CPU steering frame before hit detection.
            self.request(6, spell)
            yield self.wait(3, lambda: name+" HIT" in str(prop(self.pawn, "SpellFeedback")))
            hit_feedback = str(prop(self.pawn, "SpellFeedback"))
            self.check(name+"_actual_hit", name+" HIT" in hit_feedback,
                       feedback=hit_feedback, target_cm=xyz(self.target.get_actor_location()))
            before_location = self.target.get_actor_location()
            self.force_movement_original = (movement, float(prop(movement, "MaxAcceleration")))
            # Isolate the native spell impulse from MatchState's still-running
            # CPU steering. Zero input acceleration, never velocity or impulse.
            presentation_property(movement, "MaxAcceleration", 0.0)
            movement.set_component_tick_enabled(True)
            def actual_force_hit():
                return (name+" HIT" in hit_feedback
                        and (getattr(self.target.get_actor_location(), axis)-getattr(before_location, axis))*sign > 5)
            yield self.wait(.75, actual_force_hit)
            self.check(name+"_native_movement", actual_force_hit(),
                       feedback=hit_feedback, input_acceleration_during_fixture=0,
                       signed_displacement_cm=(getattr(self.target.get_actor_location(), axis)-getattr(before_location, axis))*sign)
            self.event("spell_hit", spell_index=spell, spell_name=name)
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
            self.restore_force_acceleration()
            yield self.at(start+4)

        # Do not manufacture the owner HUD receipt. It must draw and age .25s.
        self.anchor_spell()
        yield self.wait(5, lambda: self.ready_to_cast() and float(prop(self.target, "ImpedimentRemaining")) <= 0)
        yield self.wait(8, lambda: not str(prop(self.pawn, "SpellFeedback")))
        self.check("double_tap_ready", self.ready_to_cast() and not str(prop(self.pawn, "SpellFeedback")))
        before_fouls = int(prop(self.match, "ConductFoulCount"))
        self.request(6, 10)
        yield self.wait(.6, lambda: float(prop(self.target, "ImpedimentRemaining")) > 0)
        self.check("arresto_actual_impediment", float(prop(self.target, "ImpedimentRemaining")) > 0)
        self.event("spell_hit", spell_index=10, spell_name="Arresto Momentum")
        yield self.wait(2, lambda: self.ready_to_cast() and "target impeded" in str(prop(self.pawn, "SpellFeedback")))
        self.check("arresto_genuine_owner_feedback", self.ready_to_cast() and "target impeded" in str(prop(self.pawn, "SpellFeedback")))
        self.request(6, 2)
        yield self.wait(.7, lambda: bool(prop(self.match, "bConductReviewPending")))
        self.check("hit_applied_then_double_tap_review", bool(prop(self.match, "bConductReviewPending"))
                   and "DOUBLE-TAP" in str(prop(self.match, "LastConductCall"))
                   and int(prop(self.match, "ConductFoulCount")) == before_fouls+1
                   and float(prop(self.target, "StunRemaining")) > 0 and not prop(self.match, "bLive"),
                   target_stun_seconds=float(prop(self.target, "StunRemaining")), call=str(prop(self.match, "LastConductCall")))
        self.event("conduct_review", call=str(prop(self.match, "LastConductCall")), hit_applied=True)
        yield self.at(132)
        self.request(9)
        yield self.wait(1, lambda: not prop(self.match, "bConductReviewPending"))
        self.check("host_possession_award_queued", not prop(self.match, "bConductReviewPending")
                   and int(prop(self.match, "PendingPenaltyCount")) > 0)
        self.event("conduct_award")
        yield self.at(135)
        self.request(4)
        yield self.wait(3, lambda: bool(prop(self.match, "bLive")) and int(prop(self.match, "PendingPenaltyCount")) == 0)
        self.check("actual_possession_served", bool(prop(self.match, "bLive")) and int(prop(self.match, "PendingPenaltyCount")) == 0)
        self.event("resume")
        self.park_cpus()
        yield self.at(139)

        self.move((-1500, -1700, 3500))
        self.camera_update = lambda: self.camera_at((-1900, -1400, 4650), (0, 0, 4140), 59)
        ball = self.seed(2, (0, 0, 4040), (0, 0, 900))
        yield self.wait(2, lambda: not prop(ball, "bActive") and str(prop(ball, "BallStatus")) == "crown")
        self.check("no_crown_native_dead_ball", not prop(ball, "bActive") and str(prop(ball, "BallStatus")) == "crown")
        self.event("crown_exit", ball_index=2)
        yield self.wait(3, lambda: bool(prop(ball, "bActive")))
        self.check("no_crown_native_return", bool(prop(ball, "bActive")))
        self.event("crown_return", ball_index=2)
        self.balls[2].set_actor_tick_enabled(False)
        yield self.at(146)
        self.view(True)
        yield from self.switch_role(5)
        self.check("snitch_natural_release", bool(prop(self.balls[4], "bActive"))
                   and float(prop(self.match, "LiveSeconds")) >= 60)
        self.move(add(self.balls[4].get_actor_location(), (-1200, -200, -100)))
        yield self.at(151)

        self.camera_update = lambda: self.tracking_camera(self.balls[4], (-610, -410, 300), 57)
        yield self.at(158, lambda: self.chase(4))
        self.view(True)
        yield self.at(165, lambda: self.chase(4, True))
        before = self.scores()
        self.interact(True)
        yield self.wait(3, lambda: self.scores() != before, lambda: self.chase(4, True))
        self.observed_score(before, 150, 4, "snitch_catch")
        self.check("snitch_stops_match_for_result", not bool(prop(self.match, "bLive")))
        self.interact(False)
        yield self.wait(3, lambda: str(prop(self.match, "Status")) == "FINAL")
        winning_team = 0 if self.scores()[0] > self.scores()[1] else 1
        self.check("snitch_result_certified", str(prop(self.match, "Status")) == "FINAL"
                   and self.scores()[0] != self.scores()[1] and int(prop(self.match, "Winner")) == winning_team,
                   status=str(prop(self.match, "Status")), winner=int(prop(self.match, "Winner")), scores=self.scores())
        self.event("match_final", winner=winning_team, scores=self.scores())
        yield self.at(175)
        self.camera_update = lambda: self.camera_at((-7200, -6100, 4200+(self.elapsed()-175)*190), (0, 0, 1700), 63)
        yield self.at(180)

    def start(self):
        if self.phase != "prepared":
            raise RuntimeError("Director must be prepared exactly once before start")
        # In-memory only: never save the editor's user preference. Background
        # throttling can reduce PIE to 3 FPS and skip an entire catch radius.
        self.performance_settings = unreal.get_default_object(
            unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
        self.performance_original = bool(prop(self.performance_settings, "bThrottleCPUWhenNotForeground"))
        presentation_property(self.performance_settings, "bThrottleCPUWhenNotForeground", False)
        self.data["editor_background_throttle"] = {"before": self.performance_original, "during": False, "restored": False}
        self.controller.set_actor_tick_enabled(False)
        self.orbit_camera(0)
        capture = getattr(unreal, "_basketbroom_gameplay_demo_capture", None)
        if self.args.get("capture_sync", True):
            if capture is None or not callable(getattr(capture, "start_capture", None)):
                raise RuntimeError("Capture helper must expose start_capture() before synchronized start")
            capture_result = capture.start_capture()
            self.data["capture"] = {key: capture.data.get(key) for key in ("output", "frames", "fps", "resolution")}
        else:
            capture_result = None
        self.origin = (float(capture_result) if isinstance(capture_result, (int, float)) else self.now())
        self.data["capture_origin_game_seconds"] = self.origin
        self.wall_started = time.monotonic()
        self.phase = "running"
        self.sequence = self.scenarios()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.advance()
        self.publish()

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            self.waiting.update(start=self.now(), frames=0)
        except StopIteration:
            self.finish("complete")

    def tick(self, delta):
        if self.done:
            return
        try:
            world, match, pawn, _ = context()
            if world != self.world or match != self.match or pawn != self.pawn:
                raise RuntimeError("The owned capture world changed")
            now = self.now()
            if self.last_time is not None and now <= self.last_time:
                return
            self.last_time = now
            active = bool(prop(self.balls[4], "bActive"))
            if active and not self.last_snitch_active:
                self.event("snitch_release", ball_index=4, live_seconds=float(prop(self.match, "LiveSeconds")))
            self.last_snitch_active = active
            if self.elapsed() >= self.duration:
                # LevelCapture startup/finalization can omit its first couple
                # of frames. Record a short real tail, then let the assembler
                # trim to precisely 5400 frames for the 180-second master.
                if self.full_take and self.args.get("capture_sync", True) and self.elapsed() < self.duration+.3:
                    if self.camera_update:
                        self.camera_update()
                    return
                self.finish("complete" if not self.full_take or any(e["event"] == "match_final" for e in self.data["events"]) else "failed")
                return
            if self.camera_update:
                self.camera_update()
            waiting = self.waiting
            if waiting:
                if waiting["update"]:
                    waiting["update"]()
                waiting["frames"] += 1
                age = now-waiting["start"]
                if waiting["frames"] >= 1 and age >= .1 and (age >= waiting["seconds"]
                        or waiting["predicate"] is not None and waiting["predicate"]()):
                    self.advance()
            if int(self.elapsed()) != self.last_publish:
                self.last_publish = int(self.elapsed())
                self.publish()
        except Exception:
            self.data["error"] = traceback.format_exc()
            unreal.log_error(self.data["error"])
            self.finish("failed")

    def finish(self, status="stopped"):
        if self.done:
            return
        self.done = True
        self.phase = status
        if self.handle:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.data["completed_utc"] = datetime.now(timezone.utc).isoformat()
        self.data["captured_seconds"] = round(self.elapsed(), 5)
        self.data["wall_seconds"] = round(time.monotonic()-self.wall_started, 3) if self.wall_started else 0
        self.restore_force_acceleration()
        self.restore_performance()
        self.publish()
        # Stopping LevelCapture ends PIE, so collect all evidence first.
        # Presentation cleanup must never appear inside the recorded frames.
        capture = getattr(unreal, "_basketbroom_gameplay_demo_capture", None)
        if self.args.get("capture_sync", True) and capture is not None and callable(getattr(capture, "stop_capture", None)):
            capture.stop_capture()
        # The capture helper owns this disposable PIE session. Keep its final
        # frame intact until it stops PIE; stop explicitly restores live inputs.
        if status == "stopped" or not self.args.get("capture_sync", True):
            self.restore()

    def restore_performance(self):
        if hasattr(self, "performance_settings") and hasattr(self, "performance_original"):
            presentation_property(self.performance_settings, "bThrottleCPUWhenNotForeground", self.performance_original)
            self.data.setdefault("editor_background_throttle", {})["restored"] = True

    def restore_force_acceleration(self):
        if getattr(self, "force_movement_original", None):
            movement, acceleration = self.force_movement_original
            presentation_property(movement, "MaxAcceleration", acceleration)
            self.force_movement_original = None

    def restore(self):
        try:
            context()
            self.pawn.development_set_interaction(False)
            self.controller.set_actor_tick_enabled(self.original["controller_tick"])
            self.view(True, self.original["hud"])
            self.camera.set_actor_location(self.original["camera_location"], False, True)
            self.camera.set_actor_rotation(self.original["camera_rotation"], True)
            self.camera_component.set_field_of_view(self.original["camera_fov"])
            for rider, actor_enabled, movement, movement_enabled in self.tick_states:
                rider.set_actor_tick_enabled(actor_enabled)
                movement.set_component_tick_enabled(movement_enabled)
            for ball, enabled in self.ball_ticks:
                ball.set_actor_tick_enabled(enabled)
        except Exception as exc:
            self.data["cleanup_note"] = str(exc)


def main():
    operation = ARGS.get("operation", "inspect")
    previous = getattr(unreal, RUNNER, None)
    if operation == "prepare":
        if previous is not None and not previous.done:
            raise RuntimeError("A director is already prepared/running; stop it first")
        previous = Director(ARGS)
        setattr(unreal, RUNNER, previous)
    elif operation == "start":
        if previous is None:
            raise RuntimeError("Prepare the director first")
        # A bridge edit can arrive between preparation and the first frame.
        # Adopt only the current implementation before a prepared run starts.
        if previous.phase == "prepared":
            previous.__class__ = Director
        try:
            previous.start()
        except Exception:
            previous.restore_performance()
            previous.restore()
            raise
    elif operation == "stop":
        if previous is not None:
            if not previous.done:
                previous.finish("stopped")
            else:
                previous.restore()
    elif operation != "inspect":
        raise ValueError("operation must be prepare/start/inspect/stop")
    return {"status": previous.phase if previous else "absent", "report": str(REPORT),
            "elapsed_seconds": round(previous.elapsed(), 5) if previous else None,
            "duration_seconds": previous.duration if previous else None}


RESULT = main()
