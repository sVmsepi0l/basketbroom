"""Author simplified native UE 5.8 scrimmage riders.

Scoring roles pursue assigned carried balls, contest shared possession, carry,
and shoot actual ballistic balls. Hurleybacks and Scouts patrol visually in this
first slice; they do not award points or fake chase catches. Python authors the
Blueprint only and is not a game runtime dependency.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
from pathlib import Path

import unreal

from bp_graph import Graph
from build_gameplay import (
    ACTOR, BASE, MANAGER, add, bind_manager, both, div, eqi, fn, fresh,
    gt, location, lt, math, mg, mul, neg, setloc, sub, vadd, vec, vmul, vsub, xyz,
)


BALL = BASE + "BP_BBBall.BP_BBBall_C"


def build():
    ball_class = unreal.load_class(None, BALL)
    if ball_class is None:
        raise RuntimeError("Compile BP_BBBall with BotOwner and BotPosition before bots")
    if unreal.load_class(None, MANAGER) is None:
        raise RuntimeError("Compile BP_BBMatch before bots")
    bp, g = fresh("BP_BBBot", unreal.StaticMeshActor)
    for name, kind, default in (
        ("Team", "int", 0), ("Slot", "int", 0), ("PlayerRole", "int", 1),
        ("Home", "vector", (0, 0, 1500)), ("Rest", "double", 0),
    ):
        g.var(name, kind, default, editable=name in ("Team", "Slot", "PlayerRole", "Home"))
    g.var("Target", ball_class, editable=True)
    bind_manager(g)
    g.compile()

    # Reusable movement remains kinematic, matching the slice's ball simulation.
    move = g.function("MoveStep")
    destination = move.param("Destination", "vector")
    speed = move.param("Speed", "double", 1400)
    delta = move.param("Delta", "double")
    facing = math(move, "FindLookAtRotation", Start=location(move), Target=destination)
    smoothed = math(move, "RInterpTo", Current=fn(move, ACTOR + "K2_GetActorRotation"),
                    Target=facing, DeltaTime=delta, InterpSpeed=5)
    turn = move.call(ACTOR + "K2_SetActorRotation", NewRotation=smoothed, bTeleportPhysics=True)
    step = math(move, "VInterpTo_Constant", Current=location(move), Target=destination,
                DeltaTime=delta, InterpSpeed=speed)
    move.chain(move.entry(), turn, setloc(move, step))
    g.compile()

    patrol = g.function("Patrol")
    delta = patrol.param("Delta", "double")
    phase = add(patrol, mul(patrol, mg(patrol, "Elapsed"), 0.38), mul(patrol, patrol.get("Slot"), 1.17))
    offset = vec(patrol,
                 mul(patrol, math(patrol, "Sin", A=phase), 320),
                 mul(patrol, math(patrol, "Cos", A=phase), 380),
                 mul(patrol, math(patrol, "Sin", A=mul(patrol, phase, 0.73)), 160))
    drift = patrol.call("MoveStep", Destination=vadd(patrol, patrol.get("Home"), offset),
                        Speed=650, Delta=delta)
    patrol.exec(patrol.entry(), drift)
    g.compile()

    tick = g.event("ReceiveTick")
    dt = g.out(tick, "DeltaSeconds")
    valid_match = g.branch(fn(g, "/Script/Engine.KismetSystemLibrary.IsValid", Object=g.get("Match")))
    live = g.branch(neg(g, mg(g, "MatchOver")))
    rest = g.set("Rest", math(g, "FMax", A=sub(g, g.get("Rest"), dt), B=0))
    scoring_role = g.branch(lt(g, g.get("PlayerRole"), 4))
    g.chain(tick, valid_match, live, rest, scoring_role)

    def patrol_after(node, output="else"):
        g.exec(node, g.call("Patrol", Delta=dt), output)

    def ball_get(name):
        return g.get(name, target=g.get("Target"), class_path=BALL)

    def ball_set(name, value):
        return g.set(name, value, target=g.get("Target"), class_path=BALL)

    patrol_after(scoring_role)
    valid_target = g.branch(fn(g, "/Script/Engine.KismetSystemLibrary.IsValid", Object=g.get("Target")))
    g.exec(scoring_role, valid_target)
    patrol_after(valid_target)
    available = both(g, both(g, lt(g, g.get("Rest"), 0.001), lt(g, ball_get("Kind"), 2)),
                     both(g, neg(g, ball_get("Held")), lt(g, ball_get("Cooldown"), 0.001)))
    action = g.branch(available)
    g.exec(valid_target, action)
    patrol_after(action)
    owned = g.branch(eqi(g, ball_get("BotOwner"), g.get("Slot")))
    g.exec(action, owned)

    # Attack the other team's center hoop. The target height is ball-specific.
    side = math(g, "SelectFloat", A=1, B=-1, bPickA=eqi(g, g.get("Team"), 0))
    goal_x = mul(g, side, dimensions.GOAL_PLANE_X + 60)
    goal_z = math(g, "SelectFloat", A=3048, B=2103.12, bPickA=eqi(g, ball_get("Kind"), 1))
    goal = vec(g, goal_x, 0, goal_z)
    approach = vsub(g, goal, vec(g, 0, 0, 60))
    carry_move = g.call("MoveStep", Destination=approach, Speed=1400, Delta=dt)
    carry_position = vadd(g, location(g), vec(g, 0, 0, 60))
    carry = ball_set("BotPosition", carry_position)
    range_to_goal = math(g, "VSize", A=vsub(g, goal, carry_position))
    shoot = g.branch(lt(g, range_to_goal, 2400))
    g.chain(owned, carry_move, carry, shoot)

    # v=(target-origin)/0.7 + 0.5*g*0.7; gravity is 380 cm/s².
    # Place the released ball at the exact launch origin so tick order cannot
    # give the shot an origin one frame behind its computed trajectory.
    launch_origin = ball_get("BotPosition")
    launch = setloc(g, launch_origin, g.get("Target"))
    launch_p = ball_set("P", launch_origin)
    launch_old = ball_set("OldP", launch_origin)
    velocity = vadd(g, vmul(g, vsub(g, goal, launch_origin), 1.0 / 0.7), vec(g, 0, 0, 133))
    impulse = ball_set("Velocity", velocity)
    relinquish = ball_set("BotOwner", -1)
    cooldown = ball_set("Cooldown", 0.5)
    recover = g.set("Rest", 2.0)
    g.chain(shoot, launch, launch_p, launch_old, impulse, relinquish, cooldown, recover)

    # A bot never steals from a human carrier or an existing bot owner. Free
    # balls are claimed atomically by the first nearby rider in engine tick order.
    free = g.branch(lt(g, ball_get("BotOwner"), 0))
    g.exec(owned, free, "else")
    patrol_after(free)
    ball_position = location(g, g.get("Target"))
    pursuit = g.call("MoveStep", Destination=vsub(g, ball_position, vec(g, 0, 0, 60)),
                     Speed=1400, Delta=dt)
    near = g.branch(lt(g, math(g, "VSize", A=vsub(g, ball_position, location(g))), 180))
    claim = ball_set("BotOwner", g.get("Slot"))
    pocket = ball_set("BotPosition", vadd(g, location(g), vec(g, 0, 0, 60)))
    stop = ball_set("Velocity", (0, 0, 0))
    g.chain(free, pursuit, near, claim, pocket, stop)

    g.compile(save=True)
    g.export_manifest(Path(__file__).resolve().parents[1] / ".local" / "ue5" / "bots_manifest.json")
    return bp
