"""Real roof rebound replication in two connected local PIE worlds.

Run separately with BRIDGE_ARGS={"variant":"regulation"} or "bloodbroom",
plus the normal test_native_network.py settings_already_configured/source
arguments when its installed net-mode wrapper is unavailable. Only the server
receives a guarded free-ball physical starting trajectory. Clients receive
native replication; no client transform, velocity, custody, score, clock,
collision outcome or other protected gameplay field is assigned.
"""
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
REPORT = ROOT / ".local" / ("native-pyramid-network-%s-results.json" % VARIANT)
TESTS = (
    "distinct_connected_worlds_and_host_variant_start_replicate",
    "authoritative_free_ball_records_actual_roof_rebound",
    "remote_ball_receives_rebound_above_former_crown_plane",
    "post_bounce_trajectories_stay_inside_and_converge",
    "roof_contact_preserves_scores_custody_live_clocks_and_no_crown_state",
    "managed_play_settings_restored_and_pie_ended",
)
_spec = importlib.util.spec_from_file_location("_bb_pyramid_network_base", ROOT / "Tools/test_native_network.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
base.TESTS, base.REPORT, base.ARGS = TESTS, REPORT, ARGS
unreal, prop, vec = base.unreal, base.prop, base.vec


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def length(values):
    return math.sqrt(sum(float(value)**2 for value in values))


def difference(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def inside_sphere(point, radius, tolerance=1.0):
    x, y, z = point
    if abs(x)+radius > 6850.8+tolerance or abs(y)+radius > 3200.4+tolerance or z-radius < -tolerance:
        return False
    for nx, ny in ((2103.12/6850.8, 0), (-2103.12/6850.8, 0),
                   (0, 2103.12/3200.4), (0, -2103.12/3200.4)):
        if (nx*x+ny*y+z-6309.36)/math.sqrt(nx*nx+ny*ny+1)+radius > tolerance:
            return False
    return True


class PyramidNetworkTests(base.NativeNetworkTests):
    def __init__(self):
        self.flight_samples = []
        super().__init__()

    def write(self, status):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        data = {
            "status": status, "phase": self.phase, "variant": VARIANT,
            "scope": "actual free-ball roof rebound replication in two distinct connected local PIE worlds",
            "elapsed_wall_seconds": round(time.monotonic()-self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "provenance": self.provenance, "events": self.events,
            "settings_restored": self.settings_restored, "reason": self.reason,
            "external_restore_required": base.net_mode_restore_actions(self.provenance),
            "not_covered": ["remote machines, separate processes, LAN or internet sessions",
                            "latency, packet loss, late joining and movement reconciliation",
                            "human controller input or rendered presentation",
                            "full regulation or Hogwarts Legacy multiplayer"],
        }
        base.write_json_atomic(REPORT, data)

    def isolate_server(self):
        # All arrangements remain in the disposable authority world. Park CPUs
        # within the real enclosed arena, well below the independent roof shot.
        for rider in self.host["riders"]:
            if rider.is_player_controlled():
                continue
            movement = rider.get_component_by_class(unreal.CharacterMovementComponent)
            self.require(movement is not None, "CPU movement component missing")
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
            rider.set_actor_tick_enabled(False)
            rider.consume_movement_input_vector()
            slot = int(prop(rider, "RosterIndex"))
            rider.set_actor_location(vec(-1400+slot*175, -2000, 1800), False, True)
        for ball in self.host["balls"].values():
            ball.set_actor_tick_enabled(False)

    def roof_receipt(self):
        values = [float(value) for value in self.host["balls"][0].development_get_roof_contact_state()]
        self.require(len(values) == 10, "Authority roof contact diagnostic requires ten fields")
        return {"count": int(values[0]), "normal": values[1:4],
                "incoming": values[4:7], "outgoing": values[7:10]}

    def crown_state(self):
        return [int(value) for value in self.host["match"].development_get_crown_penalty_state(0)]

    def observe_flight(self):
        server, client = self.host["balls"][0], self.client["balls"][0]
        row = {"server_time": self.now(),
               "server_position": xyz(server.get_actor_location()),
               "client_position": xyz(client.get_actor_location()),
               "server_velocity": xyz(server.get_flight_velocity()),
               "client_velocity": xyz(client.get_flight_velocity())}
        row["position_error_cm"] = length(difference(row["server_position"], row["client_position"]))
        row["velocity_error_cm_s"] = length(difference(row["server_velocity"], row["client_velocity"]))
        row["both_inside"] = all(inside_sphere(row[key], self.ball_radius)
                                  for key in ("server_position", "client_position"))
        self.flight_samples.append(row)
        return row

    def scenarios(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant")
        genuine_worlds = (self.host["world"] != self.client["world"]
                          and self.host["match"].has_authority() and not self.client["match"].has_authority()
                          and self.host["pawn"].has_authority() and not self.client["pawn"].has_authority()
                          and unreal.GameplayStatics.get_game_mode(self.host["world"]) is not None
                          and unreal.GameplayStatics.get_game_mode(self.client["world"]) is None
                          and self.player_id(self.host["pawn"]) != self.player_id(self.client["pawn"]))
        self.require(genuine_worlds, "Two genuinely connected authority/client worlds and distinct owners required")
        self.require(not self.live(self.host) and not self.live(self.client), "Fresh lobby required")
        desired = VARIANT == "bloodbroom"
        if bool(prop(self.host["match"], "bBloodbroom")) != desired:
            self.request(self.host, 8)
        selected = lambda: all(bool(prop(side["match"], "bBloodbroom")) == desired for side in (self.host, self.client))
        yield self.wait(3, selected)
        self.require(selected(), "Host-selected variant did not replicate")
        self.request(self.host, 4)
        both_live = lambda: self.live(self.host) and self.live(self.client)
        yield self.wait(5, both_live)
        self.record(TESTS[0], genuine_worlds and selected() and both_live(),
                    worlds=self.provenance["worlds"], humans=self.provenance["human_player_ids"], variant=VARIANT)
        self.require(both_live(), "Host kickoff must reach both connected worlds")
        self.isolate_server()
        server_ball, client_ball = self.host["balls"][0], self.client["balls"][0]
        self.require(callable(getattr(server_ball, "development_get_roof_contact_state", None)),
                     "Rebuild the read-only roof contact diagnostic")
        self.require(prop(server_ball, "bActive") and prop(server_ball, "Holder") is None,
                     "Fixture requires a genuinely live free Quaffle")
        self.ball_radius = float(server_ball.get_collision_radius())
        scores_before = [self.scores(side) for side in (self.host, self.client)]
        clocks_before = [float(prop(side["match"], "LiveSeconds")) for side in (self.host, self.client)]
        pending_before = [int(prop(side["match"], "PendingPenaltyCount")) for side in (self.host, self.client)]
        crown_before = self.crown_state()
        before = self.roof_receipt()
        start, velocity = vec(0, 1600, 4700), vec(0, 0, 1800)
        self.require(inside_sphere(xyz(start), self.ball_radius) and start.z > 4206.24,
                     "Physical start must be inside the hollow roof above the former crown plane")
        self.require(server_ball.development_set_flight_fixture(start, velocity), "Authority physical trajectory rejected")
        server_ball.set_actor_tick_enabled(True)
        self.events.append({"fixture": "one authority-only free-ball trajectory", "position": xyz(start),
                            "velocity": xyz(velocity), "client_writes": False})
        contact = lambda: self.roof_receipt()["count"] > before["count"]
        yield self.wait(2, contact)
        receipt = self.roof_receipt()
        bounced = (receipt["count"] > before["count"] and receipt["normal"][1] > .4
                   and receipt["normal"][2] > .7 and dot(receipt["incoming"], receipt["normal"]) > 100
                   and dot(receipt["outgoing"], receipt["normal"]) < -100)
        self.record(TESTS[1], bounced and inside_sphere(xyz(server_ball.get_actor_location()), self.ball_radius),
                    contact=receipt, location=xyz(server_ball.get_actor_location()))
        self.require(bounced, "Native flight did not create the expected positive-Y roof contact")

        def received():
            return (client_ball.get_actor_location().z > 4206.24
                    and dot(xyz(client_ball.get_flight_velocity()), receipt["normal"]) < -100
                    and inside_sphere(xyz(client_ball.get_actor_location()), self.ball_radius))
        yield self.wait(1.2, received)
        self.record(TESTS[2], received() and not client_ball.has_authority(),
                    client_position=xyz(client_ball.get_actor_location()),
                    client_velocity=xyz(client_ball.get_flight_velocity()), authority=False)
        self.require(received(), "Remote client did not receive a contained roof rebound above the old plane")
        self.flight_samples = []
        self.observe_flight()
        yield self.wait(1.0, fixture=self.observe_flight)
        final = self.observe_flight()
        first = self.flight_samples[0]
        server_travel = length(difference(final["server_position"], first["server_position"]))
        client_travel = length(difference(final["client_position"], first["client_position"]))
        trajectory_ok = (len(self.flight_samples) >= 5 and all(row["both_inside"] for row in self.flight_samples)
                         and server_travel > 150 and client_travel > 150
                         and final["position_error_cm"] < 350 and final["velocity_error_cm_s"] < 180)
        self.record(TESTS[3], trajectory_ok, samples=self.flight_samples,
                    server_travel_cm=server_travel, client_travel_cm=client_travel,
                    position_tolerance_cm=350, velocity_tolerance_cm_s=180,
                    limits="local sampled trajectory agreement, not latency/reconciliation precision")
        after_scores = [self.scores(side) for side in (self.host, self.client)]
        after_clocks = [float(prop(side["match"], "LiveSeconds")) for side in (self.host, self.client)]
        after_pending = [int(prop(side["match"], "PendingPenaltyCount")) for side in (self.host, self.client)]
        preserved = (both_live() and after_scores == scores_before and after_pending == pending_before
                     and self.crown_state() == crown_before and crown_before[0] == 0
                     and all(new > old+.5 for new, old in zip(after_clocks, clocks_before))
                     and all(prop(ball, "bActive") and prop(ball, "Holder") is None
                             for ball in (server_ball, client_ball)))
        self.record(TESTS[4], preserved, before_scores=scores_before, after_scores=after_scores,
                    before_clocks=clocks_before, after_clocks=after_clocks,
                    before_pending=pending_before, after_pending=after_pending,
                    crown=self.crown_state(), both_live=both_live())


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "variant": VARIANT, "planned_tests": list(TESTS), "count": len(TESTS)}
    runner = PyramidNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
        unreal._basketbroom_native_pyramid_network_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(REPORT), "planned_cases": len(TESTS), "variant": VARIANT}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
