"""Readable, code-drawn feature cards for the native gameplay showcase.

ASS vector shapes and text keep these overlays editable and resolution-native.
The controller insert is editorial information over the automated flight shot;
it does not relabel that shot as a physical-controller recording.
"""

COPY = {
    "WELCOME TO BASKETBROOM": ("WELCOME TO BASKETBROOM", "A playable Unreal Engine 5.8 prototype", "teal"),
    "OWN THE AIR": ("OWN THE AIR", "Six positions. Three dimensions.\nFind your place in the sky.", "teal"),
    "QUAFFLE  /  13 POINTS": ("QUAFFLE  /  13 POINTS", "Collect. Aim. Throw.\nThe whole ball must pass through a large hoop.", "gold"),
    "QUARK  /  37 POINTS": ("QUARK  /  37 POINTS", "Smaller hoop. Higher target.\nPrecision earns 37 points.", "purple"),
    "SNIPE  /  69 POINTS": ("SNIPE  /  69 POINTS", "Ranger: stay within 3.8 metres.\nHold catch for one continuous second.", "gold"),
    "THE HURLEYBACK": ("CHANGE YOUR POSITION", "Switch roles at an official stoppage.\nThe Hurleyback controls and releases Bludgers.", "teal"),
    "WANDWORK IN FLIGHT": ("WANDWORK IN FLIGHT", "Shield with Protego. Light up with Lumos.\nCast offensive spell adaptations.", "purple"),
    "MOVE THE OPPOSITION": ("PULL. PUSH. LIFT.", "Accio. Depulso. Levioso.\nReal spell effects move the opposing rider.", "purple"),
    "BB-0  /  APPLY THE HIT, THEN PENALIZE": ("HIT FIRST. THEN THE CALL.", "Stunning after a confirmed impediment?\nThat is a BB-0 double-tap foul.", "gold"),
    "NO CROWN": ("NO CROWN", "A scoring ball crossing the open crown\nbecomes dead and returns to play.", "gold"),
    "SNITCH  /  150 POINTS": ("SNITCH  /  150 POINTS", "Scout: secure the match-ending catch.\nPractice release: after 60 live seconds.", "gold"),
    "THE MATCH-ENDING CATCH": ("THE MATCH-ENDING CATCH", "Actual prototype gameplay.\nAutomated and staged for this showcase.", "teal"),
}

# ASS colors are BGR, not RGB.
ACCENTS = {"teal": "D5E85C", "gold": "7ACBFF", "purple": "FFC798"}
X, Y, WIDTH, HEIGHT = 96, 350, 1510, 304


def ass_time(seconds):
    value = max(0, round(float(seconds) * 100))
    return "%d:%02d:%02d.%02d" % (value // 360000, value // 6000 % 60, value % 6000 // 100, value % 100)


def text_escape(value):
    # Normalize editorial copy before adding ASS escapes; native HUD text is
    # already in the source video and never passes through this compositor.
    return editorial_text(value).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", r"\N")


def editorial_text(value):
    return str(value).lower()


def rounded_box(width, height, radius=18):
    # Cubic corners are native ASS vector paths, not bitmap backgrounds.
    r, w, h = radius, width, height
    return (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} "
            f"b {w} {h} {w} {h} {w-r} {h} l {r} {h} "
            f"b 0 {h} 0 {h} 0 {h-r} l 0 {r} b 0 0 0 0 {r} 0")


def make_captions(manifest, path, duration):
    shots = manifest.get("shots", manifest.get("timeline", []))
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 2160
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Segoe UI,84,&H00FFFFFF,&H00FFFFFF,&H001A140E,&H001A140E,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Body,Segoe UI,54,&H00F6EFE7,&H00FFFFFF,&H001A140E,&H001A140E,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Shape,Segoe UI,24,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, cards = [], []

    def event(start, end, style, value, tags="", layer=2):
        lines.append("Dialogue: %d,%s,%s,%s,,0,0,0,,{\\fad(180,220)%s}%s" %
                     (layer, ass_time(start), ass_time(end), style, tags, value))

    def shape(start, end, x, y, drawing, color, alpha="00", border=0, blur=0, layer=0):
        event(start, end, "Shape", drawing,
              r"\an7\pos(%d,%d)\p1\bord%d\blur%d\1c&H%s&\1a&H%s&" %
              (x, y, border, blur, color, alpha), layer)

    def text(start, end, value, x, y, style="Body", extra=""):
        event(start, end, style, text_escape(value), r"\pos(%d,%d)" % (x, y) + extra)

    def panel(start, end, accent, height, top=Y):
        shape(start, end, X + 8, top + 10, rounded_box(WIDTH, height), "000000", "88", blur=10)
        shape(start, end, X, top, rounded_box(WIDTH, height), "281C10", "12")
        shape(start, end, X, top + 16, f"m 0 0 l 10 0 10 {height-32} 0 {height-32}", accent, layer=1)
        shape(start, end, X + 25, top, "m 0 0 l 230 0 230 4 0 4", accent, layer=1)

    def controller_icon(start, end):
        left, top = X + 54, Y + 140
        outline = ("m 63 13 b 82 4 99 6 117 14 l 182 14 b 200 6 222 4 238 14 "
                   "b 258 29 276 83 287 119 b 300 168 277 190 250 164 l 215 129 "
                   "l 88 129 52 166 b 24 188 3 165 16 119 l 43 40 b 48 26 53 18 63 13")
        shape(start, end, left, top, outline, "F6EFE7", layer=2)
        # D-pad and four face buttons convey a generic gamepad, with no brand mark.
        shape(start, end, left + 65, top + 42,
              "m 15 0 l 35 0 35 16 50 16 50 35 35 35 35 51 15 51 15 35 0 35 0 16 15 16", "281C10", layer=3)
        circle = "m 10 0 b 23 0 23 20 10 20 b -3 20 -3 0 10 0"
        for dx, dy, color in ((211, 37, "D5E85C"), (188, 61, "281C10"), (234, 61, "281C10"), (211, 85, "281C10")):
            shape(start, end, left + dx, top + dy, circle, color, layer=3)

    for shot in shots:
        start = float(shot.get("start", shot.get("start_seconds", 0)))
        end = min(float(shot.get("end", shot.get("end_seconds", duration))), start + 6.0, duration)
        original = shot.get("title", shot.get("name", ""))
        if end <= start or not original:
            continue
        title, body, accent_name = COPY.get(original, (original, shot.get("caption", shot.get("subtitle", "")), "teal"))
        title, body = editorial_text(title), editorial_text(body)
        # These native central dialogs must remain fully visible throughout the card.
        top = 1260 if original in ("BB-0  /  APPLY THE HIT, THEN PENALIZE", "THE MATCH-ENDING CATCH") else Y
        panel(start, end, ACCENTS[accent_name], HEIGHT, top)
        text(start, end, title, X + 54, top + 25, "Title")
        text(start, end, body, X + 56, top + 139)
        cards.append({"start": start, "end": end, "title": title, "subtitle": body,
                      "accent": accent_name, "bounds": [X, top, WIDTH, HEIGHT], "source_shot_title": original})

    # Insert only where the director provides the matching uninterrupted flight shot.
    flight = any(s.get("title") == "OWN THE AIR" and
                 float(s.get("start_seconds", s.get("start", 0))) <= 19 and
                 float(s.get("end_seconds", s.get("end", 0))) >= 27 for s in shots)
    if flight and duration >= 27:
        for start, end, body in (
            (19.0, 23.0, "Sticks: fly + aim\nR1: cast   /   L1: shield"),
            (23.0, 27.0, "DualSense USB: Triangle works.\nMore USB + Bluetooth tests next."),
        ):
            body = editorial_text(body)
            panel(start, end, ACCENTS["teal"], 365)
            text(start, end, "controller support", X + 54, Y + 25, "Title")
            controller_icon(start, end)
            text(start, end, body, X + 400, Y + 145, extra=r"\fs54")
            text(start, end, "gamepad controls implemented", X + 400, Y + 283,
                 extra=r"\fs42\1c&H%s&" % ACCENTS["teal"])
            cards.append({"start": start, "end": end, "title": "controller support", "subtitle": body,
                          "footer": "gamepad controls implemented", "bounds": [X, Y, WIDTH, 365],
                          "editorial_insert": True, "footage": "Existing automated flight, not a physical-controller recording",
                          "hardware_evidence": "DualSense USB Triangle opens spellbook; remaining USB gameplay and Bluetooth tests pending"})
    if not cards:
        raise ValueError("Director manifest contains no shot captions")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return sorted(cards, key=lambda item: item["start"])
