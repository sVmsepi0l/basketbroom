"""PIE trail-picker acceptance through the real simulated gamepad input boundary.

Owns a fresh PIE session. Requires team-default color initially and resets that
preference before success. Saves a temporary custom color through ordinary menu
bindings, checks the actual INI, then verifies the local possession load hook.
This does not certify process restart, mouse dragging, physical hardware,
replication, emitted trail appearance or the visual readability of the picker.
On an interrupted/error run, use Flight Journal > Broom trail color > Triangle
to restore team default; the report explicitly records incomplete cleanup.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-trail-color-results.json'
CASES = (
    'options_and_dpad_open_color_picker_while_clock_frozen',
    'hue_input_changes_custom_trail_color',
    'saturation_input_changes_custom_trail_color',
    'brightness_input_changes_custom_trail_color',
    'idle_picker_edit_is_flushed_to_local_ini',
    'resume_keeps_selected_color_and_advances_clock',
    'local_repossession_restores_saved_custom_color',
    'triangle_restores_and_saves_dynamic_team_default',
)
spec = importlib.util.spec_from_file_location('_bb_trail_controller_base', ROOT/'Tools/test_native_controller.py')
ctrl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctrl)
unreal, prop = ctrl.unreal, ctrl.prop
receipt_spec = importlib.util.spec_from_file_location('_bb_trail_receipts', ROOT/'Tools/native_test_receipts.py')
receipts = importlib.util.module_from_spec(receipt_spec)
receipt_spec.loader.exec_module(receipts)
ctrl.REPORT = ctrl.base.REPORT = REPORT
ctrl.base.TEST_NAMES = CASES
ctrl.base.ARGS = {'max_wall_seconds':150, **globals().get('BRIDGE_ARGS', {})}


def rgb(color):
    return [float(color.r), float(color.g), float(color.b)]


def close(left, right, tolerance=2e-5):
    return len(left) == len(right) and all(abs(a-b) <= tolerance for a, b in zip(left, right))


def png_dimensions(path):
    """Accept a complete PNG only; dimensions alone do not certify its content."""
    try:
        data = path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 32:
            return None
        dimensions = struct.unpack('>II', data[16:24])
        offset = 8
        while offset + 12 <= len(data):
            length = struct.unpack('>I', data[offset:offset+4])[0]
            if offset + length + 12 > len(data):
                return None
            if data[offset+4:offset+8] == b'IEND':
                return dimensions if length == 0 else None
            offset += length + 12
    except OSError:
        pass
    return None


def read_trail_section(path):
    """Read this section only; Unreal INIs can have repeated keys elsewhere."""
    data = path.read_bytes()
    text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    values, inside = {}, False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            inside = line.casefold() == '[basketbroom.broomtrail]'
        elif inside and '=' in line and not line.startswith((';', '#')):
            key, value = line.split('=', 1)
            values[key.strip().casefold()] = value.strip()
    return values


class TrailColorTests(ctrl.NativeControllerTests):
    def __init__(self):
        self.changed_preference = False
        self.restored_team_default = False
        self.preview_capture = None
        super().__init__()

    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(
            scope='single-world PIE color picker via simulated gamepad events through real PlayerInput',
            hardware_claim=False,
            preview_capture=self.preview_capture,
            preference_cleanup='team default restored' if self.restored_team_default else
                'pending: reset in Flight Journal > Broom trail color > Triangle' if self.changed_preference else
                'no preference edit was attempted',
            not_covered=['physical DualSense, USB or Bluetooth transport', 'mouse drag and keyboard bindings',
                         'process restart or another machine', 'remote replication and network ownership',
                         'visual readability, actual emitted trails and performance'],
            fixture_policy='Own fresh PIE; inherited scaffold isolates disposable CPU riders. '
                'Menu edits use simulated gamepad input. Repossession check deliberately resets only '
                'the in-memory cosmetic field via its public setter before cycling local possession. '
                'No score, clock, material, menu-selection or preference-file writes from Python.')
        receipts.write_json_atomic(REPORT, data)

    def color(self):
        return rgb(self.pawn.get_broom_trail_color())

    def saved(self):
        section = read_trail_section(self.ini)
        return {'custom': section.get('custom', '').casefold() in ('true', '1'),
                'rgb': [float(section[key]) for key in ('red', 'green', 'blue')]}

    def open_picker(self):
        yield from self.tap('Gamepad_Special_Right', lambda: bool(prop(self.pawn, 'bPauseMenuOpen')))
        self.require(int(prop(self.pawn, 'PauseMenuPage')) == 0, 'Options must open journal main page')
        # The picker is the last main-menu entry: normal wrapping selects it.
        yield from self.tap('Gamepad_DPad_Up')
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: int(prop(self.pawn, 'PauseMenuPage')) == 5)
        self.require(int(prop(self.pawn, 'PauseMenuPage')) == 5, 'Real menu input must reach trail picker')

    def capture_picker_preview(self):
        # A unique engine output prevents a previous image from satisfying the
        # observation. Publish the stable preview name only after completion.
        pending = ROOT/'.local'/('native-trail-picker-preview-'+uuid.uuid4().hex+'.png')
        final = ROOT/'.local/native-trail-picker-preview.png'
        view = self.controller.get_view_target()
        self.require(view is not None and view.get_path_name().startswith(self.world.get_path_name()+':'),
                     'Capture view must belong to the owned PIE world')
        hud = self.controller.get_hud()
        self.require(hud is not None and bool(prop(hud, 'bShowHUD')), 'Picker capture requires its visible HUD')
        command = 'Shot showui filename='+pending.as_posix()+' -nosuffix'
        unreal.SystemLibrary.execute_console_command(self.world, command, self.controller)
        yield self.wait_until(lambda: png_dimensions(pending) is not None, timeout=15)
        dimensions = png_dimensions(pending)
        if dimensions:
            pending.replace(final)
        self.preview_capture = {
            'file': str(final) if dimensions else None,
            'dimensions': list(dimensions) if dimensions else None,
            'bytes': final.stat().st_size if dimensions else None,
            'world': self.world.get_path_name(), 'view_target': view.get_path_name(),
            'command': command, 'hud_visible': True,
            'status': 'rendered_pending_visual_review' if dimensions else 'capture_not_observed',
            'visual_review': 'pending' if dimensions else 'not_rendered',
        }
        self.write_report('running')

    def scenarios(self):
        yield self.wait(max(3, min(60, float(ctrl.base.ARGS.get('focus_grace_seconds', 10)))))
        self.require(not prop(self.pawn, 'bUseCustomBroomTrailColor'),
                     'Preserve an existing custom color; this bounded test only starts from team default')
        self.require(callable(getattr(self.pawn, 'set_broom_trail_color', None)), 'Current trail API is required')
        self.require(self.controller.is_actor_tick_enabled(), 'Real PlayerInput ticks must remain enabled')
        self.ini = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'Config/WindowsEditor/GameUserSettings.ini'
        self.require(self.ini.is_file(), 'Expected editor GameUserSettings INI must already exist')
        initial = read_trail_section(self.ini)
        self.require(initial.get('custom', '').casefold() not in ('true', '1'), 'Saved preference must also use team default')
        self.provenance.update(config_file=str(self.ini), initial_section=initial, original_color=self.color(),
                               input_boundary='FInputKeyEventArgs::CreateSimulated -> PlayerController::InputKey -> PlayerInput',
                               process_restart_claim=False)
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.match, 'bLive')))
        self.require(prop(self.match, 'bLive'), 'Cross must start the actual match')
        yield from self.open_picker()
        frozen = float(prop(self.match, 'LiveSeconds'))
        if ctrl.base.ARGS.get('capture_preview', False):
            yield from self.capture_picker_preview()
        visual_hold = max(0, min(30, float(ctrl.base.ARGS.get('visual_hold_seconds', 0))))
        if visual_hold:
            self.provenance['visual_hold_seconds'] = visual_hold
            self.event('picker_visual_hold', seconds=visual_hold)
            self.write_report('running')
            yield self.wait(visual_hold)
        yield self.wait(.3)
        self.record(CASES[0], unreal.GameplayStatics.is_game_paused(self.world)
                    and float(prop(self.match, 'LiveSeconds')) == frozen, page=int(prop(self.pawn, 'PauseMenuPage')))
        before = self.color()
        # An interruption during the first tap may occur after its save. Mark
        # cleanup pending before sending any editing input, conservatively.
        self.changed_preference = True
        for _ in range(8):
            yield from self.tap('Gamepad_DPad_Right')
        custom_mode = bool(prop(self.pawn, 'bUseCustomBroomTrailColor'))
        self.record(CASES[1], custom_mode and not close(before, self.color()), before=before, after=self.color())
        self.require(custom_mode, 'Hue input must enter custom mode')
        yield from self.tap('Gamepad_DPad_Down')
        before = self.color()
        for _ in range(5):
            yield from self.tap('Gamepad_DPad_Left')
        self.record(CASES[2], int(prop(self.pawn, 'PauseMenuSelection')) == 1 and not close(before, self.color()),
                    before=before, after=self.color())
        yield from self.tap('Gamepad_DPad_Down')
        before = self.color()
        # Both team defaults start at maximum HSV brightness. Reduce it so
        # this observes a real edit instead of clamping at the upper bound.
        for _ in range(4):
            yield from self.tap('Gamepad_DPad_Left')
        self.record(CASES[3], int(prop(self.pawn, 'PauseMenuSelection')) == 2 and not close(before, self.color()),
                    before=before, after=self.color())
        yield self.wait(.8)
        expected = self.color()
        disk = self.saved()
        self.record(CASES[4], disk['custom'] and close(disk['rgb'], expected)
                    and unreal.GameplayStatics.is_game_paused(self.world), saved=disk, observed=expected)
        self.require(disk['custom'] and close(disk['rgb'], expected), 'Idle save must be on disk before close')
        yield from self.tap('Gamepad_FaceButton_Right', lambda: int(prop(self.pawn, 'PauseMenuPage')) == 0)
        yield from self.tap('Gamepad_Special_Right', lambda: not prop(self.pawn, 'bPauseMenuOpen'))
        yield self.wait(.3)
        self.record(CASES[5], not unreal.GameplayStatics.is_game_paused(self.world)
                    and prop(self.match, 'bLive') and float(prop(self.match, 'LiveSeconds')) > frozen
                    and close(self.color(), expected), after=self.color())

        # Fixture changes RAM only. A successful load must recover the previously
        # observed custom value rather than merely retain it across possession.
        self.pawn.set_broom_trail_color(False, unreal.LinearColor(1, 1, 1, 1))
        self.require(not prop(self.pawn, 'bUseCustomBroomTrailColor'), 'Memory-only fixture reset must take effect')
        self.controller.un_possess()
        self.require(self.pawn.get_controller() is None, 'UnPossess must detach the local controller')
        # Repossess within the same callback: no unpossessed Tick may reset the
        # preference cache on our behalf. The lifecycle hook must handle it.
        self.controller.possess(self.pawn)
        yield self.wait_until(lambda: bool(prop(self.pawn, 'bUseCustomBroomTrailColor')) and close(self.color(), expected))
        self.record(CASES[6], prop(self.pawn, 'bUseCustomBroomTrailColor') and close(self.color(), expected),
                    expected=expected, restored=self.color(),
                    scope='same-process immediate repossession reload plus preceding disk observation')

        yield from self.open_picker()
        yield from self.tap('Gamepad_FaceButton_Top', lambda: not prop(self.pawn, 'bUseCustomBroomTrailColor'))
        yield self.wait(.2)
        disk = self.saved()
        self.restored_team_default = not prop(self.pawn, 'bUseCustomBroomTrailColor') and not disk['custom']
        self.record(CASES[7], self.restored_team_default and close(self.color(), self.provenance['original_color']),
                    saved=disk, color=self.color())
        yield from self.tap('Gamepad_Special_Right', lambda: not prop(self.pawn, 'bPauseMenuOpen'))


def main():
    if unreal is None:
        return {'status':'not_run', 'planned_tests':CASES, 'hardware_claim':False,
                'instruction':'Run through editor bridge with a fresh stopped UE5.8 arena and focus its PIE viewport.'}
    runner = TrailColorTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish('error', traceback.format_exc())
        started = False
    if started:
        unreal._basketbroom_native_test = runner
    return {'status':'started' if started else runner.final_status, 'report':str(REPORT), 'planned_cases':len(CASES)}


if __name__ == '__main__':
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))
