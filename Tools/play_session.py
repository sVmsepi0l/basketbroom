"""Reproducible interactive checks on PIE copies only; not runtime gameplay."""
import unreal
import json
from pathlib import Path

args=globals().get('BRIDGE_ARGS',{})
operation=args.get('operation','inspect')
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if operation=='start':
    level.editor_request_begin_play()
    RESULT={'requested':'play'}
elif operation=='stop':
    level.editor_request_end_play()
    RESULT={'requested':'stop'}
else:
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start Play In Editor before interacting with the game')
    actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
    match=next(a for a in actors if a.get_class().get_name().startswith('BP_BBMatch'))
    balls=[a for a in actors if a.get_class().get_name().startswith('BP_BBBall')]
    player=unreal.GameplayStatics.get_player_pawn(world,0)
    controller=unreal.GameplayStatics.get_player_controller(world,0)
    ball=next(a for a in balls if a.get_editor_property('Kind')==0)
    if operation=='setup_pickup':
        for a in actors:
            if a.get_class().get_name().startswith('BP_BBBot'):
                a.set_actor_tick_enabled(False)
        player.set_actor_location(unreal.Vector(-4300,0,240),False,True)
        controller.set_control_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0))
        match.set_editor_property('HasBall',False)
        match.set_editor_property('MatchOver',False)
        match.set_editor_property('SecondsLeft',300.0)
        ball.set_editor_property('Held',False)
        ball.set_editor_property('BotOwner',-1)
        ball.set_editor_property('Cooldown',0.0)
        ball.set_editor_property('Velocity',unreal.Vector(0,0,0))
        ball.set_actor_location(unreal.Vector(-4050,0,200),False,True)
    elif operation=='setup_goal':
        if not ball.get_editor_property('Held'):
            raise RuntimeError('Use E to pick up the test Quaffle first')
        player.set_actor_location(unreal.Vector(4200,0,2151.12),False,True)
        controller.set_control_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0))
    elif operation=='screenshot':
        unreal.SystemLibrary.execute_console_command(world,'HighResShot 1600x900')
    elif operation=='chase_screenshot':
        # Presentation fixture on a PIE copy; no capture or score is injected.
        target=next(a for a in balls if a.get_editor_property('Kind')==3)
        focus=target.get_actor_location()
        view=focus-unreal.Vector(1600,800,-180)
        player.set_actor_location(view,False,True)
        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(view,focus))
        unreal.SystemLibrary.execute_console_command(world,'HighResShot 1600x900')
    def v(p): return [round(p.x,2),round(p.y,2),round(p.z,2)]
    RESULT={'operation':operation,'player':player.get_class().get_name(),
      'position':v(player.get_actor_location()),'velocity':v(player.get_velocity()),
      'rotation':str(controller.get_control_rotation()),
      'score':[match.get_editor_property('TealScore'),match.get_editor_property('CopperScore')],
      'has_ball':match.get_editor_property('HasBall'),'message':match.get_editor_property('Message'),
      'balls':[{'kind':a.get_editor_property('Kind'),'held':a.get_editor_property('Held'),
        'owner':a.get_editor_property('BotOwner'),'position':v(a.get_actor_location())} for a in balls]}
    (Path(__file__).resolve().parents[1]/'.local'/'interactive-state.json').write_text(json.dumps(RESULT,indent=2))
