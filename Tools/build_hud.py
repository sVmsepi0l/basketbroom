"""Author the standalone UE 5.8 Basketbroom training HUD as native Blueprint.

Import inside Unreal after BP_BBMatch exists, then call build(). Runtime drawing
is Blueprint HUD/Canvas code; Python is used only to author the asset.
"""
from pathlib import Path

import unreal

from bp_graph import Graph, create_blueprint
from build_gameplay import fresh


ASSET = "/Basketbroom/Blueprints/BP_BBHUD"
MANAGER = "/Basketbroom/Blueprints/BP_BBMatch.BP_BBMatch_C"
MATH = "/Script/Engine.KismetMathLibrary."
STR = "/Script/Engine.KismetStringLibrary."
TEXT = "/Script/Engine.KismetTextLibrary."
HUD = "/Script/Engine.HUD."
INK = "(R=0.016,G=0.027,B=0.039,A=0.88)"
INK_LIGHT = "(R=0.030,G=0.047,B=0.061,A=0.82)"
CREAM = "(R=0.94,G=0.91,B=0.82,A=1)"
MUTED = "(R=0.53,G=0.63,B=0.65,A=1)"
TEAL = "(R=0.15,G=0.88,B=0.76,A=1)"
COPPER = "(R=1,G=0.48,B=0.24,A=1)"
GOLD = "(R=0.96,G=0.74,B=0.32,A=1)"
# Ball identity is independent of team identity. These match stage_game.py's
# orange Quaffle, violet Quarks, cyan Snipe and gold Snitch, lifted for text.
QUAFFLE = "(R=1,G=0.30,B=0.13,A=1)"
QUARK = "(R=0.70,G=0.38,B=1,A=1)"
SNIPE = "(R=0.13,G=0.86,B=1,A=1)"


def build():
    manager_class = unreal.load_class(None, MANAGER)
    if manager_class is None:
        raise RuntimeError("Build and compile BP_BBMatch before the HUD")
    font = next((asset for path in ("/Engine/EngineFonts/RobotoDistanceField",
                                    "/Engine/EngineFonts/Roboto", "/Engine/EngineFonts/TinyFont")
                 if (asset := unreal.load_asset(path)) is not None), None)
    if font is None:
        raise RuntimeError("No Canvas font is available")
    bp, g = fresh('BP_BBHUD', unreal.HUD)
    g.var("Match", manager_class)
    g.compile()

    begin = g.event("ReceiveBeginPlay")
    find = g.call("/Script/Engine.GameplayStatics.GetActorOfClass", ActorClass=manager_class)
    store = g.set("Match", g.result(find))
    g.chain(begin, find, store)

    draw = g.event("ReceiveDrawHUD")
    match = g.get("Match")
    valid = g.call("/Script/Engine.KismetSystemLibrary.IsValid", Object=match)
    ready = g.branch(g.result(valid))
    g.exec(draw, ready)
    tail = g.output(ready, "then")

    def math(name, **values):
        return g.result(g.call(MATH + name, **values))

    def string(name, **values):
        return g.result(g.call(STR + name, **values))

    def state(name):
        return g.get(name, target=match, class_path=MANAGER)

    width = math("Conv_IntToDouble", InInt=g.output(draw, "SizeX"))
    height = math("Conv_IntToDouble", InInt=g.output(draw, "SizeY"))
    scale = math("FMin", A=math("Divide_DoubleDouble", A=width, B=1280),
                 B=math("Divide_DoubleDouble", A=height, B=720))
    half_w = math("Multiply_DoubleDouble", A=width, B=0.5)
    half_h = math("Multiply_DoubleDouble", A=height, B=0.5)
    # Canvas fonts have different baked point sizes. Normalize to a 20-pixel
    # reference height so the Roboto/TinyFont fallback preserves panel layout.
    font_probe = g.call(HUD + "GetTextSize", Text="M", Font=font, Scale=1.0)
    font_base = math("Divide_DoubleDouble", A=20,
                     B=math("FMax", A=g.output(font_probe, "OutHeight"), B=1))
    coordinates = {}

    def scaled(value):
        key = ("scale", value)
        if key not in coordinates:
            coordinates[key] = math("Multiply_DoubleDouble", A=scale, B=value)
        return coordinates[key]

    def position(value, axis="x", anchor="start"):
        key = (axis, anchor, value)
        if key not in coordinates:
            offset = scaled(value)
            if anchor == "start":
                coordinates[key] = offset
            else:
                basis = {("x", "center"): half_w, ("y", "center"): half_h,
                         ("x", "end"): width, ("y", "end"): height}[axis, anchor]
                coordinates[key] = math("Add_DoubleDouble", A=basis, B=offset)
        return coordinates[key]

    def queue(node):
        nonlocal tail
        g.exec(tail, node)
        tail = g.output(node, "then")
        return node

    def rect(x, y, w, h, color=INK, xa="start", ya="start"):
        queue(g.call(HUD + "DrawRect", RectColor=color,
                     ScreenX=position(x, "x", xa), ScreenY=position(y, "y", ya),
                     ScreenW=scaled(w), ScreenH=scaled(h)))

    def label(text, x, y, size=1.0, color=CREAM, xa="start", ya="start", center=False):
        screen_x = position(x, "x", xa)
        text_scale = math("Multiply_DoubleDouble", A=scaled(max(size, 0.65)), B=font_base)
        if center:
            measure = g.call(HUD + "GetTextSize", Text=text, Font=font, Scale=text_scale)
            screen_x = math("Subtract_DoubleDouble", A=screen_x,
                            B=math("Multiply_DoubleDouble", A=g.output(measure, "OutWidth"), B=0.5))
        queue(g.call(HUD + "DrawText", Text=text, TextColor=color,
                     ScreenX=screen_x, ScreenY=position(y, "y", ya),
                     Font=font, Scale=text_scale, bScalePosition=False))

    # Identity and the top score card leave most of the arena unobstructed.
    rect(24, 24, 246, 66)
    rect(24, 24, 3, 66, GOLD)
    label("BASKETBROOM", 42, 34, 1.1)
    label("TRAINING FLIGHT  /  OPEN CROWN", 43, 64, 0.47, MUTED)
    rect(-268, 24, 536, 88, xa="center")
    rect(-268, 24, 178, 3, TEAL, xa="center")
    rect(90, 24, 178, 3, COPPER, xa="center")
    rect(-88, 24, 176, 88, INK_LIGHT, xa="center")
    label("TEAL", -176, 34, 0.57, TEAL, xa="center", center=True)
    label("COPPER", 176, 34, 0.57, COPPER, xa="center", center=True)
    label(string("Conv_IntToString", InInt=state("TealScore")), -176, 56, 1.85,
          xa="center", center=True)
    label(string("Conv_IntToString", InInt=state("CopperScore")), 176, 56, 1.85,
          xa="center", center=True)
    seconds = math("Max", A=math("FCeil", A=state("SecondsLeft")), B=0)
    minutes = math("Divide_IntInt", A=seconds, B=60)
    remainder = math("Percent_IntInt", A=seconds, B=60)
    minute_string = string("Conv_IntToString", InInt=minutes)
    second_text = g.result(g.call(TEXT + "Conv_IntToText", Value=remainder,
                                  bUseGrouping=False, MinimumIntegralDigits=2, MaximumIntegralDigits=2))
    second_string = g.result(g.call(TEXT + "Conv_TextToString", InText=second_text))
    clock = string("Concat_StrStr", A=string("Concat_StrStr", A=minute_string, B=":"), B=second_string)
    label("FIVE MINUTE SCRIMMAGE", 0, 35, 0.45, MUTED, xa="center", center=True)
    label(clock, 0, 59, 1.4, xa="center", center=True)
    progress = math("FClamp", Value=math("Divide_DoubleDouble", A=state("SecondsLeft"), B=300), Min=0, Max=1)
    progress_w = math("Multiply_DoubleDouble", A=scaled(176), B=progress)
    queue(g.call(HUD + "DrawRect", RectColor=GOLD, ScreenX=position(-88, "x", "center"),
                 ScreenY=position(109, "y"), ScreenW=progress_w, ScreenH=scaled(3)))

    # A compact ball legend makes the asymmetric scoring readable at a glance.
    rect(-218, 132, 194, 135, xa="end")
    label("SCORING ROUTES", -204, 144, 0.52, MUTED, xa="end")
    label("QUAFFLE", -204, 169, 0.55, QUAFFLE, xa="end")
    label("13", -63, 168, 0.65, QUAFFLE, xa="end")
    label("QUARK", -204, 191, 0.55, QUARK, xa="end")
    label("37", -63, 190, 0.65, QUARK, xa="end")
    label("SNIPE", -204, 213, 0.55, SNIPE, xa="end")
    label("69", -63, 212, 0.65, SNIPE, xa="end")
    label("SNITCH", -204, 235, 0.55, GOLD, xa="end")
    label("150", -74, 234, 0.65, GOLD, xa="end")

    # Center reticle: corners avoid covering a small target ball.
    for x, y, w, h in ((-13, -1, 7, 2), (6, -1, 7, 2), (-1, -13, 2, 7), (-1, 6, 2, 7)):
        rect(x, y, w, h, "(R=0.96,G=0.94,B=0.86,A=0.82)", xa="center", ya="center")
    carry_text = math("SelectString", A="BALL SECURED  /  LMB TO THROW",
                      B="E TO CARRY  /  HOLD E TO CATCH", bPickA=state("HasBall"))
    carry_color = math("SelectColor", A=TEAL, B=MUTED, bPickA=state("HasBall"))
    label(carry_text, 0, 32, 0.49, carry_color, xa="center", ya="center", center=True)

    # The large message is brief in the manager and never covers the reticle.
    rect(-354, -162, 708, 42, xa="center", ya="end")
    rect(-354, -162, 3, 42, GOLD, xa="center", ya="end")
    label(state("Message"), 0, -151, 0.64, xa="center", ya="end", center=True)
    rect(-504, -98, 1008, 68, xa="center", ya="end")
    label("W A S D   FLIGHT       MOUSE   AIM       SPACE / CTRL   ALTITUDE", 0, -86,
          0.55, CREAM, xa="center", ya="end", center=True)
    label("E   CARRY / HOLD TO CATCH       LMB   THROW       R   RESTART", 0, -58,
          0.53, MUTED, xa="center", ya="end", center=True)

    # Conditional panels are last in the draw order.
    states = g.sequence(2)
    g.exec(tail, states)
    stunned = g.branch(math("Greater_DoubleDouble", A=state("Stun"), B=0))
    g.exec(states, stunned, out="then_0")
    tail = g.output(stunned, "then")
    rect(-151, -93, 302, 38, "(R=0.17,G=0.045,B=0.018,A=0.92)", xa="center", ya="center")
    label("BLUDGER HIT  /  RECOVERING", 0, -83, 0.55, COPPER,
          xa="center", ya="center", center=True)
    finished = g.branch(state("MatchOver"))
    g.exec(states, finished, out="then_1")
    tail = g.output(finished, "then")
    rect(-260, -138, 520, 243, "(R=0.012,G=0.024,B=0.034,A=0.97)", xa="center", ya="center")
    rect(-260, -138, 520, 4, GOLD, xa="center", ya="center")
    label("FLIGHT COMPLETE", 0, -106, 1.3, CREAM, xa="center", ya="center", center=True)
    teal_wins = math("Greater_IntInt", A=state("TealScore"), B=state("CopperScore"))
    tied = math("EqualEqual_IntInt", A=state("TealScore"), B=state("CopperScore"))
    winner = math("SelectString", A="TEAL TAKES THE ARENA", B="COPPER TAKES THE ARENA", bPickA=teal_wins)
    winner = math("SelectString", A="HONOURS EVEN", B=winner, bPickA=tied)
    label(winner, 0, -54, 0.72, GOLD, xa="center", ya="center", center=True)
    summary = string("Concat_StrStr", A=string("Conv_IntToString", InInt=state("TealScore")), B="   :   ")
    summary = string("Concat_StrStr", A=summary, B=string("Conv_IntToString", InInt=state("CopperScore")))
    label(summary, 0, -17, 1.45, CREAM, xa="center", ya="center", center=True)
    label("PRESS R TO FLY AGAIN", 0, 58, 0.6, MUTED, xa="center", ya="center", center=True)

    g.compile(save=True)
    g.export_manifest(Path(__file__).resolve().parents[1] / ".local" / "ue5" / "hud_manifest.json")
    return bp


if __name__ == '__main__':
    RESULT = build().get_path_name()
