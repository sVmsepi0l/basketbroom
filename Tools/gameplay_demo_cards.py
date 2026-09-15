"""readable, code-drawn feature cards for the native gameplay showcase.

ass vector shapes and text keep these overlays editable and resolution-native.
the controller insert is editorial information over the automated flight shot;
it does not relabel that shot as a physical-controller recording.
"""

copy = {
    "welcome to BASKETBROOM": ("welcome to basketbroom", "a playable unreal engine 5.8 prototype", "teal"),
    "own the AIR": ("own the air", "six positions. three dimensions.\nFind your place in the sky.", "teal"),
    "quaffle  /  13 POINTS": ("quaffle  /  13 points", "Collect. Aim. Throw.\nThe whole ball must pass through a large hoop.", "gold"),
    "quark  /  37 POINTS": ("quark  /  37 points", "smaller hoop. higher target.\nPrecision earns 37 points.", "purple"),
    "snipe  /  69 POINTS": ("snipe  /  69 points", "Ranger: stay within 3.8 metres.\nHold catch for one continuous second.", "gold"),
    "the HURLEYBACK": ("change your position", "switch roles at an official stoppage.\nThe hurleyback controls and releases Bludgers.", "teal"),
    "wandwork in FLIGHT": ("wandwork in flight", "shield with Protego. light up with Lumos.\nCast offensive spell adaptations.", "purple"),
    "move the OPPOSITION": ("PULL. PUSH. LIFT.", "Accio. Depulso. Levioso.\nReal spell effects move the opposing rider.", "purple"),
    "bb-0  /  apply the hit, then PENALIZE": ("hit FIRST. then the CALL.", "stunning after a confirmed impediment?\nThat is a bb-0 double-tap foul.", "gold"),
    "no CROWN": ("no crown", "a scoring ball crossing the open crown\nbecomes dead and returns to play.", "gold"),
    "snitch  /  150 POINTS": ("snitch  /  150 points", "Scout: secure the match-ending catch.\nPractice release: after 60 live seconds.", "gold"),
    "the match-ending CATCH": ("the match-ending catch", "actual prototype gameplay.\nAutomated and staged for this showcase.", "teal"),
}

# opt-in role chapters belong to an observed six-position take. keep the
# original director shot keys intact so older captures retain their card plan.
position_copy = {
    "the NETMINDER": (0, "netminder · 1 per team", "teal", (
        "guard four hoops. collect a quaffle or quark.\nclear the danger and start the counterattack.",
        "your team conceded? take the protected restart.\nkeep play moving with a pass, carry or shot.",
    )),
    "the CHASER": (1, "chaser · 2 per team", "gold", (
        "find a lane. carry, pass and shoot.\nplay the quaffle or either quark.",
        "one scoring ball at a time.\nquaffle: 13 points. quark: 37 points.",
    )),
    "the TRAPPER": (2, "trapper · 1 per team", "purple", (
        "read the lanes. intercept a free scoring ball.\nturn the turnover into a counterattack.",
        "carry, pass or shoot after the interception.\ndefensive duty gives no extra license to foul.",
    )),
    "snipe  /  69 POINTS": (3, "ranger · 1 per team", "gold", (
        "score, cover or chase: switch with the game.\nplay scoring balls and pursue both winged targets.",
        "release your scoring ball before a chase catch.\nsecure the snipe for 69 points; keep moving.",
    )),
    "the HURLEYBACK": (4, "hurleyback · 2 per team", "teal", (
        "use your hurley to control one bludger.\nprotect teammates and disrupt incoming attacks.",
        "keep it moving: release before three seconds.\nteam control across passes: six seconds maximum.",
    )),
    "snitch  /  150 POINTS": (5, "scout · 1 per team", "gold", (
        "hunt the snipe and snitch. stay within 3.8m.\nhold catch for one uninterrupted second.",
        "snitch: 150 in regulation; 300 in overtime.\nthe catch triggers final review; scores decide.",
    )),
}

# ass colors are bgr, not RGB.
accents = {"teal": "d5e85c", "gold": "7acbff", "purple": "ffc798"}
x, y, width, height = 96, 350, 1510, 304


def ass_time(seconds):
    value = max(0, round(float(seconds) * 100))
    return "%d:%02d:%02d.%02d" % (value // 360000, value // 6000 % 60, value % 6000 // 100, value % 100)


def text_escape(value):
    # normalize editorial copy before adding ass escapes; native hud text is
    # already in the source video and never passes through this compositor.
    return editorial_text(value).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", r"\N")


def editorial_text(value):
    return str(value).lower()


def rounded_box(width, height, radius=18):
    # cubic corners are native ass vector paths, not bitmap backgrounds.
    r, w, h = radius, width, height
    return (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} "
            f"b {w} {h} {w} {h} {w-r} {h} l {r} {h} "
            f"b 0 {h} 0 {h} 0 {h-r} l 0 {r} b 0 0 0 0 {r} 0")


def make_captions(manifest, path, duration):
    shots = manifest.get("shots", manifest.get("timeline", []))
    position_showcase = manifest.get("showcase_positions") is true
    if position_showcase and not all(any(shot.get("title") == key for shot in shots) for key in POSITION_COPY):
        raise valueerror("position showcase requires all six observed role chapters")
    header = """[script info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 2160
WrapStyle: 2
ScaledBorderAndShadow: yes

[v4+ styles]
Format: name, fontname, fontsize, primarycolour, secondarycolour, outlinecolour, backcolour, bold, italic, underline, strikeout, scalex, scaley, spacing, angle, borderstyle, outline, shadow, alignment, marginl, marginr, marginv, encoding
Style: title,segoe ui,84,&h00ffffff,&h00ffffff,&h001a140e,&h001a140e,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: body,segoe ui,54,&h00f6efe7,&h00ffffff,&h001a140e,&h001a140e,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: shape,segoe ui,24,&h00ffffff,&h00ffffff,&h00ffffff,&h00ffffff,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[events]
Format: layer, start, end, style, name, marginl, marginr, marginv, effect, text
"""
    lines, cards = [], []

    def event(start, end, style, value, tags="", layer=2):
        lines.append("Dialogue: %d,%s,%s,%s,,0,0,0,,{\\fad(180,220)%s}%s" %
                     (layer, ass_time(start), ass_time(end), style, tags, value))

    def shape(start, end, x, y, drawing, color, alpha="00", border=0, blur=0, layer=0):
        event(start, end, "shape", drawing,
              r"\an7\pos(%d,%d)\p1\bord%d\blur%d\1c&H%s&\1a&H%s&" %
              (x, y, border, blur, color, alpha), layer)

    def text(start, end, value, x, y, style="body", extra=""):
        event(start, end, style, text_escape(value), r"\pos(%d,%d)" % (x, y) + extra)

    def panel(start, end, accent, height, top=Y):
        shape(start, end, x + 8, top + 10, rounded_box(width, height), "000000", "88", blur=10)
        shape(start, end, x, top, rounded_box(width, height), "281c10", "12")
        shape(start, end, x, top + 16, f"m 0 0 l 10 0 10 {height-32} 0 {height-32}", accent, layer=1)
        shape(start, end, x + 25, top, "m 0 0 l 230 0 230 4 0 4", accent, layer=1)

    def controller_icon(start, end):
        left, top = x + 54, y + 140
        outline = ("m 63 13 b 82 4 99 6 117 14 l 182 14 b 200 6 222 4 238 14 "
                   "b 258 29 276 83 287 119 b 300 168 277 190 250 164 l 215 129 "
                   "l 88 129 52 166 b 24 188 3 165 16 119 l 43 40 b 48 26 53 18 63 13")
        shape(start, end, left, top, outline, "f6efe7", layer=2)
        # d-pad and four face buttons convey a generic gamepad, with no brand mark.
        shape(start, end, left + 65, top + 42,
              "m 15 0 l 35 0 35 16 50 16 50 35 35 35 35 51 15 51 15 35 0 35 0 16 15 16", "281c10", layer=3)
        circle = "m 10 0 b 23 0 23 20 10 20 b -3 20 -3 0 10 0"
        for dx, dy, color in ((211, 37, "d5e85c"), (188, 61, "281c10"), (234, 61, "281c10"), (211, 85, "281C10")):
            shape(start, end, left + dx, top + dy, circle, color, layer=3)

    for shot in shots:
        start = float(shot.get("start", shot.get("start_seconds", 0)))
        end = min(float(shot.get("end", shot.get("end_seconds", duration))), start + 6.0, duration)
        original = shot.get("title", shot.get("name", ""))
        if end <= start or not original:
            continue
        if position_showcase and original in POSITION_COPY:
            role, title, accent_name, phases = position_copy[original]
            shot_end = min(float(shot.get("end", shot.get("end_seconds", duration))), duration)
            if shot_end - start < 14 - .001:
                raise valueerror("each position chapter needs at least fourteen seconds")
            for phase, body in enumerate(phases):
                phase_start, phase_end = start + phase * 7, start + (phase + 1) * 7
                panel(phase_start, phase_end, accents[accent_name], height)
                text(phase_start, phase_end, title, x + 54, y + 25, "title")
                text(phase_start, phase_end, body, x + 56, y + 139)
                cards.append({"start": phase_start, "end": phase_end, "title": title, "subtitle": body,
                              "accent": accent_name, "bounds": [x, y, width, height],
                              "source_shot_title": original, "position_role": role, "position_phase": phase + 1})
            continue
        title, body, accent_name = COPY.get(original, (original, shot.get("caption", shot.get("subtitle", "")), "teal"))
        title, body = editorial_text(title), editorial_text(body)
        # these native central dialogs must remain fully visible throughout the card.
        top = 1260 if original in ("bb-0  /  apply the hit, then penalize", "the match-ending catch") else y
        panel(start, end, accents[accent_name], height, top)
        text(start, end, title, x + 54, top + 25, "title")
        text(start, end, body, x + 56, top + 139)
        cards.append({"start": start, "end": end, "title": title, "subtitle": body,
                      "accent": accent_name, "bounds": [x, top, width, height], "source_shot_title": original})

    # insert only where the director provides the matching uninterrupted flight shot.
    flight = any(s.get("title") == "own the air" and
                 float(s.get("start_seconds", s.get("start", 0))) <= 19 and
                 float(s.get("end_seconds", s.get("end", 0))) >= 27 for s in shots)
    if flight and duration >= 27:
        for start, end, body in (
            (19.0, 23.0, "Sticks: fly + aim\nR1: cast   /   L1: shield"),
            (23.0, 27.0, "dualsense USB: triangle works.\nMore usb + bluetooth tests next."),
        ):
            body = editorial_text(body)
            panel(start, end, accents["teal"], 365)
            text(start, end, "controller support", x + 54, y + 25, "title")
            controller_icon(start, end)
            text(start, end, body, x + 400, y + 145, extra=r"\fs54")
            text(start, end, "gamepad controls implemented", x + 400, y + 283,
                 extra=r"\fs42\1c&H%s&" % accents["teal"])
            cards.append({"start": start, "end": end, "title": "controller support", "subtitle": body,
                          "footer": "gamepad controls implemented", "bounds": [x, y, width, 365],
                          "editorial_insert": true, "footage": "existing automated flight, not a physical-controller recording",
                          "hardware_evidence": "dualsense usb triangle opens spellbook; remaining usb gameplay and bluetooth tests pending"})
    if not cards:
        raise valueerror("director manifest contains no shot captions")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return sorted(cards, key=lambda item: item["start"])
