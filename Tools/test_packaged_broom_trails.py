"""Bounded, unattended Development-package trail/picker smoke.

Default invocation only prints a plan. --run starts one owned process (offscreen
unless --visible is supplied),
injects keys using UE5.8's existing Input.+key/Input.-key console commands, reads
GETALL output, captures the real picker HUD, and checks its isolated saved INI.
No PIE-only bridge, Python runtime plugin, OS input or new game API is used.

Engine source contracts used: EnhancedInputModule.cpp registers Input.+/-key;
EnhancedInputSubsystemInterface.cpp routes forced keys through InputKey;
UnrealEngine.cpp DEFER queues the next frame; LocalPlayer.cpp EXEC runs a macro;
Obj.cpp GETALL exports reflected properties. Paths.cpp supports -UserDir, and
ConfigCacheIni.cpp supports -GameUserSettingsINI. EXEC unusually prepends a
relative Binaries directory unless its argument contains 'Binaries', hence the
private Binaries macro directory below. Digital keys span one deferred frame:
EnhancedInput queues one Pressed event after world actors tick, then removal
queues Released. UPlayerInput::FlushPressedKeys preserves EventAccumulator, so
the next PlayerInput tick consumes both edges once. Two frames repeat Pressed.

Scope excludes earned boosts, remote replication, physical controllers and
packaged trail pixels: the local first-person view deliberately hides its own
trail. Native component visibility is observed; appearance is checked by the
separate PIE visual suite. Picker PNGs can be inspected by the agent; no user
interaction or manual check is required to execute this driver.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    'native_roster_and_safe_tracer_components_loaded',
    'simulated_cross_starts_packaged_match',
    'simulated_left_stick_moves_owner_and_emits_three_tracers',
    'neutral_input_stops_owner_and_tracers_expire',
    'options_opens_real_pause_menu_and_freezes_clock',
    'dpad_and_cross_open_real_trail_picker',
    'hue_input_changes_custom_color_without_identity_or_energy_mutation',
    'picker_hud_png_written',
    'custom_color_saved_to_isolated_game_user_settings',
    'options_resumes_live_clock',
    'baseline_hud_png_written',
)
ARENA_MAPS = {'Classic':'/Basketbroom/Maps/BB_Regulation',
              'Redrock':'/Basketbroom/Maps/BB_Redrock', 'Redwoods':'/Basketbroom/Maps/BB_Redwoods'}
STAGE_RIDER_PROPS = {
    'lobby':('Controller', 'TeamIndex', 'bUseCustomBroomTrailColor'),
    'paused':('bPauseMenuOpen', 'PauseMenuPage', 'PauseMenuSelection'),
    'picker':('bPauseMenuOpen', 'PauseMenuPage', 'PauseMenuSelection', 'TeamIndex', 'Position', 'RosterIndex', 'FlightBoostCharge'),
    'custom':('bUseCustomBroomTrailColor', 'CustomBroomTrailColor', 'TeamIndex', 'Position', 'RosterIndex', 'FlightBoostCharge'),
    'resumed':('bPauseMenuOpen',),
}
STAGE_MATCH_PROPS = {
    'lobby':('bLive',), 'live':('bLive',), 'paused':('LiveSeconds',), 'paused_stable':('LiveSeconds',),
    'picker':('TealScore', 'CopperScore', 'LiveSeconds'), 'custom':('TealScore', 'CopperScore', 'LiveSeconds'),
    'resumed':('bLive', 'LiveSeconds'),
}
TRACER_PROPS = ('bVisible', 'bGenerateOverlapEvents', 'CastShadow', 'bCanEverAffectNavigation',
                'bOwnerNoSee', 'bOnlyOwnerSee', 'bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')
ERRORS = re.compile(r'^.*(?:Fatal error:|Assertion failed:|Ensure condition failed:|'
                    r'Log[^:\r\n]+:\s*(?:Error|Fatal):|Command not recognized:|'
                    r"Can.t find file '|Failed to locate a key named).*$", re.MULTILINE)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def png_size(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 32 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return None
    size, offset = struct.unpack('>II', data[16:24]), 8
    while offset+12 <= len(data):
        count = struct.unpack('>I', data[offset:offset+4])[0]
        if offset+count+12 > len(data):
            return None
        if data[offset+4:offset+8] == b'IEND':
            return size if count == 0 else None
        offset += count+12
    return None


def plan(directory):
    """Return a deterministic frame sequence; no file writes or game calls."""
    steps = []

    def step(label, commands=(), wait=1):
        steps.append({'label':label, 'commands':list(commands), 'wait_frames':wait})

    def snapshot(label, wait=1, screenshot=False):
        commands = ['GETALL BBRiderCharacter '+name for name in STAGE_RIDER_PROPS.get(label, ())]
        commands += ['GETALL BBMatchState '+name for name in STAGE_MATCH_PROPS.get(label, ())]
        # Obj.cpp GETALL supports NAME=<exact FName>. Query the 48 tracers,
        # excluding the ~176 unrelated shield/hurley components. Static safety
        # flags need only one lobby observation; later stages read changed state.
        properties = TRACER_PROPS if label == 'lobby' else ('bVisible',) if label in ('moving', 'stopped') else ()
        commands += ['GETALL InstancedStaticMeshComponent '+name+' NAME=BroomTracer'+str(strand)
                     for name in properties for strand in range(3)]
        if label in ('moving', 'stopped'):
            commands += ['GETALL CharacterMovementComponent Velocity']
        if screenshot:
            commands.append('Shot filename='+str(directory/(screenshot+'.png')).replace('\\', '/')+' -nosuffix')
        step(label, commands, wait)

    def tap(label, key):
        # UGameEngine ticks the null-world EnhancedInput module after actors;
        # LaunchEngineLoop ticks deferred commands after GEngine->Tick. Remove
        # after one injection: FlushPressedKeys leaves EventAccumulator intact.
        # A second forced Pressed survives that flush and toggles Options twice.
        step(label+'_press', ['Input.+key '+key+' 1'], 1)
        step(label+'_release', ['Input.-key '+key], 5)

    step('warmup', ['t.MaxFPS 60'], 180)
    snapshot('lobby', wait=35, screenshot='baseline-hud')
    tap('kickoff', 'Gamepad_FaceButton_Bottom')
    snapshot('live', wait=5)
    step('move', ['Input.+key Gamepad_LeftY 1'], 35)
    snapshot('moving')
    step('stop', ['Input.-key Gamepad_LeftY'], 100)
    snapshot('stopped')
    tap('pause', 'Gamepad_Special_Right')
    snapshot('paused', wait=40)
    snapshot('paused_stable')
    tap('select_picker', 'Gamepad_DPad_Up')
    tap('open_picker', 'Gamepad_FaceButton_Bottom')
    snapshot('picker')
    for index in range(8):
        tap('hue_%02d' % index, 'Gamepad_DPad_Right')
    step('wait_for_preference_flush', wait=70)
    snapshot('custom', wait=40, screenshot='picker')
    tap('resume', 'Gamepad_Special_Right')
    step('wait_for_resumed_clock', wait=45)
    snapshot('resumed', wait=20)
    step('done', ['QUIT'])
    for index, entry in enumerate(steps):
        entry['file'] = str(directory/'Binaries'/('%03d_%s.txt' % (index, entry['label'])))
    for index, entry in enumerate(steps[:-1]):
        entry['commands'].append('DEFER '*entry['wait_frames']+'EXEC "'+steps[index+1]['file'].replace('\\', '/')+'"')
    return steps


def read_states(log_text, steps):
    labels = {Path(row['file']).name:row['label'] for row in steps}
    # FName casing is process-dependent: the packaged log exports `.position`
    # even though the native reflected declaration and query use `Position`.
    properties = {name.casefold():name for groups in (STAGE_RIDER_PROPS, STAGE_MATCH_PROPS)
                  for names in groups.values() for name in names}
    properties.update({name.casefold():name for name in (*TRACER_PROPS, 'Velocity')})
    states, current = {}, None
    for line in log_text.splitlines():
        marker = re.search(r'LogPlayerManagement:\s*(?:Log:\s*)?Execing (.+)$', line)
        if marker:
            current = labels.get(Path(marker[1].strip()).name)
            if current:
                states.setdefault(current, {})
        entry = re.search(r'\b\d+\) (\S+) (.+)\.(\w+) = (.*)$', line)
        if current and entry:
            name = properties.get(entry[3].casefold(), entry[3])
            states[current].setdefault(name, {})[entry[2]] = entry[4].strip()
    return states


def truth(value):
    return str(value).casefold() == 'true'


def numbers(value, names):
    matches = dict(re.findall(r'([XYZRGBA])\s*=\s*([-+\deE.]+)', str(value)))
    result = [float(matches[name]) for name in names]
    if not all(math.isfinite(number) for number in result):
        raise ValueError('Nonfinite observed value')
    return result


def saved_color(path):
    data = path.read_bytes()
    text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    values, inside = {}, False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('['):
            inside = line.casefold() == '[basketbroom.broomtrail]'
        elif inside and '=' in line and not line.startswith((';', '#')):
            key, value = line.split('=', 1)
            values[key.casefold()] = value.strip()
    return {'custom':truth(values.get('custom')), 'rgb':[float(values[key]) for key in ('red', 'green', 'blue')]}


def evaluate(log_text, steps, screenshot, ini, baseline):
    states = read_states(log_text, steps)
    tests, errors = [], {}
    owners = [actor for actor, controller in states.get('lobby', {}).get('Controller', {}).items()
              if 'PlayerController' in controller]
    owner = owners[0] if len(owners) == 1 else None

    def value(stage, name):
        if owner is None:
            raise ValueError('Exactly one native rider must have the local PlayerController: '+repr(owners))
        return states[stage][name][owner]

    def match_value(stage, name):
        values = list(states[stage][name].values())
        if len(values) != 1:
            raise ValueError('Expected exactly one BBMatchState '+name)
        return values[0]

    def owned_parts(stage, name):
        if owner is None:
            raise ValueError('Cannot identify the owned rider')
        return {path:raw for path, raw in states[stage][name].items()
                if path.startswith(owner+'.') and re.search(r'\.BroomTracer[012]$', path)}

    def speed(stage):
        if owner is None:
            raise ValueError('Cannot identify the owned rider')
        velocities = [numbers(raw, 'XYZ') for path, raw in states[stage]['Velocity'].items() if path.startswith(owner+'.')]
        if len(velocities) != 1:
            raise ValueError('Expected exactly one owned CharacterMovement velocity')
        return sum(number*number for number in velocities[0])**.5

    def check(index, observe):
        # Missing persistence or one malformed observation must not hide later
        # independent screenshot/clock checks. Every planned case gets a result.
        try:
            condition, detail = observe()
            tests.append({'name':CASES[index], 'status':'passed' if condition else 'failed', 'detail':detail})
        except (KeyError, ValueError, OSError) as error:
            errors[CASES[index]] = str(error)
            tests.append({'name':CASES[index], 'status':'failed', 'detail':{'observation_error':str(error)}})

    def roster():
        lobby = states['lobby']
        tracer_paths = {path for path in lobby['bVisible'] if re.search(r'\.BroomTracer[012]$', path)}
        expected_flags = {'bGenerateOverlapEvents':False, 'CastShadow':False, 'bCanEverAffectNavigation':False,
                          'bOwnerNoSee':True, 'bOnlyOwnerSee':False,
                          'bAbsoluteLocation':True, 'bAbsoluteRotation':True, 'bAbsoluteScale':True}
        flags_valid = all(path in lobby[name] and truth(lobby[name][path]) == expected
                          for path in tracer_paths for name, expected in expected_flags.items())
        valid = (len(lobby['Controller']) == 16 and len(tracer_paths) == 48 and flags_valid
                 and value('lobby', 'TeamIndex') == '0' and not truth(value('lobby', 'bUseCustomBroomTrailColor')))
        return valid, dict(rider_count=len(lobby['Controller']), tracer_components=len(tracer_paths), flags_valid=flags_valid)

    def movement(stage):
        parts, velocity = owned_parts(stage, 'bVisible'), speed(stage)
        valid = (velocity > 80 and all(map(truth, parts.values()))) if stage == 'moving' else (velocity < 5 and not any(map(truth, parts.values())))
        return len(parts) == 3 and valid, dict(speed_cm_s=velocity, component_visibility=parts)

    def pause():
        clock = float(match_value('paused', 'LiveSeconds'))
        later = float(match_value('paused_stable', 'LiveSeconds'))
        opened, page = truth(value('paused', 'bPauseMenuOpen')), value('paused', 'PauseMenuPage')
        return opened and page == '0' and later == clock, dict(menu_open=opened, page=page, live_seconds=clock, later_live_seconds=later)

    def picker():
        opened, page = truth(value('picker', 'bPauseMenuOpen')), value('picker', 'PauseMenuPage')
        return opened and page == '5', dict(menu_open=opened, page=page)

    def color():
        custom = numbers(value('custom', 'CustomBroomTrailColor'), 'RGB')
        identity = all(value('picker', name) == value('custom', name)
                       for name in ('TeamIndex', 'Position', 'RosterIndex', 'FlightBoostCharge'))
        identity = identity and all(match_value('picker', name) == match_value('custom', name)
                                    for name in ('TealScore', 'CopperScore', 'LiveSeconds'))
        valid = (truth(value('custom', 'bUseCustomBroomTrailColor')) and identity
                 and any(abs(a-b) > 1e-4 for a, b in zip(custom, [.075, 1, .61])))
        return valid, dict(color=custom, identity_unchanged=identity)

    def capture(path):
        dimensions = png_size(path)
        return (dimensions is not None and dimensions[0] >= 640 and dimensions[1] >= 360,
                dict(file=str(path), dimensions=dimensions, visual_review='agent review pending'))

    def persistence():
        saved = saved_color(ini)
        custom = numbers(value('custom', 'CustomBroomTrailColor'), 'RGB')
        return saved['custom'] and max(abs(a-b) for a, b in zip(saved['rgb'], custom)) < 2e-5, dict(ini=str(ini), saved=saved)

    def resumed():
        valid = (truth(value('paused', 'bPauseMenuOpen')) and not truth(value('resumed', 'bPauseMenuOpen'))
                 and truth(match_value('resumed', 'bLive'))
                 and float(match_value('resumed', 'LiveSeconds')) > float(match_value('paused_stable', 'LiveSeconds')))
        return valid, {}

    check(0, roster)
    check(1, lambda: (not truth(match_value('lobby', 'bLive')) and truth(match_value('live', 'bLive')), {}))
    check(2, lambda: movement('moving'))
    check(3, lambda: movement('stopped'))
    check(4, pause)
    check(5, picker)
    check(6, color)
    check(7, lambda: capture(screenshot))
    check(8, persistence)
    check(9, resumed)
    check(10, lambda: capture(baseline))
    return tests, {'owner':owner, 'observation_errors':errors, 'observed_stages':list(states), 'completed_macro':'done' in states}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-manifest', type=Path, default=ROOT/'.local/latest-package.json')
    parser.add_argument('--arena', choices=list(ARENA_MAPS), default='Classic')
    parser.add_argument('--timeout-seconds', type=float, default=90)
    parser.add_argument('--visible', action='store_true',
                        help='Show a normal game window for agent-managed viewport focus; omit RenderOffscreen.')
    parser.add_argument('--run', action='store_true', help='Launch the owned package; default is a read-only plan.')
    args = parser.parse_args()
    if not 20 <= args.timeout_seconds <= 180:
        parser.error('Timeout must be between 20 and 180 seconds')
    directory = ROOT/'.local/packaged-broom-trails'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    steps = plan(directory)
    report = {'status':'not_run', 'scope':'packaged local console-injected input, native tracer flags, picker HUD and isolated color persistence',
              'planned_tests':list(CASES), 'hardware_claim':False, 'remote_replication_claim':False,
              'not_covered':['earned partial/super boosts', 'remote replication', 'physical controllers',
                             'packaged trail pixels and frame rate', 'picker visual quality until agent image inspection'],
              'input_boundary':'UE EnhancedInput Input.+key/Input.-key -> PlayerController::InputKey -> native bindings',
              'readback':'engine GETALL reflected properties; no PIE-only diagnostics',
              'package_manifest':str(args.package_manifest.resolve()), 'output_directory':str(directory),
              'arena':args.arena, 'map':ARENA_MAPS[args.arena],
              'window_mode':'visible' if args.visible else 'offscreen',
              'viewport_focus':'normal game focus rules apply; driver does not override focus'}
    if not args.run:
        report['macro_steps'] = [{'label':row['label'], 'wait_frames':row['wait_frames']} for row in steps]
        report['instruction'] = 'Use --run with a completed UE5.8 Development package. The driver requires no manual interaction.'
        print(json.dumps(report, indent=2))
        return 0
    if sys.platform != 'win32':
        parser.error('Packaged launch requires Windows')
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'Binaries').mkdir()
    process = None
    try:
        manifest = args.package_manifest.resolve()
        package = json.loads(manifest.read_text(encoding='utf-8-sig'))
        if (package.get('Status') != 'complete' or package.get('NativeRuntime') is not True
                or package.get('Configuration') != 'Development' or not str(package.get('EngineVersion', '')).startswith('5.8.')):
            raise ValueError('A complete native UE5.8 Development package is required')
        bootstrap, archive = Path(package['Executable']), Path(package['Archive']).resolve()
        if not bootstrap.is_absolute() or not bootstrap.is_file():
            raise ValueError('Absolute package bootstrap executable must exist')
        package_root = bootstrap.parent.resolve()
        package_root.relative_to(archive)
        if ARENA_MAPS[args.arena] not in package.get('ArenaMaps', [ARENA_MAPS['Classic']]):
            raise ValueError('Selected arena is not recorded in the candidate package manifest')
        executable = package_root/'BasketbroomDev/Binaries/Win64/BasketbroomDev.exe'
        if not executable.is_file():
            raise ValueError('Packaged main executable missing')
        ini, log, screenshot = directory/'UserData/GameUserSettings.ini', directory/'game.log', directory/'picker.png'
        baseline = directory/'baseline-hud.png'
        ini.parent.mkdir()
        for entry in steps:
            Path(entry['file']).write_text('\n'.join(entry['commands'])+'\n', encoding='utf-8')
        arguments = [str(executable), ARENA_MAPS[args.arena]+'?Practice=1',
                     '-unattended', '-windowed', '-ResX=1280', '-ResY=720', '-ForceRes', '-NoSplash', '-NoSound',
                     # Readback happens after normal process exit, which flushes
                     # logs. FORCELOGFLUSH previously added ~11ms per GETALL row.
                     # ExecMacro's category defaults to Warning; explicitly enable
                     # its Log-level markers so stages have a verified boundary.
                     '-LogCmds=LogPlayerManagement Log', '-AbsLog='+str(log),
                     '-UserDir='+str(ini.parent), '-GameUserSettingsINI='+str(ini),
                     '-ExecCmds=EXEC '+"'"+steps[0]['file'].replace('\\', '/')+"'"]
        if not args.visible:
            arguments.append('-RenderOffscreen')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1 if args.visible else 0  # SW_SHOWNORMAL / SW_HIDE
        report.update(status='running', executable=str(executable), executable_sha256=sha(executable),
                      package_manifest_sha256=sha(manifest), arguments=arguments, log=str(log), isolated_ini=str(ini),
                      screenshot=str(screenshot), baseline_screenshot=str(baseline), start_utc=datetime.now(timezone.utc).isoformat())
        process = subprocess.Popen(arguments, cwd=package_root, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   startupinfo=startup, creationflags=0 if args.visible else subprocess.CREATE_NO_WINDOW)
        report.update(pid=process.pid, process_ownership='original subprocess process creation handle')
        started = time.monotonic()
        while process.poll() is None and time.monotonic()-started < args.timeout_seconds:
            time.sleep(.2)
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        if process.poll() is None:
            raise TimeoutError('Owned packaged smoke exceeded its wall-time bound')
        report['exit_code'] = process.returncode
        log_text = log.read_text(encoding='utf-8-sig', errors='replace')
        tests, evidence = evaluate(log_text, steps, screenshot, ini, baseline)
        by_name = {row['name']:row for row in tests}
        report['tests'] = [by_name.get(name, {'name':name, 'status':'not_run'}) for name in CASES]
        report['evidence'] = evidence
        report['log_errors'] = ERRORS.findall(log_text)
        report['passed'] = sum(row['status'] == 'passed' for row in report['tests'])
        report['status'] = ('passed' if report['passed'] == len(CASES) and evidence.get('completed_macro')
                            and process.returncode == 0 and not report['log_errors'] else 'failed')
        if screenshot.exists():
            report['screenshot_sha256'] = sha(screenshot)
        if baseline.exists():
            report['baseline_screenshot_sha256'] = sha(baseline)
    except Exception as error:
        report.update(status='error', error=str(error))
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    # Popen retains its creation handle on Windows; no PID lookup,
                    # process-name search or unrelated game termination is used.
                    process.terminate()
                    process.wait(timeout=10)
                    report['cleanup'] = 'terminated exact owned process using original creation handle'
                else:
                    report['cleanup'] = 'owned process exited'
            except Exception as error:
                report.update(status='error', cleanup_error=str(error))
        report['completed_utc'] = datetime.now(timezone.utc).isoformat()
        (directory/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
