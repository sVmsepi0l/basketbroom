"""Native spell/conduct PIE checks through queued ordinary player inputs.

Run twice in fresh, standalone PIE sessions through editor_bridge.py:
  BRIDGE_ARGS={"variant": "regulation"}  # default, 17 checks
  BRIDGE_ARGS={"variant": "bloodbroom"}  # 3 checks
Each run creates one extra local player and owns/ends its disposable PIE world.
No runtime RPC, protected property, hit confirmation, score or penalty is injected.
Owner HUD rendering must actually acknowledge the successful impediment notice.
--list prints both plans outside Unreal; it does not claim gameplay execution.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 240, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
REGULATION_CASES = (
    "two_local_humans_in_native_regulation_world",
    "basic_torso_hit_applies_damage_without_foul",
    "miss_spends_cooldown_without_damage_or_foul",
    "physical_side_wall_blocks_targeted_spell",
    "protego_blocks_actual_basic_hit",
    "contextual_spell_requires_owned_workshop_without_combat_effect",
    "arresto_reduces_actual_native_flight",
    "confirmed_impediment_then_stupefy_applies_stun_before_double_tap_review",
    "conduct_stoppage_freezes_live_effect_timers",
    "enter_cannot_bypass_pending_conduct_review",
    "moderate_award_stays_pending_before_real_restart",
    "moderate_award_resolves_only_with_opposing_ball_possession",
    "regulation_headshot_applies_damage_before_review",
    "severe_ejection_moves_offender_to_box_and_blocks_role_swap",
    "ejected_offender_cannot_cast_after_resume",
    "five_force_spells_apply_directional_motion_without_leaving_flight",
    "force_spell_target_retains_vertical_input_and_chase_ceiling",
)
BLOODBROOM_CASES = (
    "bloodbroom_can_be_selected_in_lobby_and_is_locked_after_kickoff",
    "bloodbroom_head_unforgivable_bypasses_protego_without_foul",
    "bloodbroom_retains_confirmed_impediment_double_tap_foul",
)
CASES = BLOODBROOM_CASES if VARIANT == "bloodbroom" else REGULATION_CASES
REPORT = ROOT / ".local" / ("native-bloodbroom-spell-test-results.json" if VARIANT == "bloodbroom"
                             else "native-spell-test-results.json")
spec = importlib.util.spec_from_file_location("_bb_spell_scaffold", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)  # A non-__main__ import never starts the base suite.
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeSpellTests(base.NativePlayableTests):
    def __init__(self):
        self.guest = self.guest_controller = None
        self.extra_controllers = []
        self.controller_ticks = []
        self.original_dilation = None
        super().__init__()

    def write_report(self, status, reason=None):
        super().write_report(status, reason)
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        data.update(scope="native same-world local-player spell and conduct integration", variant=VARIANT,
                    not_covered=["remote ownership, networking and internet play",
                                 "physical keyboard bindings, visual quality or frame rate",
                                 "the separate eight contextual workshop/resource adapters",
                                 "canonical automatic penalty tiers, penalty shots and catastrophic review",
                                 "mob attacker identities and window expiry (portable conduct suite)"],
                    fixture_policy="Only disposable actor transforms/component ticks, ordinary local-player lifecycle, "
                                   "native AddMovementInput and queued DevelopmentRequestAction are arranged. "
                                   "No spell state, hit receipt, rule state, score or penalty is written.")
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def conduct(self):
        result = [int(v) for v in self.match.development_get_conduct_state()]
        self.require(len(result) == 6, "Loaded DLL lacks the six-field read-only conduct diagnostic")
        return result

    def effects(self, rider):
        return {name: round(float(prop(rider, name)), 4) for name in
                ("Vitality", "StunRemaining", "ImpedimentRemaining", "ShieldRemaining",
                 "SpellCooldownRemaining", "DisarmRemaining")}

    def guest_request(self, action, value=0):
        self.require(self.guest.development_request_action(action, value), "Guest input was not queued")
        self.event("guest_input_action", action=action, value=value)

    def isolate(self):
        super().isolate()
        # The guest must retain its real Tick: it dispatches queued inputs and
        # owns stun recovery. Movement alone is disabled to anchor spell targets.
        for rider in (self.pawn, self.guest):
            if rider:
                rider.set_actor_tick_enabled(True)
                self.component(rider, unreal.CharacterMovementComponent).set_component_tick_enabled(False)

    def anchor_pair(self, caster=(-1200, 0, 1800), target=(-400, 0, 1872), yaw=0):
        for rider, point in ((self.pawn, caster), (self.guest, target)):
            movement = self.component(rider, unreal.CharacterMovementComponent)
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
            rider.consume_movement_input_vector()
            rider.set_actor_location(vector(point), False, True)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=yaw, roll=0))
        self.guest_controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=180, roll=0))
        yield from self.settle_aim(yaw)
        self.event("spell_geometry", caster=xyz(self.pawn.get_actor_location()),
                   target=xyz(self.guest.get_actor_location()), yaw=yaw, native_aim=xyz(self.pawn.get_aim_direction()))

    def settle_aim(self, yaw):
        # APawn::GetBaseAimRotation reads the player's cached camera POV. A
        # controller rotation edit is not that POV until a later world camera
        # update. Wait for the actual gameplay getter before queuing the cast.
        def aligned():
            aim = self.pawn.get_aim_direction()
            return aim.x*math.cos(math.radians(yaw))+aim.y*math.sin(math.radians(yaw)) > .999

        yield self.wait_until(aligned, timeout=1)
        self.require(aligned(), "Native camera aim did not settle to the arranged horizontal spell ray")

    def ready_to_cast(self, rider=None):
        rider = rider or self.pawn
        return float(prop(rider, "SpellCooldownRemaining")) <= 0 and float(prop(rider, "StunRemaining")) <= 0

    def side_wall_evidence(self):
        # Public profile traces ignore both fixture riders. The shorter segment
        # must stay clear; extending it across the side net must hit real world
        # collision. This cannot succeed merely because the spell missed.
        start = vector((-1200, dimensions.HALF_WIDTH-400.4, 1872))

        def blocked_to(y):
            result = unreal.SystemLibrary.line_trace_single_by_profile(
                self.world, start, vector((-1200, y, 1872)), "BlockAll", False,
                [self.pawn, self.guest], unreal.DrawDebugTrace.NONE, True)
            self.require(result is None or isinstance(result, unreal.HitResult),
                         "Unexpected public trace return type; no collision result is assumed")
            return result is not None

        evidence = {"profile": "BlockAll", "start": xyz(start), "clear_end_y": dimensions.HALF_WIDTH-20.4,
                    "blocked_end_y": dimensions.HALF_WIDTH+39.6, "net_y_cm": dimensions.HALF_WIDTH,
                    "short_clear": not blocked_to(dimensions.HALF_WIDTH-20.4), "through_net_blocked": blocked_to(dimensions.HALF_WIDTH+39.6)}
        self.require(evidence["short_clear"] and evidence["through_net_blocked"],
                     "Side-wall fixture must bracket actual world collision")
        return evidence

    def drain_feedback(self):
        # Old non-impediment notices are intentionally not cleared or replaced.
        # Drain the genuine owner display queue before the 3-second hit window.
        yield self.wait_until(lambda: not str(prop(self.pawn, "SpellFeedback"))
                             and float(prop(self.pawn, "SpellFeedbackRemaining")) <= 0, timeout=35)
        self.require(not str(prop(self.pawn, "SpellFeedback")),
                     "Owner HUD feedback queue did not drain; no confirmation is manufactured")

    def wait_for_displayed_impediment(self):
        # Critical notices start at 2.25 seconds and remain there until the
        # owner's actual HUD draws them. Their native countdown reaching 1.90
        # proves more than the 0.25-second display interval required before
        # Rider Tick sends the receipt. Merely observing the queued text is
        # insufficient, including in a renderer-less PIE session.
        def observation():
            return {
                "notice": str(prop(self.pawn, "SpellFeedback")),
                "feedback_seconds_remaining": float(prop(self.pawn, "SpellFeedbackRemaining")),
                "impediment_seconds_remaining": float(prop(self.guest, "ImpedimentRemaining")),
                "ready_to_cast": self.ready_to_cast(),
            }

        def displayed(data):
            return ("target impeded" in data["notice"]
                    and 0 < data["feedback_seconds_remaining"] <= 1.90
                    and data["impediment_seconds_remaining"] > .15
                    and data["ready_to_cast"])

        yield self.wait_until(lambda: displayed(observation()), timeout=2)
        data = observation()
        self.event("owner_impediment_display_observation", **data,
                   displayed_countdown_observed=displayed(data),
                   proof="Native critical-notice countdown after actual owner HUD draw; no ACK injected")
        self.require(displayed(data),
                     "Double-tap requires a genuine owner HUD display countdown and active impediment; "
                     "queued text alone is insufficient. Run this check in rendered PIE.")
        return data

    def measure_guest_flight(self):
        movement = self.component(self.guest, unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(True)
        start, began, samples = self.guest.get_actor_location(), self.now(), []

        def apply_input():
            self.guest.add_movement_input(vector((0, 1, 0)), 1.0, True)
            samples.append(self.now())

        # Feed native movement immediately, then once per callback. The result
        # records elapsed time and displacement, not an assumed frame count.
        apply_input()
        yield self.wait(.4, apply_input)
        end, elapsed = self.guest.get_actor_location(), self.now() - began
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(False)
        self.guest.consume_movement_input_vector()
        return {"start": xyz(start), "end": xyz(end), "seconds": round(elapsed, 4),
                "dy": round(float(end.y - start.y), 4), "off_axis": round(abs(end.x-start.x)+abs(end.z-start.z), 4),
                "mean_speed": round(float(end.y-start.y) / max(elapsed, .001), 4), "input_samples": len(samples)}

    def double_tap(self, measure=False):
        yield self.wait_until(lambda: self.ready_to_cast() and self.ready_to_cast(self.guest)
                             and float(prop(self.guest, "ImpedimentRemaining")) <= 0, timeout=10)
        self.require(self.ready_to_cast() and float(prop(self.guest, "ImpedimentRemaining")) <= 0,
                     "Double-tap fixture requires naturally recovered participants")
        yield from self.drain_feedback()
        yield from self.anchor_pair()
        normal = None
        if measure:
            normal = yield from self.measure_guest_flight()
            self.require(normal["dy"] > 30 and normal["off_axis"] < 5,
                         "Unimpeded native-flight control must actually move")
            yield from self.anchor_pair()
        before = self.conduct()
        self.request(6, 10)  # Arresto Momentum, a genuine impediment.
        yield self.wait_until(lambda: float(prop(self.guest, "ImpedimentRemaining")) > 0, timeout=.8)
        self.require(float(prop(self.guest, "ImpedimentRemaining")) > 0 and self.conduct()[0] == before[0],
                     "Torso Arresto must apply a legal real impediment")
        slowed = None
        if measure:
            slowed = yield from self.measure_guest_flight()
            self.record(REGULATION_CASES[6], slowed["dy"] > 5 and slowed["off_axis"] < 5
                        and slowed["mean_speed"] < normal["mean_speed"] * .75
                        and float(prop(self.guest, "ImpedimentRemaining")) > 0,
                        normal=normal, impeded=slowed, effects=self.effects(self.guest))
            yield from self.anchor_pair()
        confirmation = yield from self.wait_for_displayed_impediment()
        notice = confirmation["notice"]
        remaining = confirmation["impediment_seconds_remaining"]
        self.request(6, 2)  # Stupefy is stun=true, impediment=false.
        yield self.wait_until(lambda: bool(prop(self.match, "bConductReviewPending")), timeout=.65)
        state = self.conduct()
        passed = (state[0] == before[0]+1 and state[1] == 1 and state[3] == 8
                  and state[2] == int(prop(self.pawn, "RosterIndex"))
                  and float(prop(self.guest, "StunRemaining")) > 0 and not prop(self.match, "bLive"))
        name = BLOODBROOM_CASES[2] if VARIANT == "bloodbroom" else REGULATION_CASES[7]
        self.record(name, passed, before=before, after=state, target=self.effects(self.guest),
                    genuine_feedback=notice, impediment_seconds_before_stun=remaining,
                    last_call=str(prop(self.match, "LastConductCall")))
        self.require(passed, "Successful confirmed-impediment Stupefy must produce exactly DOUBLE-TAP review")

    def force_spells(self):
        movement = self.component(self.guest, unreal.CharacterMovementComponent)
        # IsFlying is a public BlueprintCallable NavMovementComponent query;
        # no Python enum spelling or protected MovementMode write is needed.
        self.require(callable(getattr(movement, "is_flying", None)), "Public IsFlying query must be reflected")
        observations = []
        for spell, label, axis, sign in ((6, "Accio", 0, -1), (7, "Depulso", 0, 1),
                                        (8, "Descendo", 2, -1), (9, "Flipendo", 2, 1),
                                        (12, "Levioso", 2, 1)):
            yield self.wait_until(lambda: self.ready_to_cast() and self.ready_to_cast(self.guest), timeout=4)
            yield from self.anchor_pair()
            start = xyz(self.guest.get_actor_location())
            samples = []
            movement.set_component_tick_enabled(True)

            def observe():
                point = xyz(self.guest.get_actor_location())
                samples.append({"point": point, "velocity": xyz(prop(movement, "Velocity")),
                                "flying": bool(movement.is_flying())})

            self.request(6, spell)
            yield self.wait_until(lambda: abs(xyz(self.guest.get_actor_location())[axis]-start[axis]) > 3,
                                  observe, timeout=.65)
            observe()
            end = xyz(self.guest.get_actor_location())
            signed_delta = (end[axis]-start[axis])*sign
            peak_velocity = max((row["velocity"][axis]*sign for row in samples), default=0)
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
            observations.append({"spell": label, "start": start, "end": end, "signed_delta": signed_delta,
                                 "peak_directional_velocity": peak_velocity, "samples": samples,
                                 "passed": signed_delta > 3 and all(row["flying"] for row in samples)
                                           and bool(movement.is_flying()) and self.conduct()[0] == 0})
        self.record(REGULATION_CASES[15], all(row["passed"] for row in observations), spells=observations)

        # A real movement request must still climb after the final lift impulse.
        # Check the actual upper envelope as well, where Falling previously
        # bypassed the custom PhysFlying bounds. Never restore movement mode.
        yield from self.anchor_pair(caster=(-1200, 0, 1800), target=(-400, 0, dimensions.APEX_HEIGHT-209.36))
        start = xyz(self.guest.get_actor_location())
        movement.set_component_tick_enabled(True)
        samples = []

        def climb():
            self.guest.add_movement_input(vector((0, 0, 1)), 1.0, True)
            samples.append({"point": xyz(self.guest.get_actor_location()), "flying": bool(movement.is_flying())})

        climb()
        yield self.wait(1.2, climb)
        end = xyz(self.guest.get_actor_location())
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(False)
        self.guest.consume_movement_input_vector()
        # Whole capsule must fit below the pyramid apex. Radius/height are read from the
        # actor's actual collision component, not assumed from its constructor.
        capsule = self.component(self.guest, unreal.CapsuleComponent)
        height = float(capsule.get_scaled_capsule_half_height())
        peak = max([end[2]]+[row["point"][2] for row in samples])
        self.record(REGULATION_CASES[16], end[2]-start[2] > 25 and peak+height <= dimensions.APEX_HEIGHT+2
                    and all(row["flying"] for row in samples) and movement.is_flying(),
                    start=start, end=end, capsule_half_height=height, peak_center_z=peak, samples=samples)
        yield from self.anchor_pair()

    def prepare(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant argument")
        self.require(callable(getattr(self.match, "development_get_conduct_state", None)),
                     "Loaded native DLL has no conduct diagnostic; rebuild and restart")
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        unreal.GameplayStatics.set_global_time_dilation(self.world, .5)
        self.provenance.update(owned_world_dilation=.5, input_path="guarded FIFO -> native rider Tick -> ordinary action",
                               hit_confirmation="actual owner HUD draw -> native receipt; no injected ACK",
                               editor_assets_saved=False)
        self.guest_controller = unreal.GameplayStatics.create_player(self.world, -1, True)
        self.require(self.guest_controller is not None, "Public CreatePlayer failed")
        self.extra_controllers.append(self.guest_controller)
        yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 1) is not None, timeout=2)
        self.guest = unreal.GameplayStatics.get_player_pawn(self.world, 1)
        self.require(self.guest and self.guest.get_class() == self.classes["BBRiderCharacter"],
                     "Second local participant must possess a native rider")
        for controller in (self.controller, self.guest_controller):
            self.controller_ticks.append((controller, bool(controller.is_actor_tick_enabled())))
            controller.set_actor_tick_enabled(False)
        self.provenance["aim_fixture"] = "Local controller look ticks suspended; native Rider input queue and HUD drawing retained"
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"]))
        self.require(len(self.riders) == 16 and self.roster_valid()
                     and int(prop(self.pawn, "TeamIndex")) != int(prop(self.guest, "TeamIndex")),
                     "Spell fixture needs valid opposing human roster entries")
        self.provenance["local_humans"] = [int(prop(r, "RosterIndex")) for r in (self.pawn, self.guest)]
        desired = VARIANT == "bloodbroom"
        if bool(prop(self.match, "bBloodbroom")) != desired:
            self.request(8)
            yield self.wait_until(lambda: bool(prop(self.match, "bBloodbroom")) == desired, timeout=1)
        self.require(bool(prop(self.match, "bBloodbroom")) == desired, "Lobby must accept the requested match variant")
        selected_in_lobby = str(prop(self.match, "Status")) == "LOBBY" and not prop(self.match, "bLive")
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        self.require(prop(self.match, "bLive"), "Host kickoff must enter actual live play")
        self.isolate()  # Kickoff restored regulation opening locations.
        yield from self.anchor_pair()
        if desired:
            self.request(8)
            yield self.wait(.2)
            self.record(BLOODBROOM_CASES[0], selected_in_lobby and bool(prop(self.match, "bBloodbroom"))
                        and bool(prop(self.match, "bLive")), status=str(prop(self.match, "Status")),
                        bloodbroom=bool(prop(self.match, "bBloodbroom")), selected_in_lobby=selected_in_lobby)
        else:
            self.record(REGULATION_CASES[0], len(self.riders) == 16 and self.roster_valid()
                        and sum(r.is_player_controlled() for r in self.riders) == 2
                        and not prop(self.match, "bBloodbroom") and prop(self.match, "bLive"),
                        roster=self.roster(), native_world=self.world.get_path_name())

    def regulation(self):
        before = self.effects(self.guest)
        self.request(6, 0)
        yield self.wait_until(lambda: float(prop(self.guest, "Vitality")) < before["Vitality"]-2, timeout=.6)
        after = self.effects(self.guest)
        self.record(REGULATION_CASES[1], after["Vitality"] <= before["Vitality"]-5
                    and after["Vitality"] >= before["Vitality"]-8.1 and self.conduct()[0] == 0,
                    before=before, after=after, conduct=self.conduct())

        yield self.wait_until(self.ready_to_cast, timeout=1)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=90, roll=0))
        yield from self.settle_aim(90)
        before = self.effects(self.guest)
        self.request(6, 0)
        yield self.wait_until(lambda: float(prop(self.pawn, "SpellCooldownRemaining")) > 0, timeout=.25)
        self.record(REGULATION_CASES[2], float(prop(self.guest, "Vitality")) >= before["Vitality"]
                    and float(prop(self.pawn, "SpellCooldownRemaining")) > 0 and self.conduct()[0] == 0
                    and self.pawn.get_aim_direction().y > .999,
                    before=before, after=self.effects(self.guest), native_aim=xyz(self.pawn.get_aim_direction()),
                    cooldown=float(prop(self.pawn, "SpellCooldownRemaining")))

        yield self.wait_until(self.ready_to_cast, timeout=1)
        yield from self.anchor_pair(caster=(-1200, dimensions.HALF_WIDTH-400.4, 1800), target=(-1200, dimensions.HALF_WIDTH+199.6, 1872), yaw=90)
        wall = self.side_wall_evidence()
        before = self.effects(self.guest)
        self.request(6, 0)
        yield self.wait_until(lambda: float(prop(self.pawn, "SpellCooldownRemaining")) > 0, timeout=.25)
        self.record(REGULATION_CASES[3], float(prop(self.guest, "Vitality")) >= before["Vitality"]
                    and float(prop(self.pawn, "SpellCooldownRemaining")) > 0 and self.conduct()[0] == 0
                    and self.pawn.get_aim_direction().y > .999,
                    before=before, after=self.effects(self.guest), collision_evidence=wall,
                    native_aim=xyz(self.pawn.get_aim_direction()),
                    caster=xyz(self.pawn.get_actor_location()), target=xyz(self.guest.get_actor_location()))

        yield self.wait_until(self.ready_to_cast, timeout=1)
        yield from self.drain_feedback()
        yield from self.anchor_pair()
        self.guest_request(7)
        yield self.wait_until(lambda: float(prop(self.guest, "ShieldRemaining")) > 0, timeout=.4)
        self.require(float(prop(self.guest, "ShieldRemaining")) > 0, "Actual guest Protego must be raised")
        before = self.effects(self.guest)
        self.request(6, 0)
        yield self.wait_until(lambda: "blocked" in str(prop(self.pawn, "SpellFeedback")).lower(), timeout=.6)
        block_feedback = str(prop(self.pawn, "SpellFeedback"))
        self.record(REGULATION_CASES[4], float(prop(self.guest, "Vitality")) >= before["Vitality"]
                    and float(prop(self.guest, "ShieldRemaining")) > 0
                    and "blocked" in block_feedback.lower() and self.conduct()[0] == 0,
                    before=before, after=self.effects(self.guest), conduct=self.conduct(), feedback=block_feedback)

        yield self.wait_until(self.ready_to_cast, timeout=1)
        yield from self.drain_feedback()
        before = self.effects(self.guest)
        self.request(6, 4)  # A rider is not the owned Alohomora workshop target.
        yield self.wait_until(lambda: bool(str(prop(self.pawn, "SpellFeedback"))), timeout=.5)
        self.record(REGULATION_CASES[5], bool(str(prop(self.pawn, "SpellFeedback")))
                    and float(prop(self.pawn, "SpellCooldownRemaining")) == 0
                    and float(prop(self.guest, "Vitality")) >= before["Vitality"] and self.conduct()[0] == 0,
                    feedback=str(prop(self.pawn, "SpellFeedback")), target=self.effects(self.guest),
                    context_status="requires the owned workshop locker; ordinary rider target is rejected")

        yield from self.force_spells()
        yield from self.double_tap(measure=True)
        frozen = {"clock": float(prop(self.match, "LiveSeconds")), "caster": self.effects(self.pawn),
                  "target": self.effects(self.guest)}
        yield self.wait(.6)
        after = {"clock": float(prop(self.match, "LiveSeconds")), "caster": self.effects(self.pawn),
                 "target": self.effects(self.guest)}
        self.record(REGULATION_CASES[8], frozen == after and not prop(self.match, "bLive"), before=frozen, after=after)
        state = self.conduct()
        self.request(4)
        yield self.wait(.2)
        self.record(REGULATION_CASES[9], self.conduct() == state and not prop(self.match, "bLive")
                    and bool(prop(self.match, "bConductReviewPending")), before=state, after=self.conduct())

        self.request(9)  # The actual host F7 playtest-referee action.
        yield self.wait_until(lambda: not prop(self.match, "bConductReviewPending"), timeout=1)
        queued = self.conduct()
        self.require(queued[5] in (0, 1, 2), "F7 must queue a real scoring-ball award")
        award = self.balls[queued[5]]
        self.record(REGULATION_CASES[10], queued[1] == 0 and not prop(self.match, "bLive")
                    and int(prop(self.match, "PendingPenaltyCount")) >= 1
                    and prop(award, "Holder") is None and not prop(award, "bActive")
                    and str(prop(award, "BallStatus")) == "penalty", conduct=queued,
                    pending=int(prop(self.match, "PendingPenaltyCount")), ball_status=str(prop(award, "BallStatus")))
        self.request(4)
        yield self.wait_until(lambda: prop(award, "Holder") is not None and self.conduct()[5] == -1, timeout=3)
        holder = prop(award, "Holder")
        self.record(REGULATION_CASES[11], bool(prop(self.match, "bLive")) and holder is not None
                    and int(prop(holder, "TeamIndex")) == int(prop(self.guest, "TeamIndex"))
                    and int(prop(holder, "Position")) in (0, 1, 2, 3)
                    and self.conduct()[5] == -1 and int(prop(self.match, "PendingPenaltyCount")) == 0
                    and self.conduct()[0] == queued[0], conduct=self.conduct(),
                    holder_slot=int(prop(holder, "RosterIndex")) if holder else None,
                    pending=int(prop(self.match, "PendingPenaltyCount")), ball_status=str(prop(award, "BallStatus")))

        # The awarded CPU may have moved into the test's sight line. Move only
        # that disposable actor to a safe in-court mark, retaining its custody.
        if holder and holder != self.guest:
            holder.set_actor_location(vector((2500, 2000, 1800)), False, True)
        yield self.wait_until(lambda: self.ready_to_cast() and self.ready_to_cast(self.guest), timeout=4)
        yield from self.anchor_pair(target=(-400, 0, 1792))  # Beam at target+80cm: capsule head zone.
        before_health, before_fouls = float(prop(self.guest, "Vitality")), self.conduct()[0]
        self.request(6, 0)
        yield self.wait_until(lambda: bool(prop(self.match, "bConductReviewPending")), timeout=.5)
        self.record(REGULATION_CASES[12], self.conduct()[0] == before_fouls+1 and self.conduct()[3] == 2
                    and float(prop(self.guest, "Vitality")) < before_health-4
                    and not prop(self.match, "bLive"), before_health=before_health,
                    target=self.effects(self.guest), conduct=self.conduct())
        self.require(prop(self.match, "bConductReviewPending"), "Actual headshot must create review before F9")
        role, slot = int(prop(self.pawn, "Position")), int(prop(self.pawn, "RosterIndex"))
        self.request(11)
        yield self.wait_until(lambda: not prop(self.match, "bConductReviewPending")
                             and abs(float(self.pawn.get_actor_location().x)) > dimensions.HALF_LENGTH, timeout=1)
        self.request(2, 1 if role != 1 else 3)
        yield self.wait(.2)
        self.record(REGULATION_CASES[13], not prop(self.match, "bConductReviewPending")
                    and int(prop(self.pawn, "Position")) == role and int(prop(self.pawn, "RosterIndex")) == slot
                    and abs(float(self.pawn.get_actor_location().x)) > dimensions.HALF_LENGTH
                    and float(prop(self.pawn, "StunRemaining")) > .5,
                    role=int(prop(self.pawn, "Position")), position=xyz(self.pawn.get_actor_location()),
                    review=str(prop(self.match, "ConductReviewStatus")), effects=self.effects(self.pawn))
        self.request(4)
        yield self.wait_until(lambda: prop(self.match, "bLive")
                             and float(prop(self.pawn, "SpellCooldownRemaining")) == 0, timeout=2)
        self.require(prop(self.match, "bLive"), "Host must resume after served ejection")
        before = self.conduct()
        self.request(6, 0)
        yield self.wait(.2)
        self.record(REGULATION_CASES[14], float(prop(self.pawn, "SpellCooldownRemaining")) == 0
                    and float(prop(self.pawn, "StunRemaining")) > .5 and self.conduct() == before,
                    effects=self.effects(self.pawn), conduct=self.conduct())

    def bloodbroom(self):
        yield from self.anchor_pair(target=(-400, 0, 1792))
        self.guest_request(7)
        yield self.wait_until(lambda: float(prop(self.guest, "ShieldRemaining")) > 0, timeout=.5)
        shield_before = float(prop(self.guest, "ShieldRemaining"))
        self.require(shield_before > 0, "Bloodbroom shield-bypass fixture requires actual Protego")
        self.request(6, 26)
        yield self.wait_until(lambda: float(prop(self.guest, "StunRemaining")) > 0, timeout=.5)
        self.record(BLOODBROOM_CASES[1], bool(prop(self.match, "bBloodbroom")) and prop(self.match, "bLive")
                    and self.conduct()[0] == 0 and not prop(self.match, "bConductReviewPending")
                    and float(prop(self.guest, "StunRemaining")) >= 5
                    and abs(float(prop(self.guest, "Vitality"))-50) < .1,
                    shield_before=shield_before, target=self.effects(self.guest), conduct=self.conduct(),
                    target_relative_beam_z_cm=80)
        yield from self.double_tap()

    def scenarios(self):
        yield from self.prepare()
        if VARIANT == "bloodbroom":
            yield from self.bloodbroom()
        else:
            yield from self.regulation()

    def finish(self, status, reason=None):
        if unreal and self.owns_play:
            cleanup_errors = []
            for controller, enabled in self.controller_ticks:
                try:
                    controller.set_actor_tick_enabled(enabled)
                except Exception:
                    cleanup_errors.append("Controller tick restore: " + traceback.format_exc())
            self.provenance["controller_look_ticks_restored"] = not cleanup_errors
            self.controller_ticks = []
            try:
                for controller in reversed(self.extra_controllers[:]):
                    unreal.GameplayStatics.remove_player(controller, True)
                    self.extra_controllers.remove(controller)
                self.provenance["extra_local_players_removed"] = not self.extra_controllers
            except Exception:
                cleanup_errors.append("Local-player cleanup: " + traceback.format_exc())
            try:
                if self.world and self.original_dilation is not None:
                    unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)
                    self.provenance["world_dilation_restored"] = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
            except Exception:
                cleanup_errors.append("World dilation restore: " + traceback.format_exc())
            if cleanup_errors:
                status, reason = "error", (reason or "") + "\n" + "\n".join(cleanup_errors)
            self.provenance["pie_cleanup"] = "EndPlay requested by owning base runner; external runner must observe session ended"
        super().finish(status, reason)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "regulation": list(REGULATION_CASES), "bloodbroom": list(BLOODBROOM_CASES),
                "total_planned": len(REGULATION_CASES)+len(BLOODBROOM_CASES)}
    test = NativeSpellTests()
    try:
        started = test.begin()
    except Exception:
        test.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = test
    return {"status": "started" if started else test.final_status, "variant": VARIANT,
            "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
