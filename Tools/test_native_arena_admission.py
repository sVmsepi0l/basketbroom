"""Live expanded-arena admission checks using existing native PIE input APIs.

Run through editor_bridge.py on the clean, staged BB_Regulation map with
BRIDGE_ARGS={"variant": "regulation"}; repeat with variant="bloodbroom".
Outside Unreal, no arguments/--list/--help describe coverage without opening an
editor or writing a result. No new C++ hooks or gameplay-state injection.

A chase ball always clamps itself before private StepCapture. Consequently the
suite verifies chase recovery from an outside sphere; sphere-admission rejection
is isolated through ordinary scoring-ball pickup, using the same CanInteract
gate with free-ball tick paused. It never claims to observe a rejected chase
sphere that native Tick has already brought inside.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 150, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
REPORT = ROOT / ".local" / ("native-arena-admission-%s-results.json" % VARIANT)
CASES = (
    "native_variant_and_eligible_ranger_are_live",
    "ordinary_quark_pickup_succeeds_in_expanded_side_strip",
    "protruding_scoring_sphere_cannot_be_picked_up_below_apex",
    "same_scoring_sphere_becomes_pickable_when_wholly_inside",
    "protruding_rider_capsule_cannot_start_chase_capture_below_apex",
    "outside_chase_sphere_recovers_inside_before_capture",
    "continuous_snipe_capture_in_expanded_side_strip_awards_69",
    "admission_fixtures_preserve_live_clock_and_conduct_state",
    "owned_pie_ends_with_original_clean_editor_map",
)


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


dimensions = module("_bb_admission_dimensions", "Tools/arena_dimensions.py")
base = module("_bb_arena_admission_base", "Tools/test_native_playable.py")
receipts = module("_bb_arena_admission_receipts", "Tools/native_test_receipts.py")
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
unreal, prop, vector = base.unreal, base.prop, base.vector
HX, HY = dimensions.HALF_LENGTH, dimensions.HALF_WIDTH
EAVE, APEX = dimensions.EAVE_HEIGHT, dimensions.APEX_HEIGHT
SX, SY = (APEX - EAVE) / HX, (APEX - EAVE) / HY


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def distance(first, second):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def clearance(point, radius, half_height=None):
    # Independent support-plane distances, not the production C++ predicate.
    half_height = radius if half_height is None else half_height
    return min(HX - abs(point[0]) - radius, HY - abs(point[1]) - radius,
               point[2] - half_height,
               min((APEX - slope * abs(point[axis]) - point[2]) / math.sqrt(1 + slope * slope)
                   - radius - (half_height - radius) / math.sqrt(1 + slope * slope)
                   for axis, slope in ((0, SX), (1, SY))))


class ArenaAdmissionTests(base.NativePlayableTests):
    def __init__(self):
        self.original_map = None
        self.cleanup_status = "not_run"
        self.cleanup_reason = None
        self.cleanup_started = None
        self.cleanup_verified = False
        self.old_dilation = None
        self.dilation_restored = True
        self.original_movement_tick = None
        self.movement = None
        super().__init__()

    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                                              unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(variant=VARIANT,
                    scope="real queued native input and authoritative admission in one disposable UE5.8 PIE world",
                    fixture_policy="Only actor positions, guarded free-ball trajectories, actor/component tick isolation, "
                                   "and temporary world dilation are arranged; custody, capture progress, activation, "
                                   "scores, timers, rules, collision and outcomes are never assigned.",
                    geometry_cm=dict(half_x=HX, half_y=HY, eave=EAVE, apex=APEX),
                    cleanup=dict(editor_map=self.original_map, clean_map_verified=self.cleanup_verified,
                                 time_dilation_restored=self.dilation_restored),
                    not_covered=["network admission/latency or physical controller operation",
                                 "normal-speed piloting/capture difficulty",
                                 "rejection of an outside chase sphere: native Tick clamps before StepCapture; "
                                 "the shared sphere gate is tested by scoring-ball pickup instead",
                                 "Hogwarts Legacy native character integration"])
        receipts.write_json_atomic(REPORT, data)

    def dirty(self):
        saving = unreal.EditorLoadingAndSavingUtils
        return sorted(package.get_path_name() for package in
                      list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages()))

    def editor_map(self):
        world = self.editor.get_editor_world()
        return world.get_path_name().split(".")[0] if world else None

    def begin(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant")
        self.require(not self.level.is_in_play_in_editor(), "An existing PIE session must not be adopted")
        self.original_map = self.editor_map()
        self.require(self.original_map == "/Basketbroom/Maps/BB_Regulation", "Open the staged BB_Regulation map first")
        self.require(not self.dirty(), "Editor map/content must be clean before the test")
        self.provenance.update(original_editor_map=self.original_map, editor_assets_saved=False)
        return super().begin()

    def assert_case(self, name, condition, **detail):
        self.record(name, bool(condition), **detail)
        self.require(condition, name)

    def free_fixture(self, index, location, ticking=False):
        ball = self.seed_ball(index, location)
        ball.set_actor_tick_enabled(ticking)
        return ball

    def settle_free_ball(self, index):
        # ResetOpeningLayout/ordinary release impose real native pickup
        # cooldowns. Let an isolated, stationary interior ball Tick those down
        # before pausing its Tick to isolate the admission geometry.
        ball = self.seed_ball(index, (0, 0, 1000))
        before, started = self.scores(), self.now()
        yield self.wait(.35, minimum_frames=2)
        self.require(self.now() - started >= .35 and prop(ball, "Holder") is None
                     and prop(ball, "bActive") and self.scores() == before,
                     "A genuinely free ball must Tick its cooldown before a static admission fixture")
        ball.set_actor_tick_enabled(False)
        self.event("native_cooldown_settled", ball=index, elapsed_game_seconds=self.now() - started,
                   position=xyz(ball.get_actor_location()), ticks_paused_after_wait=True)
        return ball

    def input_off(self):
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)
        self.require(not prop(self.pawn, "bInteractHeld"), "Interaction release must execute")

    def pickup(self, ball, timeout=1):
        self.interact(True)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn, timeout=timeout)

    def release_and_park(self, ball):
        yield from self.input_off()
        self.request(1)
        yield self.wait_until(lambda: prop(ball, "Holder") is None, timeout=1)
        self.require(prop(ball, "Holder") is None, "Actual throw must release fixture custody")
        yield from self.settle_free_ball(int(prop(ball, "BallIndex")))

    def snapshot(self, ball):
        rider, point = xyz(self.pawn.get_actor_location()), xyz(ball.get_actor_location())
        return dict(seconds=self.now(), rider=rider, ball=point,
                    rider_clearance_cm=clearance(rider, self.radius, self.half_height),
                    ball_clearance_cm=clearance(point, float(ball.get_collision_radius())),
                    distance_cm=distance(rider, point), interaction=bool(prop(self.pawn, "bInteractHeld")),
                    capture_progress=float(prop(ball, "CaptureProgress")),
                    capturing_rider=prop(ball, "CapturingRider") == self.pawn,
                    active=bool(prop(ball, "bActive")), scores=self.scores())

    def chase_fixture(self, ball, rider_point, ball_point, rows):
        # Observe completed native ticks before arranging the next free-ball
        # transform. No score/progress or clock is manufactured by this callback.
        now = self.now()
        if not rows or now > rows[-1]["seconds"]:
            rows.append(self.snapshot(ball))
        if prop(ball, "bActive"):
            self.move_pawn(rider_point)
            self.require(ball.development_set_flight_fixture(vector(ball_point), vector((0, 0, 0))),
                         "Only an active, free chase-ball physical fixture is allowed")

    def scenarios(self):
        wanted = VARIANT == "bloodbroom"
        if bool(prop(self.match, "bBloodbroom")) != wanted:
            self.request(8)
            yield self.wait_until(lambda: bool(prop(self.match, "bBloodbroom")) == wanted)
            self.require(bool(prop(self.match, "bBloodbroom")) == wanted, "Native variant input must execute")
            yield self.wait(.09)
        # A redundant role predicate could pass before its queued action drains,
        # causing Start to share that Tick and be rejected by the native limit.
        if int(prop(self.pawn, "Position")) != 3:
            self.request(2, 3)
            yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 3)
            self.require(int(prop(self.pawn, "Position")) == 3, "Native Ranger selection must execute")
            yield self.wait(.09)
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")))
        self.require(bool(prop(self.match, "bLive")), "Actual native Start must succeed before admission fixtures")
        self.isolate()
        self.movement = self.component(self.pawn, unreal.CharacterMovementComponent)
        self.original_movement_tick = self.movement.is_component_tick_enabled()
        self.movement.stop_movement_immediately()
        self.movement.set_component_tick_enabled(False)
        capsule = self.component(self.pawn, unreal.CapsuleComponent)
        self.radius = float(capsule.get_scaled_capsule_radius())
        self.half_height = float(capsule.get_scaled_capsule_half_height())
        self.initial_scores = self.scores()
        self.initial_live = float(prop(self.match, "LiveSeconds"))
        self.initial_conduct = [int(prop(self.match, "ConductFoulCount")), int(prop(self.match, "PendingPenaltyCount"))]
        self.assert_case(CASES[0], bool(prop(self.match, "bBloodbroom")) == wanted
                         and int(prop(self.pawn, "Position")) == 3 and prop(self.match, "bLive")
                         and prop(self.balls[3], "bActive"), variant=VARIANT, roster=self.roster())

        strip_y = (dimensions.BASELINE_HALF_WIDTH + HY) / 2
        strip_rider = (-160, strip_y, 1800)
        strip_ball = (20, strip_y, 1800)
        self.require(strip_y - max(self.radius, 65) > dimensions.BASELINE_HALF_WIDTH,
                     "Entire interaction fixture must occupy newly added side space")
        self.move_pawn(strip_rider)
        yield from self.settle_free_ball(1)
        quark = self.free_fixture(1, strip_ball)
        yield from self.pickup(quark)
        self.assert_case(CASES[1], prop(quark, "Holder") == self.pawn and self.scores() == self.initial_scores,
                         old_side_plane_cm=dimensions.BASELINE_HALF_WIDTH, sample=self.snapshot(quark))
        yield from self.release_and_park(quark)

        roof_y = HY * .62
        roof_z = APEX - SY * roof_y
        # Both actor centres and their connecting line lie inside the convex
        # venue. Only the ball's finite radius protrudes through the roof.
        invalid_ball = (0, roof_y, roof_z - 15)
        valid_rider = (-180, roof_y, roof_z - 250)
        self.move_pawn(valid_rider)
        self.free_fixture(1, invalid_ball)
        self.require(clearance(valid_rider, self.radius, self.half_height) > 50
                     and clearance(invalid_ball, 65) < -40 and invalid_ball[2] < APEX,
                     "Roof sphere fixture must isolate shape protrusion below the apex")
        self.interact(True)
        rows = []
        yield self.wait(.45, lambda: rows.append(self.snapshot(quark)), minimum_frames=2)
        self.assert_case(CASES[2], bool(prop(self.pawn, "bInteractHeld")) and prop(quark, "Holder") is None
                         and self.scores() == self.initial_scores
                         and all(row["distance_cm"] < 425 and row["rider_clearance_cm"] > 0
                                 and row["ball_clearance_cm"] < -40 for row in rows), samples=rows)
        yield from self.input_off()
        valid_ball = (0, roof_y, roof_z - 180)
        self.free_fixture(1, valid_ball)
        yield from self.pickup(quark)
        self.assert_case(CASES[3], prop(quark, "Holder") == self.pawn and self.scores() == self.initial_scores,
                         sample=self.snapshot(quark), change="only the free sphere was lowered inside")
        yield from self.release_and_park(quark)

        self.old_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.dilation_restored = False
        unreal.GameplayStatics.set_global_time_dilation(self.world, .1)
        snipe = self.balls[3]
        roof_y = HY * .5
        roof_z = APEX - SY * roof_y
        capsule_support = self.radius * math.sqrt(1 + SY * SY) + self.half_height - self.radius
        invalid_rider = (0, roof_y, roof_z - capsule_support + 25)
        chase_inside = (0, roof_y, invalid_rider[2] - 130)
        self.require(clearance(invalid_rider, self.radius, self.half_height) < -15
                     and invalid_rider[2] < roof_z < APEX and clearance(chase_inside, 28) > 50,
                     "Capsule fixture must protrude while its centre and chase sphere remain inside")
        self.move_pawn(invalid_rider)
        self.free_fixture(3, chase_inside, ticking=True)
        self.interact(True)
        rows = []
        fixture = lambda: self.chase_fixture(snipe, invalid_rider, chase_inside, rows)
        yield self.wait(1.25, fixture, minimum_frames=3)
        held_rows = [row for row in rows if row["interaction"]]
        self.assert_case(CASES[4], len(held_rows) >= 3 and self.scores() == self.initial_scores
                         and all(row["rider_clearance_cm"] < -15 and row["ball_clearance_cm"] >= -.1
                                 and row["distance_cm"] < 380 and row["capture_progress"] == 0
                                 and not row["capturing_rider"] for row in held_rows), samples=rows,
                         capsule_radius_cm=self.radius, capsule_half_height_cm=self.half_height)
        yield from self.input_off()

        # No ordinary API can make StepCapture observe this outside sphere:
        # native chase Tick repairs its position before attempting admission.
        self.move_pawn((0, 0, 1000))
        outside_chase = (0, roof_y, roof_z - 5)
        self.free_fixture(3, outside_chase, ticking=True)
        self.require(clearance(outside_chase, 28) < -20, "Chase recovery fixture must begin outside")
        rows = []
        recovery_started = self.now()
        def recovery_sample():
            # Slate can tick twice without advancing the game. Exclude the
            # deliberately invalid pre-native-tick seed from recovery evidence.
            if self.now() > (rows[-1]["seconds"] if rows else recovery_started):
                rows.append(self.snapshot(snipe))
        yield self.wait(.15, recovery_sample, minimum_frames=2)
        self.assert_case(CASES[5], len(rows) >= 2 and self.scores() == self.initial_scores
                         and all(row["ball_clearance_cm"] >= -.1 and row["capture_progress"] == 0
                                 and not row["capturing_rider"] and row["active"] for row in rows),
                         outside_sphere=outside_chase, samples=rows,
                         observation="native chase containment, not an outside-sphere rejection claim")
        snipe.set_actor_tick_enabled(False)

        self.move_pawn(strip_rider)
        self.free_fixture(3, strip_ball, ticking=True)
        rows = []
        fixture = lambda: self.chase_fixture(snipe, strip_rider, strip_ball, rows)
        self.interact(True)
        yield self.wait_until(lambda: self.scores() != self.initial_scores, fixture, timeout=2)
        expected = [0, 0]
        expected[int(prop(self.pawn, "TeamIndex"))] = 69
        positive = [row for row in rows if row["capture_progress"] > 0]
        self.assert_case(CASES[6], self.score_delta(self.initial_scores) == expected and positive
                         and not prop(snipe, "bActive") and str(prop(snipe, "BallStatus")) == "timeout"
                         and all(row["rider"][1] - self.radius > dimensions.BASELINE_HALF_WIDTH
                                 and row["ball"][1] - 28 > dimensions.BASELINE_HALF_WIDTH
                                 and row["rider_clearance_cm"] >= -.1 and row["ball_clearance_cm"] >= -.1
                                 for row in positive), samples=rows, awarded=self.score_delta(self.initial_scores),
                         expected=expected, return_seconds=float(prop(snipe, "ReturnIn")))
        yield from self.input_off()
        self.assert_case(CASES[7], prop(self.match, "bLive") and float(prop(self.match, "LiveSeconds")) > self.initial_live
                         and [int(prop(self.match, "ConductFoulCount")), int(prop(self.match, "PendingPenaltyCount"))]
                         == self.initial_conduct, live_seconds=float(prop(self.match, "LiveSeconds")),
                         conduct_before=self.initial_conduct, scores=self.scores())

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            now = self.now()
            self.waiting.update(last_game_seconds=now, game_frames=0, until=now + self.waiting["seconds"],
                                wall_started=time.monotonic())
        except StopIteration:
            complete = len(self.results) == len(CASES) - 1 and all(row["status"] == "passed" for row in self.results.values())
            self.finish("passed" if complete else "failed")

    def finish(self, status, reason=None):
        if self.phase == "ending_owned_pie":
            return
        self.cleanup_status, self.cleanup_reason = status, reason
        self.final_status = status
        self.cleanup_started = time.monotonic()
        self.phase = "ending_owned_pie"
        try:
            if self.owns_play and self.world:
                if self.old_dilation is not None:
                    unreal.GameplayStatics.set_global_time_dilation(self.world, self.old_dilation)
                    self.dilation_restored = abs(float(unreal.GameplayStatics.get_global_time_dilation(self.world)) - self.old_dilation) < .0001
                if self.pawn:
                    self.pawn.development_set_interaction(False)
                if self.movement is not None and self.original_movement_tick is not None:
                    self.movement.set_component_tick_enabled(self.original_movement_tick)
            if self.owns_play and self.level.is_in_play_in_editor():
                self.level.editor_request_end_play()
            if self.handle is None:
                self.handle = unreal.register_slate_post_tick_callback(self.tick)
            self.write_report("running", reason)
        except Exception:
            self.complete_cleanup(False, (reason or "") + "\nCleanup request: " + traceback.format_exc())

    def complete_cleanup(self, clean, reason=None):
        self.cleanup_verified = bool(clean and self.owns_play)
        if self.owns_play and CASES[-1] not in self.results:
            self.record(CASES[-1], clean, original_map=self.original_map, map_now=self.editor_map(),
                        pie_active=self.level.is_in_play_in_editor(), dirty=self.dirty(),
                        time_dilation_restored=self.dilation_restored)
        status = self.cleanup_status if clean else "error"
        if status == "passed" and (len(self.results) != len(CASES) or
                                    any(row["status"] != "passed" for row in self.results.values())):
            status = "failed"
        self.done, self.final_status, self.phase = True, status, "complete"
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.write_report(status, reason or self.cleanup_reason)

    def tick(self, delta):
        if self.done:
            return
        if self.phase != "ending_owned_pie":
            return super().tick(delta)
        try:
            if self.owns_play and self.level.is_in_play_in_editor():
                self.require(time.monotonic() - self.cleanup_started < 20, "Owned PIE did not end within 20 seconds")
                return
            clean = (not self.owns_play or not self.level.is_in_play_in_editor()) and self.dilation_restored
            if self.original_map is not None:
                clean = clean and self.editor_map() == self.original_map and not self.dirty()
            self.complete_cleanup(clean)
        except Exception:
            self.complete_cleanup(False, (self.cleanup_reason or "") + "\nCleanup: " + traceback.format_exc())


def main():
    if unreal is None:
        return dict(status="not_run", variants=["regulation", "bloodbroom"], planned_cases=list(CASES),
                    count_per_variant=len(CASES), requires="clean staged UE5.8 BB_Regulation and compiled BasketbroomRuntime",
                    outside_chase_sphere="native recovery tested; shared sphere rejection isolated using scoring-ball pickup")
    runner = ArenaAdmissionTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if started or runner.owns_play:
        unreal._basketbroom_native_test = runner
    return dict(status="started" if started else runner.final_status, report=str(REPORT), planned_cases=len(CASES), variant=VARIANT)


if __name__ == "__main__":
    if unreal is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--list", action="store_true", help="print planned coverage; this never runs an editor")
        parser.parse_args()
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
