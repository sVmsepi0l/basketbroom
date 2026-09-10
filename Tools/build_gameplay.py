"""Author the playable Basketbroom training slice as native Blueprint bytecode.

Standalone Unreal Engine 5.8 authoring tool. No Python runs in the resulting
gameplay; native Blueprint nodes handle movement, scoring, and sound playback.
"""
import sys
import importlib
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Tools'))
import bp_graph
importlib.reload(bp_graph)
from bp_graph import Graph, create_blueprint, pin_type, connect

BASE = '/Basketbroom/Blueprints/'
MATH = '/Script/Engine.KismetMathLibrary.'
GS = '/Script/Engine.GameplayStatics.'
ACTOR = '/Script/Engine.Actor.'
PC = '/Script/Engine.PlayerController.'
MANAGER = BASE + 'BP_BBMatch.BP_BBMatch_C'

def fn(g, path, **args):
    return g.out(g.call(path, **args))

def math(g, name, **args):
    return fn(g, MATH + name, **args)

def add(g, a, b): return math(g, 'Add_DoubleDouble', A=a, B=b)
def sub(g, a, b): return math(g, 'Subtract_DoubleDouble', A=a, B=b)
def mul(g, a, b): return math(g, 'Multiply_DoubleDouble', A=a, B=b)
def div(g, a, b): return math(g, 'Divide_DoubleDouble', A=a, B=b)
def gt(g, a, b): return math(g, 'Greater_DoubleDouble', A=a, B=b)
def lt(g, a, b): return math(g, 'Less_DoubleDouble', A=a, B=b)
def both(g, a, b): return math(g, 'BooleanAND', A=a, B=b)
def either(g, a, b): return math(g, 'BooleanOR', A=a, B=b)
def neg(g, a): return math(g, 'Not_PreBool', A=a)
def eqi(g, a, b): return math(g, 'EqualEqual_IntInt', A=a, B=b)
def vec(g, x=0, y=0, z=0): return math(g, 'MakeVector', X=x, Y=y, Z=z)
def xyz(g, v):
    n = g.call(MATH+'BreakVector', InVec=v)
    return [g.out(n, s) for s in ('X','Y','Z')]
def vadd(g, a, b): return math(g, 'Add_VectorVector', A=a, B=b)
def vmul(g, a, b): return math(g, 'Multiply_VectorFloat', A=a, B=b)
def vsub(g, a, b): return math(g, 'Subtract_VectorVector', A=a, B=b)
def pawn(g): return fn(g, GS+'GetPlayerPawn', PlayerIndex=0)
def controller(g): return fn(g, GS+'GetPlayerController', PlayerIndex=0)
def camera(g): return fn(g, GS+'GetPlayerCameraManager', PlayerIndex=0)
def location(g, actor=None):
    return fn(g, ACTOR+'K2_GetActorLocation', **({'target':actor} if actor is not None else {}))
def key(g, name, held=False):
    # FKey has a custom ImportTextItem: its literal is the key name, not a struct.
    return fn(g, PC+('IsInputKeyDown' if held else 'WasInputKeyJustPressed'), target=controller(g), Key=name)
def mg(g, name): return g.get(name, target=g.get('Match'), class_path=MANAGER)
def ms(g, name, value): return g.set(name, value, target=g.get('Match'), class_path=MANAGER)
def setloc(g, p, actor=None):
    return g.call(ACTOR+'K2_SetActorLocation', NewLocation=p, bSweep=False, bTeleport=True, **({'target':actor} if actor is not None else {}))

def sound(g, name, volume=0.65):
    """Create a native one-shot node backed by a checked imported SoundWave."""
    asset_name = 'S_BB_' + name
    path = '/Basketbroom/Audio/' + asset_name + '.' + asset_name
    asset = unreal.load_asset(path)
    if asset is None or not isinstance(asset, unreal.SoundWave):
        raise RuntimeError('Missing Basketbroom sound; run build_audio.build() first: ' + path)
    return g.call(GS+'PlaySound2D', Sound=asset, VolumeMultiplier=volume,
                  PitchMultiplier=1.0, bIsUISound=False)

def fresh(name, parent=unreal.Actor):
    path = BASE + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        # Rebuild only the generated graph assets, after unloading the generated map.
        existing = unreal.load_asset(path)
        for graph in list(unreal.BlueprintEditorLibrary.list_graphs(existing)):
            if graph.get_name() not in ('EventGraph', 'UserConstructionScript'):
                unreal.BlueprintEditorLibrary.remove_graph(existing, graph)
                continue
            editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            if graph.get_name() == 'EventGraph':
                editor.remove_nodes(editor.list_all_nodes())
        g = Graph(existing)
        for var in list(unreal.BlueprintEditorLibrary.list_member_variable_names(existing, False)):
            g.editor.remove_member_variable(var)
        return existing, g
    bp = create_blueprint(path, parent)
    return bp, Graph(bp)

def make_manager():
    bp, g = fresh('BP_BBMatch')
    for name, kind, default in [('TealScore','int',0),('CopperScore','int',0),('HasBall','bool',False),
            ('MatchOver','bool',False),('SecondsLeft','double',300),('Elapsed','double',0),('Stun','double',0),
            ('SnipeDistance','double',0),('SnitchDistance','double',0),
            ('SnipePosition','vector',(0,0,0)),('SnitchPosition','vector',(0,0,0)),
            ('SnipeProgress','double',0),('SnitchProgress','double',0),
            ('SnipeActive','bool',False),('SnitchActive','bool',False),
            ('TargetName','string','NO CHASE TARGET'),('TargetDistance','double',0),
            ('CatchProgress','double',0),('TargetAvailable','bool',False),
            ('Message','string','TRAINING FLIGHT | Find a ball. Press E to carry it.')]:
        g.var(name,kind,default,editable=True)
    tick = g.event('ReceiveTick')
    dt = g.out(tick,'DeltaSeconds')
    elapsed = g.set('Elapsed',add(g,g.get('Elapsed'),dt))
    stun = g.set('Stun',math(g,'FMax',A=0,B=sub(g,g.get('Stun'),dt)))
    seq = g.sequence(4)
    g.chain(tick,elapsed,stun,seq)
    live = g.branch(neg(g,g.get('MatchOver')))
    g.exec(seq,live,'then_0')
    countdown = g.set('SecondsLeft',math(g,'FMax',A=0,B=sub(g,g.get('SecondsLeft'),dt)))
    end = g.branch(lt(g,g.get('SecondsLeft'),0.001))
    over = g.set('MatchOver',True)
    message = g.set('Message','TRAINING COMPLETE | Press R for another flight')
    g.chain(live,countdown,end,over,message)
    reset = g.branch(key(g,'R'))
    reload = g.call(GS+'OpenLevel',LevelName='BB_Arena',bAbsolute=True)
    g.exec(seq,reset,'then_1'); g.exec(reset,reload)
    # Keep ordinary flight within the playable envelope without an invisible roof net.
    p = location(g,pawn(g)); x,y,z = xyz(g,p)
    clamp = setloc(g,vec(g,math(g,'FClamp',Value=x,Min=-6710,Max=6710),
                        math(g,'FClamp',Value=y,Min=-3090,Max=3090),math(g,'FClamp',Value=z,Min=130,Max=6250)),pawn(g))
    g.exec(seq,clamp,'then_2')
    # Each chase ball publishes its own sample; choosing here avoids tick-order
    # races from both balls clearing or overwriting a shared nearest-distance.
    available = both(g,either(g,g.get('SnipeActive'),g.get('SnitchActive')),neg(g,g.get('MatchOver')))
    pick_snipe = both(g,g.get('SnipeActive'),either(g,neg(g,g.get('SnitchActive')),
                       neg(g,gt(g,g.get('SnipeDistance'),g.get('SnitchDistance')))))
    target_name = math(g,'SelectString',A='SNIPE',B='SNITCH',bPickA=pick_snipe)
    target_distance = math(g,'SelectFloat',A=g.get('SnipeDistance'),B=g.get('SnitchDistance'),bPickA=pick_snipe)
    target_progress = math(g,'SelectFloat',A=g.get('SnipeProgress'),B=g.get('SnitchProgress'),bPickA=pick_snipe)
    target = g.set('TargetAvailable',available)
    g.exec(seq,target,'then_3')
    g.chain(target,g.set('TargetName',math(g,'SelectString',A=target_name,B='NO CHASE TARGET',bPickA=available)),
            g.set('TargetDistance',math(g,'SelectFloat',A=target_distance,B=0,bPickA=available)),
            g.set('CatchProgress',math(g,'SelectFloat',A=target_progress,B=0,bPickA=available)))
    g.compile(save=True)
    return bp

def bind_manager(g):
    g.var('Match',unreal.load_class(None,MANAGER))
    begin = g.event('ReceiveBeginPlay')
    find = g.call(GS+'GetActorOfClass',ActorClass=unreal.load_class(None,MANAGER))
    assign = g.set('Match',g.out(find))
    g.chain(begin,find,assign)
    return assign

def make_ball():
    bp,g = fresh('BP_BBBall',unreal.StaticMeshActor)
    for name,kind,default in [('Kind','int',0),('Held','bool',False),('Cooldown','double',0),('BotOwner','int',-1),('BotPosition','vector',(0,0,900)),
          ('CatchTime','double',0),('P','vector',(0,0,0)),('OldP','vector',(0,0,0)),
          ('Velocity','vector',(0,0,0)),('Home','vector',(0,0,900))]:
        g.var(name,kind,default,editable=True)
    bind_manager(g)
    tick = g.event('ReceiveTick'); dt=g.out(tick,'DeltaSeconds')
    cd=g.set('Cooldown',math(g,'FMax',A=0,B=sub(g,g.get('Cooldown'),dt)))
    valid=g.branch(fn(g,'/Script/Engine.KismetSystemLibrary.IsValid',Object=g.get('Match')))
    ready=g.branch(both(g,either(g,lt(g,g.get('Kind'),2),lt(g,g.get('Cooldown'),0.001)),neg(g,mg(g,'MatchOver'))))
    botheld=g.branch(math(g,'Greater_IntInt',A=g.get('BotOwner'),B=-1))
    classify=g.branch(lt(g,g.get('Kind'),2))
    updates=g.sequence(2)
    g.chain(tick,valid,cd,updates)
    g.exec(updates,ready,'then_0'); g.exec(ready,botheld)
    g.exec(botheld,classify,'else')
    botfollow=setloc(g,g.get('BotPosition'))
    steal=g.branch(both(g,both(g,key(g,'E'),lt(g,math(g,'VSize',A=vsub(g,location(g),location(g,pawn(g)))),425)),neg(g,mg(g,'HasBall'))))
    g.chain(botheld,botfollow,steal,g.set('BotOwner',-1),g.set('Held',True),ms(g,'HasBall',True),ms(g,'Message','INTERCEPTION | Possession won. Left mouse to shoot.'),sound(g,'Catch'))
    # Ordinary scoring balls: pickup, carry and release; one controlled ball at a time.
    held=g.branch(g.get('Held')); g.exec(classify,held)
    camrot=fn(g,'/Script/Engine.PlayerCameraManager.GetCameraRotation',target=camera(g))
    forward=math(g,'GetForwardVector',InRot=camrot)
    right=math(g,'GetRightVector',InRot=camrot)
    holdpos=vadd(g,location(g,pawn(g)),vadd(g,vmul(g,forward,175),vadd(g,vmul(g,right,72),vec(g,0,0,-48))))
    follow=setloc(g,holdpos)
    shoot=g.branch(either(g,key(g,'LeftMouseButton'),gt(g,mg(g,'Stun'),0)))
    release=g.set('Held',False); clear=ms(g,'HasBall',False)
    impulse=g.set('Velocity',vadd(g,vmul(g,forward,4400),vmul(g,fn(g,ACTOR+'GetVelocity',target=pawn(g)),0.4)))
    delay=g.set('Cooldown',0.15)
    msg=ms(g,'Message','BALL RELEASED | Bank shots stay live')
    heldroof=g.branch(gt(g,xyz(g,holdpos)[2],4206.24))
    g.chain(held,follow,heldroof)
    g.exec(heldroof,shoot,'else'); g.chain(shoot,release,clear,impulse,delay,msg,sound(g,'Throw'))
    g.chain(heldroof,g.set('Held',False),ms(g,'HasBall',False),setloc(g,g.get('Home')),g.set('Velocity',(0,0,0)),g.set('Cooldown',0.8),ms(g,'Message','NO CROWN | Carried ball returned at the roofline.'))
    free=g.sequence(3); g.exec(held,free,'else')
    distance=math(g,'VSize',A=vsub(g,location(g),location(g,pawn(g))))
    take=g.branch(both(g,both(g,key(g,'E'),lt(g,distance,425)),both(g,neg(g,mg(g,'HasBall')),lt(g,g.get('Cooldown'),0.001))))
    grab=g.set('Held',True); occupy=ms(g,'HasBall',True); stop=g.set('Velocity',(0,0,0))
    note=ms(g,'Message','CARRYING | Left mouse to shoot. Aim through the matching hoop.')
    g.exec(free,take,'then_0'); g.chain(take,grab,occupy,stop,note,sound(g,'Catch'))
    # Kinematic ball physics makes rebound/scoring deterministic and independent of frame rate.
    save=g.set('OldP',location(g)); pv=g.set('Velocity',vadd(g,g.get('Velocity'),vec(g,0,0,mul(g,-380,dt))))
    advance=g.set('P',vadd(g,location(g),vmul(g,g.get('Velocity'),dt)))
    surfaces=g.sequence(6)
    g.exec(free,save,'then_1'); g.chain(save,pv,advance,surfaces)
    # Scoring is swept across each goal plane; whole-ball clearance required.
    for index,side in enumerate((1,-1)):
        px,py,pz=xyz(g,g.get('P')); ox,oy,oz=xyz(g,g.get('OldP'))
        radius=math(g,'SelectFloat',A=33,B=24,bPickA=eqi(g,g.get('Kind'),0))
        full_plane=add(g,6400.8,radius)
        crosses=both(g,lt(g,mul(g,ox,side),full_plane),gt(g,mul(g,px,side),full_plane))
        test=g.branch(crosses); g.exec(surfaces,test,'then_'+str(index))
        frac=div(g,sub(g,side*6400.8,ox),sub(g,px,ox))
        hit_y=add(g,oy,mul(g,sub(g,py,oy),frac)); hit_z=add(g,oz,mul(g,sub(g,pz,oz),frac))
        def in_circle(y,z,radius):
            dy=sub(g,hit_y,y); dz=sub(g,hit_z,z)
            return lt(g,add(g,mul(g,dy,dy),mul(g,dz,dz)),radius*radius)
        large=either(g,in_circle(-1066.8,2103.12,301),either(g,in_circle(0,2103.12,301),in_circle(1066.8,2103.12,301)))
        small=in_circle(0,3048,169)
        legal=either(g,both(g,eqi(g,g.get('Kind'),0),large),both(g,eqi(g,g.get('Kind'),1),small))
        goal=g.branch(legal); g.exec(test,goal)
        quark=g.branch(eqi(g,g.get('Kind'),1)); g.exec(goal,quark)
        for isquark,points in [(False,13),(True,37)]:
            score_name='TealScore' if side==1 else 'CopperScore'
            award=ms(g,score_name,math(g,'Add_IntInt',A=mg(g,score_name),B=points))
            text=ms(g,'Message',('QUARK +37 | Small-hoop finish!' if isquark else 'QUAFFLE +13 | Clean through the hoop!'))
            resetp=g.set('P',g.get('Home')); resetv=g.set('Velocity',(0,0,0)); wait=g.set('Cooldown',1.0)
            g.exec(quark,award,'then' if isquark else 'else'); g.chain(award,text,resetp,resetv,wait,sound(g,'Score'))
    # Side/end nets preserve 75% normal incident speed.
    for axis,limit,out_index in [(0,6850.8,2),(1,3140,3)]:
        coords=xyz(g,g.get('P')); vel=xyz(g,g.get('Velocity'))
        hit=g.branch(gt(g,math(g,'Abs',A=coords[axis]),limit))
        pos=list(coords); pos[axis]=math(g,'FClamp',Value=coords[axis],Min=-limit,Max=limit)
        newv=list(vel); newv[axis]=mul(g,vel[axis],-0.75)
        g.exec(surfaces,hit,'then_'+str(out_index)); g.chain(hit,g.set('P',vec(g,*pos)),g.set('Velocity',vec(g,*newv)),sound(g,'Bounce',0.16))
    coords=xyz(g,g.get('P')); vel=xyz(g,g.get('Velocity'))
    floor=g.branch(lt(g,coords[2],65))
    bounce=math(g,'FMax',A=390,B=mul(g,math(g,'Abs',A=vel[2]),0.75))
    g.exec(surfaces,floor,'then_4'); g.chain(floor,g.set('P',vec(g,coords[0],coords[1],65)),g.set('Velocity',vec(g,vel[0],vel[1],bounce)))
    # No Crown: this individual ball returns; the rest of the arena stays live.
    roof=g.branch(gt(g,xyz(g,g.get('P'))[2],4206.24))
    g.exec(surfaces,roof,'then_5'); g.chain(roof,g.set('P',g.get('Home')),g.set('Velocity',(0,0,0)),ms(g,'Message','NO CROWN | Ball returned. Open roof is out for scoring balls.'))
    apply=setloc(g,g.get('P')); g.exec(free,apply,'then_2')
    # Chase balls use deterministic paths and a full 1-second capture window.
    chase=g.sequence(2); g.exec(classify,chase,'else')
    # The Snipe traverses its route at 60% of the Snitch's path rate.
    chase_rate=math(g,'SelectFloat',A=0.6,B=1.0,bPickA=eqi(g,g.get('Kind'),2))
    t=mul(g,mg(g,'Elapsed'),chase_rate); phase=mul(g,g.get('Kind'),2.17)
    cx=mul(g,math(g,'Sin',A=add(g,mul(g,t,0.23),phase)),4300)
    cy=mul(g,math(g,'Cos',A=add(g,mul(g,t,0.41),phase)),2050)
    cz=add(g,2200,mul(g,math(g,'Sin',A=add(g,mul(g,t,0.32),phase)),950))
    g.exec(chase,setloc(g,vec(g,cx,cy,cz)),'then_0')
    near=both(g,neg(g,gt(g,math(g,'VSize',A=vsub(g,location(g),location(g,pawn(g)))),380)),both(g,key(g,'E',True),neg(g,mg(g,'HasBall'))))
    catch=g.branch(near); g.exec(chase,catch,'then_1')
    accumulate=g.set('CatchTime',add(g,g.get('CatchTime'),dt)); captured=g.branch(neg(g,lt(g,g.get('CatchTime'),1)))
    g.chain(catch,accumulate,captured); g.exec(catch,g.set('CatchTime',0),'else')
    is_snipe=g.branch(eqi(g,g.get('Kind'),2)); g.chain(captured,sound(g,'Catch'),is_snipe)
    g.chain(is_snipe,ms(g,'TealScore',math(g,'Add_IntInt',A=mg(g,'TealScore'),B=69)),g.set('Cooldown',180),g.set('CatchTime',0),setloc(g,(0,0,-3000)),ms(g,'Message','SNIPE +69 | Returns in three minutes'))
    snitch=ms(g,'TealScore',math(g,'Add_IntInt',A=mg(g,'TealScore'),B=150))
    g.exec(is_snipe,snitch,'else'); g.chain(snitch,ms(g,'MatchOver',True),ms(g,'Message','SNITCH +150 | Training complete. Press R to restart.'))
    # Run after the gameplay branch even during cooldown, so a caught Snipe
    # cannot leave a stale target or capture meter visible for three minutes.
    report=g.branch(either(g,eqi(g,g.get('Kind'),2),eqi(g,g.get('Kind'),3)))
    g.exec(updates,report,'then_1')
    report_snipe=g.branch(eqi(g,g.get('Kind'),2)); g.exec(report,report_snipe)
    active=both(g,lt(g,g.get('Cooldown'),0.001),neg(g,mg(g,'MatchOver')))
    chase_distance=math(g,'VSize',A=vsub(g,location(g),location(g,pawn(g))))
    capture_progress=math(g,'SelectFloat',A=math(g,'FClamp',Value=g.get('CatchTime'),Min=0,Max=1),B=0,bPickA=active)
    for prefix,output in [('Snipe','then'),('Snitch','else')]:
        publish=ms(g,prefix+'Active',active)
        g.exec(report_snipe,publish,output)
        g.chain(publish,ms(g,prefix+'Distance',chase_distance),ms(g,prefix+'Progress',capture_progress),
                ms(g,prefix+'Position',location(g)))
    g.compile(save=True)
    return bp

def make_pawn():
    bp,g=fresh('BP_BBBroom',unreal.DefaultPawn)
    # FloatingPawnMovement supplies acceleration; explicit inputs keep E free for catches.
    tick=g.event('ReceiveTick')
    seq=g.sequence(8); g.exec(tick,seq)
    mouse=g.call(PC+'GetInputMouseDelta',target=controller(g))
    yaw=g.call('/Script/Engine.Pawn.AddControllerYawInput',Val=mul(g,g.out(mouse,'DeltaX'),0.14))
    pitch=g.call('/Script/Engine.Pawn.AddControllerPitchInput',Val=mul(g,g.out(mouse,'DeltaY'),-0.14))
    g.exec(seq,yaw,'then_0'); g.exec(seq,pitch,'then_1')
    rot=fn(g,'/Script/Engine.Pawn.GetControlRotation')
    forward=math(g,'GetForwardVector',InRot=rot)
    right=math(g,'GetRightVector',InRot=rot)
    for i,(name,direction,scale) in enumerate([('W',forward,1),('S',forward,-1),('D',right,1),('A',right,-1),('SpaceBar',(0,0,1),1),('LeftControl',(0,0,1),-1)]):
        check=g.branch(key(g,name,True))
        move=g.call('/Script/Engine.Pawn.AddMovementInput',WorldDirection=direction,ScaleValue=scale,bForce=False)
        g.exec(seq,check,'then_'+str(i+2)); g.exec(check,move)
    g.compile(save=True)
    cdo=unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property('add_default_movement_bindings',False)
    move=cdo.get_editor_property('movement_component')
    move.set_editor_property('max_speed',2100)
    move.set_editor_property('acceleration',3600)
    move.set_editor_property('deceleration',2900)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp

def build():
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    rebuild=globals().get('BRIDGE_ARGS',{}).get('rebuild',[])
    manager=make_manager() if 'manager' in rebuild else (unreal.load_asset(BASE+'BP_BBMatch') or make_manager())
    ball=make_ball() if 'ball' in rebuild else (unreal.load_asset(BASE+'BP_BBBall') or make_ball())
    broom=make_pawn() if 'broom' in rebuild else (unreal.load_asset(BASE+'BP_BBBroom') or make_pawn())
    summary={'manager':manager.get_path_name(),'ball':ball.get_path_name(),'broom':broom.get_path_name()}
    (ROOT/'.local'/'gameplay-built.json').write_text(__import__('json').dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    RESULT=build()
