"""Physical closed-pyramid containment in one owned native PIE world per variant.

BRIDGE_ARGS={"variant":"regulation", "capture_screenshots":True}; repeat with
variant="bloodbroom". Uses real live Practice clocks for the scheduled Snitch,
ordinary pickup/throw inputs, native movement and guarded free-ball trajectories.
Never writes score, custody, activation, clocks, collision receipts or outcomes.
The explicit physical fixtures isolate geometric behavior, not human flight skill.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 220, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
REPORT = ROOT / ".local" / ("native-pyramid-net-%s-results.json" % VARIANT)
CASES = (
    "host_variant_and_practice_clock_are_native",
    "old_crown_plane_is_hollow_and_free_ball_keeps_live_flight",
    "positive_x_face_returns_quaffle", "negative_x_face_returns_quark_one",
    "positive_y_face_returns_quark_two", "negative_y_face_returns_bludger",
    "northeast_ridge_has_no_gap", "northwest_ridge_has_no_gap",
    "southwest_ridge_has_no_gap", "southeast_ridge_has_no_gap",
    "apex_has_no_gap", "high_speed_large_frame_cannot_tunnel_out",
    "all_four_face_normals_preserve_tangents_and_restitute_point_75",
    "actual_ranger_pickup_establishes_custody",
    "carried_ball_passes_old_plane_without_forced_drop",
    "held_sphere_and_rider_capsule_fit_under_pyramid",
    "all_four_faces_confine_actual_rider_movement",
    "roof_contacts_never_create_no_crown_calls_or_stop_live_clock",
    "snitch_activates_through_real_sixty_second_practice_release",
    "snipe_chase_is_confined_under_roof", "snitch_chase_is_confined_under_roof",
    "ordinary_quaffle_goal_still_scores_thirteen",
    "ordinary_quark_goal_still_scores_thirty_seven",
)
_spec = importlib.util.spec_from_file_location("_bb_pyramid_base", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector
_spec = importlib.util.spec_from_file_location("_bb_pyramid_receipts", ROOT / "Tools/native_test_receipts.py")
receipts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(receipts)

HALF_X, HALF_Y, EAVE, APEX = 6850.8, 3200.4, 4206.24, 6309.36
SLOPE_X, SLOPE_Y = (APEX-EAVE)/HALF_X, (APEX-EAVE)/HALF_Y
PLANES = ((SLOPE_X, 0, 1), (-SLOPE_X, 0, 1), (0, SLOPE_Y, 1), (0, -SLOPE_Y, 1))


def dot(a, b):
    return sum(float(x)*float(y) for x, y in zip(a, b))


def unit(a):
    length = math.sqrt(dot(a, a))
    return [x/length for x in a]


def roof_clearance(point, radius, half_height=None):
    """Independent analytic support, not a call into the implementation helper."""
    vertical = 0 if half_height is None else half_height-radius
    return min((APEX-dot(n, point))/math.sqrt(dot(n, n))-radius
               -vertical/math.sqrt(dot(n, n)) for n in PLANES)


def sphere_inside(point, radius, tolerance=1):
    return (roof_clearance(point, radius) >= -tolerance and abs(point[0])+radius <= HALF_X+tolerance
            and abs(point[1])+radius <= HALF_Y+tolerance and point[2]-radius >= -tolerance)


class PyramidNetTests(base.NativePlayableTests):
    def __init__(self):
        self.url_owner = self.url_key = self.old_url = None
        self.url_restored = True
        self.old_dilation = None
        self.dilation_restored = True
        self.old_max_fps = None
        self.fps_restored = True
        self.screenshots = []
        self.frame_samples = []
        super().__init__()

    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                                              unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope="native physics and ordinary inputs in one disposable authority Practice PIE world",
                    variant=VARIANT,
                    fixture_policy="Only free-ball transforms/velocity, rider transforms, movement input, CPU tick isolation, "
                                   "temporary world dilation, frame cap and Practice URL are arranged. No gameplay state is injected.",
                    geometry_cm=dict(half_x=HALF_X, half_y=HALF_Y, eave=EAVE, apex=APEX),
                    cleanup=dict(editor_url_restored=self.url_restored, time_dilation_restored=self.dilation_restored,
                                 frame_cap_restored=self.fps_restored),
                    screenshots=[{**item, "file_written": Path(item["path"]).is_file(),
                                  "bytes": Path(item["path"]).stat().st_size if Path(item["path"]).is_file() else 0}
                                 for item in self.screenshots],
                    not_covered=["network replication (separate suite)", "physical controller inputs, comfort or visual approval",
                                 "full-length regulation clock duration", "automatic foul severity or Hogwarts integration"])
        receipts.write_json_atomic(REPORT, data)

    def begin(self):
        if unreal is None:
            return super().begin()
        self.require(not self.level.is_in_play_in_editor(), "Suite must own a fresh PIE session")
        # This public editable live EditorEngine option is the established
        # in-process Practice route. Restore the exact original value on exit.
        cls = unreal.load_class(None, "/Script/UnrealEd.EditorEngine")
        engines = [obj for obj in unreal.ObjectIterator(cls)
                   if obj.get_path_name().startswith("/Engine/Transient.") and not obj.get_name().startswith("Default__")]
        self.require(len(engines) == 1, "Expected one live EditorEngine")
        self.url_owner = engines[0]
        for key in ("InEditorGameURLOptions", "in_editor_game_url_options"):
            try:
                self.old_url = self.url_owner.get_editor_property(key)
                self.url_key = key
                break
            except Exception:
                pass
        self.require(self.url_key is not None, "Editable in-process game URL unavailable")
        self.url_restored = False
        requested = str(self.old_url)+"?Practice=1"
        self.url_owner.set_editor_property(self.url_key, requested)
        self.provenance.update(original_editor_url=self.old_url, requested_editor_url=requested)
        return super().begin()

    def finish(self, status, reason=None):
        try:
            if self.url_owner and self.url_key and not self.url_restored:
                self.url_owner.set_editor_property(self.url_key, self.old_url)
                self.url_restored = self.url_owner.get_editor_property(self.url_key) == self.old_url
                self.require(self.url_restored, "Could not restore editor URL")
            if self.world and self.old_dilation is not None:
                unreal.GameplayStatics.set_global_time_dilation(self.world, self.old_dilation)
                self.dilation_restored = abs(float(unreal.GameplayStatics.get_global_time_dilation(self.world))-self.old_dilation) < .0001
            if self.world and self.old_max_fps is not None:
                unreal.SystemLibrary.execute_console_command(self.world, "t.MaxFPS %.6f" % self.old_max_fps)
                self.fps_restored = abs(float(unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS"))-self.old_max_fps) < .001
            self.require(self.url_restored and self.dilation_restored and self.fps_restored, "Temporary test settings must restore")
        except Exception:
            status, reason = "error", (reason or "")+"\nCleanup: "+traceback.format_exc()
        super().finish(status, reason)

    def contact(self, ball):
        values = [float(value) for value in ball.development_get_roof_contact_state()]
        self.require(len(values) == 10, "Read-only roof contact diagnostic must have ten fields")
        return dict(count=int(values[0]), normal=values[1:4], incoming=values[4:7], outgoing=values[7:10])

    def sample(self, ball, rows):
        rows.append(dict(seconds=self.now(), position=xyz(ball.get_actor_location()), velocity=xyz(ball.get_flight_velocity()),
                         active=bool(prop(ball, "bActive")), status=str(prop(ball, "BallStatus")),
                         holder=prop(ball, "Holder") is not None, contact=self.contact(ball)))
        self.frame_samples.append(self.now())

    def capture(self, label):
        if not ARGS.get("capture_screenshots", False):
            return
        if not hasattr(self, "capture_dir"):
            self.capture_dir = ROOT / ".local/pyramid-net-ui" / (VARIANT+"-"+uuid.uuid4().hex[:12])
            self.capture_dir.mkdir(parents=True, exist_ok=False)
        path = self.capture_dir / (label+".png")
        command = 'Shot showui filename="%s" -nosuffix' % path.as_posix()
        unreal.SystemLibrary.execute_console_command(self.world, command)
        self.screenshots.append(dict(label=label, path=str(path), requested_world_seconds=self.now(), command=command))

    def native_flight_case(self, case, index, start, velocity, expected_face=None):
        ball = self.balls[index]
        radius = float(ball.get_collision_radius())
        self.require(sphere_inside(start, radius), "Physical roof fixture must start wholly inside venue")
        prior = self.contact(ball)["count"]
        score, live = self.scores(), float(prop(self.match, "LiveSeconds"))
        ball = self.seed_ball(index, start, velocity)
        rows = []
        self.sample(ball, rows)
        yield self.wait_until(lambda: self.contact(ball)["count"] > prior,
                              lambda: self.sample(ball, rows), timeout=1.5)
        self.sample(ball, rows)
        ball.set_actor_tick_enabled(False)
        contact = self.contact(ball)
        normal_ok = expected_face is None or dot(contact["normal"], unit(PLANES[expected_face])) > .99999
        correct = contact["count"] > prior and normal_ok and all(sphere_inside(row["position"], radius) for row in rows)
        correct = correct and all(row["active"] and row["status"] == "" and not row["holder"] for row in rows)
        correct = correct and self.scores() == score and prop(self.match, "bLive") and float(prop(self.match, "LiveSeconds")) > live
        frame_deltas = [b["seconds"]-a["seconds"] for a, b in zip(rows, rows[1:]) if b["seconds"] > a["seconds"]]
        if case == CASES[11]:
            correct = correct and max(frame_deltas, default=0) >= .15
        self.record(case, correct, ball=index, radius_cm=radius, fixture_start=start, fixture_velocity=velocity,
                    prior_contacts=prior, contact=contact, samples=rows, scores=self.scores(), expected_face=expected_face,
                    observed_frame_deltas=frame_deltas)
        self.require(correct, "Native roof flight failed: "+case)
        return contact

    def scenarios(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant")
        self.require(prop(self.match, "bPractice"), "Actual Practice configuration required for scheduled Snitch")
        self.old_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.old_max_fps = float(unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS"))
        for ball in self.balls.values():
            self.contact(ball)
        wanted = VARIANT == "bloodbroom"
        if bool(prop(self.match, "bBloodbroom")) != wanted:
            self.request(8)
            yield self.wait_until(lambda: bool(prop(self.match, "bBloodbroom")) == wanted)
        self.request(2, 3)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 3)
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")))
        self.isolate()
        self.move_pawn((-2500, -1700, 1200))
        self.record(CASES[0], bool(prop(self.match, "bBloodbroom")) == wanted and bool(prop(self.match, "bPractice"))
                    and prop(self.match, "bLive") and 175 < float(prop(self.match, "SecondsLeft")) <= 180,
                    variant=VARIANT, clock=float(prop(self.match, "SecondsLeft")), roster=self.roster())
        self.original_crown = {i: list(self.match.development_get_crown_penalty_state(i)) for i in (0, 1, 2, 5, 6)}
        self.original_score = self.scores()
        self.live_begin = float(prop(self.match, "LiveSeconds"))
        # Cross the former horizontal plane and remain above it longer than the
        # historical neutral-return delay. The hollow cap has no flat bottom.
        ball = self.seed_ball(2, (0, 0, 4090), (0, 0, 1250))
        rows = []
        yield self.wait(1.4, lambda: self.sample(ball, rows))
        ball.set_actor_tick_enabled(False)
        self.record(CASES[1], rows and max(row["position"][2] for row in rows) > EAVE+300
                    and all(row["active"] and row["status"] == "" and not row["holder"] for row in rows)
                    and self.contact(ball)["count"] == 0 and ball.get_actor_location().z > EAVE
                    and self.scores() == self.original_score,
                    samples=rows, roof_contacts=self.contact(ball)["count"], former_plane_cm=EAVE)
        self.move_pawn((-2600, -1200, 3400))
        self.controller.set_control_rotation(unreal.Rotator(pitch=35, yaw=20, roll=0))
        self.capture("hollow-pyramid-before-contact")
        yield self.wait(.15)
        faces = []
        for number, (index, face, point) in enumerate(((0, 0, (4000, 0, APEX-SLOPE_X*4000)),
                (1, 1, (-4000, 0, APEX-SLOPE_X*4000)), (2, 2, (0, 1800, APEX-SLOPE_Y*1800)),
                (5, 3, (0, -1800, APEX-SLOPE_Y*1800)))):
            normal = unit(PLANES[face])
            radius = float(self.balls[index].get_collision_radius())
            start = tuple(point[i]-normal[i]*(radius+200) for i in range(3))
            velocity = tuple(normal[i]*4000 for i in range(3))
            contact = yield from self.native_flight_case(CASES[2+number], index, start, velocity, face)
            faces.append(contact)
        self.capture("pyramid-after-native-contact")
        yield self.wait(.15)
        for offset, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
            # Aim the sphere center at the intersection of both radius-inset
            # planes, not merely the visual mesh edge (unequal slopes matter).
            radius = float(self.balls[2].get_collision_radius())
            inset_x = HALF_X*.48
            inset_y = (SLOPE_X*inset_x+radius*(math.sqrt(1+SLOPE_X*SLOPE_X)
                        -math.sqrt(1+SLOPE_Y*SLOPE_Y)))/SLOPE_Y
            contact_z = APEX-SLOPE_X*inset_x-radius*math.sqrt(1+SLOPE_X*SLOPE_X)
            start = (sx*inset_x, sy*inset_y, contact_z-300)
            yield from self.native_flight_case(CASES[6+offset], 2, start, (0, 0, 5500))
        yield from self.native_flight_case(CASES[10], 2, (0, 0, APEX-350), (0, 0, 6000))
        # A real 5 FPS frame tests native catch-up/substeps, not a direct call to
        # collision code. This global cap is restored immediately and on error.
        unreal.SystemLibrary.execute_console_command(self.world, "t.MaxFPS 5")
        self.fps_restored = False
        yield self.wait(.45)
        samples_before = len(self.frame_samples)
        yield from self.native_flight_case(CASES[11], 6, (0, 0, APEX-500), (0, 0, 65000))
        recent = self.frame_samples[samples_before:]
        deltas = [b-a for a, b in zip(recent, recent[1:]) if b > a]
        # The launch-to-first-observation interval is also an actual native frame.
        self.results[CASES[11]]["detail"]["observed_frame_deltas"] = deltas
        self.results[CASES[11]]["detail"]["requested_frame_cap_fps"] = 5
        unreal.SystemLibrary.execute_console_command(self.world, "t.MaxFPS %.6f" % self.old_max_fps)
        self.fps_restored = abs(float(unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS"))-self.old_max_fps) < .001
        restitution = []
        for contact in faces:
            n, incoming, outgoing = contact["normal"], contact["incoming"], contact["outgoing"]
            before, after = dot(n, incoming), dot(n, outgoing)
            before_tangent = [incoming[i]-before*n[i] for i in range(3)]
            after_tangent = [outgoing[i]-after*n[i] for i in range(3)]
            tangent_error = math.sqrt(sum((x-y)**2 for x, y in zip(before_tangent, after_tangent)))
            restitution.append(dict(incoming_normal=before, outgoing_normal=after,
                                    ratio=-after/before if before else None, tangent_error=tangent_error,
                                    passed=before > 0 and abs(after+.75*before) < .1 and tangent_error < .1))
        self.record(CASES[12], all(row["passed"] for row in restitution), contacts=restitution)
        self.close_ball(2)
        yield self.wait(.35)
        self.interact(True)
        yield self.wait_until(lambda: prop(self.balls[2], "Holder") == self.pawn, timeout=2)
        held = lambda: prop(self.balls[2], "Holder") == self.pawn
        self.record(CASES[13], held(), role=int(prop(self.pawn, "Position")))
        self.require(held(), "Actual pickup required before held-sphere roof check")
        self.interact(False)
        self.move_pawn((0, 0, 4700))
        yield self.wait(.3)
        self.record(CASES[14], held() and self.balls[2].get_actor_location().z > EAVE
                    and str(prop(self.balls[2], "BallStatus")) == "", ball=xyz(self.balls[2].get_actor_location()))
        capsule = self.component(self.pawn, unreal.CapsuleComponent)
        radius, height = capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height()
        ball_radius = self.balls[2].get_collision_radius()
        held_samples = []
        self.move_pawn((0, 0, 5950))
        self.controller.set_control_rotation(unreal.Rotator(pitch=60, yaw=0, roll=0))
        def fly_held():
            self.pawn.add_movement_input(vector((0, 0, 1)), 1, False)
            p, b = xyz(self.pawn.get_actor_location()), xyz(self.balls[2].get_actor_location())
            held_samples.append(dict(rider=p, ball=b, held=held(), capsule_clearance=roof_clearance(p, radius, height),
                                     ball_inside=sphere_inside(b, ball_radius)))
        yield self.wait(.65, fly_held)
        self.record(CASES[15], held_samples and all(row["held"] and row["capsule_clearance"] >= -1
                    and row["ball_inside"] for row in held_samples), samples=held_samples,
                    capsule_radius=radius, capsule_half_height=height, ball_radius=ball_radius)
        self.controller.set_control_rotation(unreal.Rotator(pitch=-30, yaw=0, roll=0))
        self.request(1)
        yield self.wait_until(lambda: not held(), timeout=1)
        self.require(not held(), "Ordinary throw must release the held-ball fixture")
        self.balls[2].set_actor_tick_enabled(False)
        movement_cases = []
        for face, point in enumerate(((4000, 0, APEX-SLOPE_X*4000), (-4000, 0, APEX-SLOPE_X*4000),
                                     (0, 1800, APEX-SLOPE_Y*1800), (0, -1800, APEX-SLOPE_Y*1800))):
            n = unit(PLANES[face])
            start = tuple(point[i]-n[i]*(height+180) for i in range(3))
            self.move_pawn(start)
            rows = []
            yield self.wait(.6, lambda: self.fly_fixture(n, rows))
            clearance = [roof_clearance(p, radius, height) for p in rows]
            movement_cases.append(dict(face=face, samples=rows, clearances=clearance,
                                       passed=bool(rows) and min(clearance) >= -1 and min(clearance) < 12))
        self.record(CASES[16], all(row["passed"] for row in movement_cases), faces=movement_cases)
        crown_after = {i: list(self.match.development_get_crown_penalty_state(i)) for i in self.original_crown}
        self.record(CASES[17], crown_after == self.original_crown and int(prop(self.match, "PendingPenaltyCount")) == 0
                    and self.scores() == self.original_score and prop(self.match, "bLive")
                    and float(prop(self.match, "LiveSeconds")) > self.live_begin,
                    crown_before=self.original_crown, crown_after=crown_after,
                    live_seconds=float(prop(self.match, "LiveSeconds")), scores=self.scores())
        self.isolate()
        self.move_pawn((-2500, -1700, 1000))
        self.dilation_restored = False
        unreal.GameplayStatics.set_global_time_dilation(self.world, 8)
        yield self.wait_until(lambda: bool(prop(self.balls[4], "bActive")), timeout=65)
        unreal.GameplayStatics.set_global_time_dilation(self.world, self.old_dilation)
        self.dilation_restored = True
        self.record(CASES[18], prop(self.balls[4], "bActive") and 60 <= float(prop(self.match, "LiveSeconds")) < 90
                    and self.scores() == self.original_score, live_seconds=float(prop(self.match, "LiveSeconds")),
                    snitch_status=str(prop(self.balls[4], "BallStatus")))
        for offset, index in enumerate((3, 4)):
            ball = self.seed_ball(index, (0, 0, APEX-90), (0, 0, 0))
            rows = []
            yield self.wait(.8, lambda: self.sample(ball, rows))
            ball.set_actor_tick_enabled(False)
            radius = ball.get_collision_radius()
            self.record(CASES[19+offset], rows and all(sphere_inside(row["position"], radius) and row["active"]
                        and row["status"] == "" for row in rows), radius=radius, samples=rows)
        self.isolate()
        before = self.scores()
        self.seed_ball(0, (6200, 0, 2103.12), (2000, 0, 0))
        yield self.wait_until(lambda: self.scores() != before, timeout=2)
        self.balls[0].set_actor_tick_enabled(False)
        self.record(CASES[21], self.score_delta(before) == [13, 0], delta=self.score_delta(before))
        before = self.scores()
        self.seed_ball(1, (-6200, 0, 3048), (-2000, 0, 0))
        yield self.wait_until(lambda: self.scores() != before, timeout=2)
        self.balls[1].set_actor_tick_enabled(False)
        self.record(CASES[22], self.score_delta(before) == [0, 37], delta=self.score_delta(before))


def main():
    if unreal is None and "--list" in sys.argv:
        return dict(status="not_run", cases_per_variant=len(CASES), planned_cases=list(CASES),
                    variants=["regulation", "bloodbroom"], optional_screenshots="capture_screenshots=true")
    runner = PyramidNetTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = runner
    return dict(status="started" if started else runner.final_status, report=str(REPORT),
                planned_cases=len(CASES), variant=VARIANT)


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
