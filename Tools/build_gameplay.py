"""author the playable basketbroom training slice as native blueprint bytecode.

standalone unreal engine 5.8 authoring tool. no python runs in the resulting
gameplay; native blueprint nodes handle movement, scoring, and sound playback.
"""

import importlib.util as _arena_importlib
from pathlib import path as _arenapath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import sys
import importlib
import math as scalar_math
from pathlib import path
import unreal

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
import bp_graph
importlib.reload(bp_graph)
from bp_graph import graph, create_blueprint, pin_type, connect
import build_arena as arena_geometry
importlib.reload(arena_geometry)

base = '/Basketbroom/Blueprints/'
math = '/Script/Engine.KismetMathLibrary.'
gs = '/Script/Engine.GameplayStatics.'
actor = '/Script/Engine.Actor.'
pc = '/Script/Engine.PlayerController.'
manager = base + 'BP_BBMatch.BP_BBMatch_C'

def fn(g, path, **args):
    return g.out(g.call(path, **args))

def math(g, name, **args):
    return fn(g, math + name, **args)

def add(g, a, b): return math(g, 'add_doubledouble', a=a, b=b)
def sub(g, a, b): return math(g, 'subtract_doubledouble', a=a, b=b)
def mul(g, a, b): return math(g, 'multiply_doubledouble', a=a, b=b)
def div(g, a, b): return math(g, 'divide_doubledouble', a=a, b=b)
def gt(g, a, b): return math(g, 'greater_doubledouble', a=a, b=b)
def lt(g, a, b): return math(g, 'less_doubledouble', a=a, b=b)
def both(g, a, b): return math(g, 'booleanand', a=a, b=b)
def either(g, a, b): return math(g, 'booleanor', a=a, b=b)
def neg(g, a): return math(g, 'not_prebool', a=a)
def eqi(g, a, b): return math(g, 'equalequal_intint', a=a, b=b)
def vec(g, x=0, y=0, z=0): return math(g, 'makevector', x=x, y=y, z=z)
def xyz(g, v):
    n = g.call(MATH+'BreakVector', invec=v)
    return [g.out(n, s) for s in ('x','y','z')]
def vadd(g, a, b): return math(g, 'add_vectorvector', a=a, b=b)
def vmul(g, a, b): return math(g, 'multiply_vectorfloat', a=a, b=b)
def vsub(g, a, b): return math(g, 'subtract_vectorvector', a=a, b=b)
def pyramid_limit(g, x, y, radius):
    """sphere support inside the same four roof planes used by native play."""
    sx = (arena_geometry.PYRAMID_APEX - arena_geometry.ROOFLINE) / arena_geometry.BACKSTOP_X
    sy = (arena_geometry.PYRAMID_APEX - arena_geometry.ROOFLINE) / arena_geometry.HALF_WIDTH
    x_support = add(g, mul(g, math(g, 'abs', a=x), sx), mul(g, radius, scalar_math.sqrt(1 + sx * sx)))
    y_support = add(g, mul(g, math(g, 'abs', a=y), sy), mul(g, radius, scalar_math.sqrt(1 + sy * sy)))
    return sub(g, arena_geometry.PYRAMID_APEX, math(g, 'fmax', a=x_support, b=y_support))


def pyramid_position(g, point, radius):
    x, y, z = xyz(g, point)
    lx = sub(g, arena_geometry.BACKSTOP_X, radius)
    ly = sub(g, arena_geometry.HALF_WIDTH, radius)
    x = math(g, 'fclamp', value=x, min=mul(g, lx, -1), max=lx)
    y = math(g, 'fclamp', value=y, min=mul(g, ly, -1), max=ly)
    z = math(g, 'fclamp', value=z, min=radius, max=pyramid_limit(g, x, y, radius))
    return vec(g, x, y, z)


def ball_radius(g):
    return math(g, 'selectfloat', a=33, b=24, bpicka=eqi(g, g.get('Kind'), 0))


def roof_rebounds(g):
    """closed plane response for training's kinematic scoring balls.

    the segment's endpoint detects exit from any convex half-space, so even a
    fast throw cannot skip a thin mesh strand. project out penetration and
    reflect only outward normal speed; a second pass settles hip/apex contacts.
    these are generated blueprint nodes, never python callbacks at runtime.
    """
    planes = []
    for face in range(4):
        slope = (arena_geometry.PYRAMID_APEX - arena_geometry.ROOFLINE) / (
            arena_geometry.BACKSTOP_X if face < 2 else arena_geometry.HALF_WIDTH)
        sign = 1 if face % 2 == 0 else -1
        length = scalar_math.sqrt(1 + slope * slope)
        n = (sign * slope / length, 0, 1 / length) if face < 2 else (0, sign * slope / length, 1 / length)
        planes.append((n, arena_geometry.PYRAMID_APEX / length))
    sequence = g.sequence(9)
    for index, (normal, distance) in enumerate(planes * 2):
        def dot(v):
            x, y, z = xyz(g, v)
            return add(g, add(g, mul(g, x, normal[0]), mul(g, y, normal[1])), mul(g, z, normal[2]))
        depth = add(g, sub(g, dot(g.get('P')), distance), ball_radius(g))
        hit = g.branch(gt(g, depth, 0))
        projection = g.set('P', vsub(g, g.get('P'), vmul(g, normal, add(g, depth, 0.01))))
        outward = g.branch(gt(g, dot(g.get('Velocity')), 0))
        reflection = g.set('Velocity', vsub(g, g.get('Velocity'), vmul(g, normal, mul(g, dot(g.get('Velocity')), 1.75))))
        g.exec(sequence, hit, 'then_' + str(index))
        g.chain(hit, projection, outward, reflection, sound(g, 'bounce', 0.16))
    # settle any accumulated float/seam penetration without killing custody,
    # resetting to home, changing scores, or applying an obsolete crown foul.
    g.exec(sequence, g.set('P', pyramid_position(g, g.get('P'), ball_radius(g))), 'then_8')
    return sequence


def pawn(g): return fn(g, gs+'getplayerpawn', playerindex=0)
def controller(g): return fn(g, gs+'getplayercontroller', playerindex=0)
def camera(g): return fn(g, gs+'getplayercameramanager', playerindex=0)
def location(g, actor=None):
    return fn(g, actor+'k2_getactorlocation', **({'target':actor} if actor is not none else {}))
def key(g, name, held=False):
    # fkey has a custom ImportTextItem: its literal is the key name, not a struct.
    return fn(g, pc+('isinputkeydown' if held else 'wasinputkeyjustpressed'), target=controller(g), key=name)
def mg(g, name): return g.get(name, target=g.get('Match'), class_path=manager)
def ms(g, name, value): return g.set(name, value, target=g.get('Match'), class_path=manager)
def setloc(g, p, actor=None):
    return g.call(ACTOR+'K2_SetActorLocation', newlocation=p, bsweep=false, bteleport=true, **({'target':actor} if actor is not none else {}))

def sound(g, name, volume=0.65):
    """create a native one-shot node backed by a checked imported SoundWave."""
    asset_name = 's_bb_' + name
    path = '/Basketbroom/Audio/' + asset_name + '.' + asset_name
    asset = unreal.load_asset(path)
    if asset is none or not isinstance(asset, unreal.SoundWave):
        raise runtimeerror('missing basketbroom sound; run build_audio.build() first: ' + path)
    return g.call(GS+'PlaySound2D', sound=asset, volumemultiplier=volume,
                  PitchMultiplier=1.0, bisuisound=false)

def fresh(name, parent=unreal.Actor):
    path = base + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        # rebuild only the generated graph assets, after unloading the generated map.
        existing = unreal.load_asset(path)
        for graph in list(unreal.BlueprintEditorLibrary.list_graphs(existing)):
            if graph.get_name() not in ('eventgraph', 'UserConstructionScript'):
                unreal.BlueprintEditorLibrary.remove_graph(existing, graph)
                continue
            editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            if graph.get_name() == 'EventGraph':
                editor.remove_nodes(editor.list_all_nodes())
        g = graph(existing)
        for var in list(unreal.BlueprintEditorLibrary.list_member_variable_names(existing, False)):
            g.editor.remove_member_variable(var)
        return existing, g
    bp = create_blueprint(path, parent)
    return bp, graph(bp)

def make_manager():
    bp, g = fresh('bp_bbmatch')
    for name, kind, default in [('tealscore','int',0),('copperscore','int',0),('hasball','bool',false),
            ('matchover','bool',false),('secondsleft','double',300),('elapsed','double',0),('stun','double',0),
            ('snipedistance','double',0),('snitchdistance','double',0),
            ('snipeposition','vector',(0,0,0)),('snitchposition','vector',(0,0,0)),
            ('snipeprogress','double',0),('snitchprogress','double',0),
            ('snipeactive','bool',false),('snitchactive','bool',false),
            ('targetname','string','no chase target'),('targetdistance','double',0),
            ('catchprogress','double',0),('targetavailable','bool',false),
            ('message','string','training flight | find a ball. press e to carry it.')]:
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
    message = g.set('Message','TRAINING complete | press r for another flight')
    g.chain(live,countdown,end,over,message)
    reset = g.branch(key(g,'R'))
    reload = g.call(GS+'OpenLevel',LevelName='BB_Arena',bAbsolute=True)
    g.exec(seq,reset,'then_1'); g.exec(reset,reload)
    # preserve training's side/floor insets, with a spherical sloped-roof limit.
    # defaultpawn uses a 35cm sphere; read an existing authored broom's radius
    # when rebuilding so collision scale adjustments remain respected.
    broom_class = unreal.load_class(None, base + 'BP_BBBroom.BP_BBBroom_C')
    broom_radius = (unreal.get_default_object(broom_class).get_editor_property('collision_component').get_scaled_sphere_radius()
                    if broom_class is not none else 35.0)
    p = location(g,pawn(g)); x,y,z = xyz(g,p)
    x = math(g,'FClamp',Value=x,Min=-(dimensions.HALF_LENGTH-140.8),Max=dimensions.HALF_LENGTH-140.8)
    y = math(g,'FClamp',Value=y,Min=-(dimensions.HALF_WIDTH-110.4),Max=dimensions.HALF_WIDTH-110.4)
    clamp = setloc(g,vec(g,x,y,math(g,'fclamp',value=z,min=130,max=pyramid_limit(g,x,y,broom_radius))),pawn(g))
    g.exec(seq,clamp,'then_2')
    # each chase ball publishes its own sample; choosing here avoids tick-order
    # races from both balls clearing or overwriting a shared nearest-distance.
    available = both(g,either(g,g.get('SnipeActive'),g.get('SnitchActive')),neg(g,g.get('MatchOver')))
    pick_snipe = both(g,g.get('SnipeActive'),either(g,neg(g,g.get('SnitchActive')),
                       neg(g,gt(g,g.get('SnipeDistance'),g.get('SnitchDistance')))))
    target_name = math(g,'selectstring',a='snipe',b='snitch',bpicka=pick_snipe)
    target_distance = math(g,'SelectFloat',A=g.get('SnipeDistance'),B=g.get('SnitchDistance'),bPickA=pick_snipe)
    target_progress = math(g,'SelectFloat',A=g.get('SnipeProgress'),B=g.get('SnitchProgress'),bPickA=pick_snipe)
    target = g.set('TargetAvailable',available)
    g.exec(seq,target,'then_3')
    g.chain(target,g.set('TargetName',math(g,'SelectString',A=target_name,B='NO chase target',bpicka=available)),
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
    for name,kind,default in [('kind','int',0),('held','bool',false),('cooldown','double',0),('botowner','int',-1),('botposition','vector',(0,0,900)),
          ('catchtime','double',0),('p','vector',(0,0,0)),('oldp','vector',(0,0,0)),
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
    botfollow=setloc(g,pyramid_position(g,g.get('BotPosition'),ball_radius(g)))
    steal=g.branch(both(g,both(g,key(g,'E'),lt(g,math(g,'VSize',A=vsub(g,location(g),location(g,pawn(g)))),425)),neg(g,mg(g,'HasBall'))))
    g.chain(botheld,botfollow,steal,g.set('BotOwner',-1),g.set('Held',True),ms(g,'HasBall',True),ms(g,'Message','INTERCEPTION | possession won. left mouse to shoot.'),sound(g,'Catch'))
    # ordinary scoring balls: pickup, carry and release; one controlled ball at a time.
    held=g.branch(g.get('Held')); g.exec(classify,held)
    camrot=fn(g,'/Script/Engine.PlayerCameraManager.GetCameraRotation',target=camera(g))
    forward=math(g,'getforwardvector',inrot=camrot)
    right=math(g,'getrightvector',inrot=camrot)
    holdpos=vadd(g,location(g,pawn(g)),vadd(g,vmul(g,forward,175),vadd(g,vmul(g,right,72),vec(g,0,0,-48))))
    follow=setloc(g,pyramid_position(g,holdpos,ball_radius(g)))
    shoot=g.branch(either(g,key(g,'LeftMouseButton'),gt(g,mg(g,'Stun'),0)))
    release=g.set('Held',False); clear=ms(g,'hasball',false)
    impulse=g.set('Velocity',vadd(g,vmul(g,forward,4400),vmul(g,fn(g,ACTOR+'GetVelocity',target=pawn(g)),0.4)))
    delay=g.set('Cooldown',0.15)
    msg=ms(g,'message','ball released | bank shots stay live')
    g.chain(held,follow,shoot)
    g.chain(shoot,release,clear,impulse,delay,msg,sound(g,'Throw'))
    free=g.sequence(3); g.exec(held,free,'else')
    distance=math(g,'vsize',a=vsub(g,location(g),location(g,pawn(g))))
    take=g.branch(both(g,both(g,key(g,'E'),lt(g,distance,425)),both(g,neg(g,mg(g,'HasBall')),lt(g,g.get('Cooldown'),0.001))))
    grab=g.set('Held',True); occupy=ms(g,'hasball',true); stop=g.set('Velocity',(0,0,0))
    note=ms(g,'message','carrying | left mouse to shoot. aim through the matching hoop.')
    g.exec(free,take,'then_0'); g.chain(take,grab,occupy,stop,note,sound(g,'Catch'))
    # kinematic ball physics makes rebound/scoring deterministic and independent of frame rate.
    save=g.set('OldP',location(g)); pv=g.set('Velocity',vadd(g,g.get('Velocity'),vec(g,0,0,mul(g,-380,dt))))
    advance=g.set('P',vadd(g,location(g),vmul(g,g.get('Velocity'),dt)))
    surfaces=g.sequence(6)
    g.exec(free,save,'then_1'); g.chain(save,pv,advance,surfaces)
    # scoring is swept across each goal plane; whole-ball clearance required.
    for index,side in enumerate((1,-1)):
        px,py,pz=xyz(g,g.get('P')); ox,oy,oz=xyz(g,g.get('OldP'))
        radius=math(g,'SelectFloat',A=33,B=24,bPickA=eqi(g,g.get('Kind'),0))
        full_plane=add(g,dimensions.GOAL_PLANE_X,radius)
        crosses=both(g,lt(g,mul(g,ox,side),full_plane),gt(g,mul(g,px,side),full_plane))
        test=g.branch(crosses); g.exec(surfaces,test,'then_'+str(index))
        frac=div(g,sub(g,side*dimensions.GOAL_PLANE_X,ox),sub(g,px,ox))
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
            score_name='tealscore' if side==1 else 'copperscore'
            award=ms(g,score_name,math(g,'add_intint',a=mg(g,score_name),b=points))
            text=ms(g,'message',('quark +37 | small-hoop finish!' if isquark else 'quaffle +13 | clean through the hoop!'))
            resetp=g.set('P',g.get('Home')); resetv=g.set('Velocity',(0,0,0)); wait=g.set('Cooldown',1.0)
            g.exec(quark,award,'then' if isquark else 'else'); g.chain(award,text,resetp,resetv,wait,sound(g,'Score'))
    # Side/end nets preserve 75% normal incident speed.
    for axis,extent,out_index in [(0,dimensions.HALF_LENGTH,2),(1,dimensions.HALF_WIDTH,3)]:
        limit=sub(g,extent,ball_radius(g))
        coords=xyz(g,g.get('P')); vel=xyz(g,g.get('Velocity'))
        hit=g.branch(gt(g,math(g,'Abs',A=coords[axis]),limit))
        pos=list(coords); pos[axis]=math(g,'fclamp',value=coords[axis],min=mul(g,limit,-1),max=limit)
        newv=list(vel); newv[axis]=mul(g,vel[axis],-0.75)
        g.exec(surfaces,hit,'then_'+str(out_index)); g.chain(hit,g.set('P',vec(g,*pos)),g.set('Velocity',vec(g,*newv)),sound(g,'Bounce',0.16))
    coords=xyz(g,g.get('P')); vel=xyz(g,g.get('Velocity'))
    floor=g.branch(lt(g,coords[2],65))
    bounce=math(g,'FMax',A=390,B=mul(g,math(g,'Abs',A=vel[2]),0.75))
    g.exec(surfaces,floor,'then_4'); g.chain(floor,g.set('P',vec(g,coords[0],coords[1],65)),g.set('Velocity',vec(g,vel[0],vel[1],bounce)))
    # all four sloping roof faces rebound the same live ball, including above
    # the former 138ft threshold. the hollow eave has no horizontal collision.
    g.exec(surfaces,roof_rebounds(g),'then_5')
    apply=setloc(g,g.get('P')); g.exec(free,apply,'then_2')
    # chase balls use deterministic paths and a full 1-second capture window.
    chase=g.sequence(2); g.exec(classify,chase,'else')
    # the snipe traverses its route at 60% of the snitch's path rate.
    chase_rate=math(g,'SelectFloat',A=0.6,B=1.0,bPickA=eqi(g,g.get('Kind'),2))
    # longer paths retain their existing flight speeds and Snipe/Snitch ratio.
    t=div(g,mul(g,mg(g,'Elapsed'),chase_rate),dimensions.LINEAR_SCALE); phase=mul(g,g.get('Kind'),2.17)
    cx=mul(g,math(g,'Sin',A=add(g,mul(g,t,0.23),phase)),4300*dimensions.LINEAR_SCALE)
    cy=mul(g,math(g,'Cos',A=add(g,mul(g,t,0.41),phase)),2050*dimensions.LINEAR_SCALE)
    cz=add(g,2200*dimensions.LINEAR_SCALE,mul(g,math(g,'Sin',A=add(g,mul(g,t,0.32),phase)),950*dimensions.LINEAR_SCALE))
    g.exec(chase,setloc(g,vec(g,cx,cy,cz)),'then_0')
    near=both(g,neg(g,gt(g,math(g,'vsize',a=vsub(g,location(g),location(g,pawn(g)))),380)),both(g,key(g,'e',true),neg(g,mg(g,'hasball'))))
    catch=g.branch(near); g.exec(chase,catch,'then_1')
    accumulate=g.set('CatchTime',add(g,g.get('CatchTime'),dt)); captured=g.branch(neg(g,lt(g,g.get('CatchTime'),1)))
    g.chain(catch,accumulate,captured); g.exec(catch,g.set('CatchTime',0),'else')
    is_snipe=g.branch(eqi(g,g.get('Kind'),2)); g.chain(captured,sound(g,'Catch'),is_snipe)
    g.chain(is_snipe,ms(g,'TealScore',math(g,'Add_IntInt',A=mg(g,'TealScore'),B=69)),g.set('Cooldown',180),g.set('CatchTime',0),setloc(g,(0,0,-3000)),ms(g,'Message','SNIPE +69 | returns in three minutes'))
    snitch=ms(g,'tealscore',math(g,'add_intint',a=mg(g,'tealscore'),b=150))
    g.exec(is_snipe,snitch,'else'); g.chain(snitch,ms(g,'MatchOver',True),ms(g,'Message','SNITCH +150 | training complete. press r to restart.'))
    # run after the gameplay branch even during cooldown, so a caught snipe
    # cannot leave a stale target or capture meter visible for three minutes.
    report=g.branch(either(g,eqi(g,g.get('Kind'),2),eqi(g,g.get('Kind'),3)))
    g.exec(updates,report,'then_1')
    report_snipe=g.branch(eqi(g,g.get('Kind'),2)); g.exec(report,report_snipe)
    active=both(g,lt(g,g.get('Cooldown'),0.001),neg(g,mg(g,'MatchOver')))
    chase_distance=math(g,'vsize',a=vsub(g,location(g),location(g,pawn(g))))
    capture_progress=math(g,'SelectFloat',A=math(g,'FClamp',Value=g.get('CatchTime'),Min=0,Max=1),B=0,bPickA=active)
    for prefix,output in [('Snipe','then'),('Snitch','else')]:
        publish=ms(g,prefix+'active',active)
        g.exec(report_snipe,publish,output)
        g.chain(publish,ms(g,prefix+'Distance',chase_distance),ms(g,prefix+'Progress',capture_progress),
                ms(g,prefix+'position',location(g)))
    g.compile(save=True)
    return bp

def make_pawn():
    bp,g=fresh('BP_BBBroom',unreal.DefaultPawn)
    # floatingpawnmovement supplies acceleration; explicit inputs keep e free for catches.
    tick=g.event('ReceiveTick')
    seq=g.sequence(8); g.exec(tick,seq)
    mouse=g.call(PC+'GetInputMouseDelta',target=controller(g))
    yaw=g.call('/Script/Engine.Pawn.AddControllerYawInput',Val=mul(g,g.out(mouse,'DeltaX'),0.14))
    pitch=g.call('/Script/Engine.Pawn.AddControllerPitchInput',Val=mul(g,g.out(mouse,'DeltaY'),-0.14))
    g.exec(seq,yaw,'then_0'); g.exec(seq,pitch,'then_1')
    rot=fn(g,'/Script/Engine.Pawn.GetControlRotation')
    forward=math(g,'getforwardvector',inrot=rot)
    right=math(g,'getrightvector',inrot=rot)
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
    result=build()
