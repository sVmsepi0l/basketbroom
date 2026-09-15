"""Original, deterministic 3-D scenery for Basketbroom's two regulation venues.

Offline: python Tools/build_arena_environments.py --generate
No Unreal packages, existing arena sources, sporting geometry or maps are edited.
Mesh units are centimetres, Z up. Source meshes remain native-kit importable OBJ.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import random

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'SourceArt/Environments'
_spec = importlib.util.spec_from_file_location('_bb_venue_dimensions', Path(__file__).with_name('arena_dimensions.py'))
dim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dim)
VERSION = 1
TAG = 'BB.Environment.v1'
MAPS = {'redrock': '/Basketbroom/Maps/BB_Redrock', 'redwoods': '/Basketbroom/Maps/BB_Redwoods'}


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def norm(a):
    length = math.sqrt(sum(v*v for v in a))
    return tuple(v/length for v in a) if length else (0., 0., 1.)


class Mesh:
    def __init__(self):
        self.vertices, self.faces = [], []

    def vertex(self, point):
        self.vertices.append(tuple(float(v) for v in point))
        return len(self.vertices)

    def face(self, *points):
        for i in range(1, len(points)-1):
            self.faces.append((points[0], points[i], points[i+1]))

    def box(self, center, size):
        b = len(self.vertices)+1
        for z in (-1, 1):
            for x, y in ((-1,-1),(1,-1),(1,1),(-1,1)):
                self.vertex(tuple(center[k]+(x,y,z)[k]*size[k]/2 for k in range(3)))
        for f in ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            self.face(*(b+i for i in f))

    def tube(self, start, end, radius, end_radius=None, sides=12, flutes=0., phase=0.):
        axis = norm(tuple(end[k]-start[k] for k in range(3)))
        u = norm(cross(axis, (0,0,1) if abs(axis[2])<.9 else (0,1,0)))
        v = cross(axis,u)
        base=len(self.vertices)+1
        for c,r in ((start,radius),(end,radius if end_radius is None else end_radius)):
            for j in range(sides):
                a=math.tau*j/sides+phase
                rr=r*(1+flutes*(.7*math.cos(9*a)+.3*math.cos(15*a+.3)))
                self.vertex(tuple(c[k]+rr*(u[k]*math.cos(a)+v[k]*math.sin(a)) for k in range(3)))
        for j in range(sides):
            self.face(base+j,base+(j+1)%sides,base+sides+(j+1)%sides,base+sides+j)
        self.face(*(base+j for j in reversed(range(sides))))
        self.face(*(base+sides+j for j in range(sides)))

    def ellipsoid(self, c, size, seed=0, sides=18, rings=10, roughness=.1):
        base=len(self.vertices)+1
        # Offset poles avoids zero-area triangles while keeping a natural tip.
        for j in range(rings+1):
            p=math.pi*(.002+.996*j/rings)
            for i in range(sides):
                a=math.tau*i/sides
                warp=1+roughness*(.55*math.sin(a*5+p*8+seed)+.3*math.cos(a*9-p*4+seed))
                self.vertex((c[0]+size[0]*math.sin(p)*math.cos(a)*warp,
                             c[1]+size[1]*math.sin(p)*math.sin(a)*warp,
                             c[2]+size[2]*math.cos(p)*warp))
        for j in range(rings):
            for i in range(sides):
                a=base+j*sides+i;b=base+j*sides+(i+1)%sides
                self.face(a,a+sides,b+sides,b)
        self.face(*(base+i for i in range(sides)))
        self.face(*(base+rings*sides+i for i in reversed(range(sides))))

    def save(self, name):
        path=OUTPUT/'Meshes'/(name+'.obj');path.parent.mkdir(parents=True,exist_ok=True)
        lines=['# Basketbroom original 3D environment. Centimetres, Z up.', 'o '+name, 's 1']
        lines += ['v %.5f %.5f %.5f'%p for p in self.vertices]
        # Stable object-space projection exists for generic import; materials
        # use world projection to retain physical detail at every instance scale.
        lines += ['vt %.6f %.6f'%(p[0]/1000,p[2]/1000) for p in self.vertices]
        lines += ['f '+' '.join('%d/%d'%(v,v) for v in f) for f in self.faces]
        text='\n'.join(lines)+'\n'
        if not path.exists() or path.read_text(encoding='ascii') != text:
            path.write_text(text,encoding='ascii',newline='\n')
        return {'name':name,'file':path.relative_to(OUTPUT).as_posix(), 'vertices':len(self.vertices),
                'triangles':len(self.faces), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'bounds':[[min(v[k] for v in self.vertices) for k in range(3)],
                          [max(v[k] for v in self.vertices) for k in range(3)]]}


PALETTE = {
 'Sandstone': {'color':[.45,.15,.062], 'roughness':.91, 'texture':'T_BB_RedSandstone_Albedo', 'texture_cm':850},
 'SandstoneLight': {'color':[.63,.28,.13], 'roughness':.92, 'texture':'T_BB_RedSandstone_Albedo', 'texture_cm':850},
 'SandstoneDark': {'color':[.28,.075,.027], 'roughness':.94, 'texture':'T_BB_RedSandstone_Albedo', 'texture_cm':850},
 'Adobe': {'color':[.58,.35,.19], 'roughness':.97, 'texture':'T_BB_Adobe_Albedo', 'texture_cm':250},
 'AdobeLight': {'color':[.73,.49,.27], 'roughness':.98, 'texture':'T_BB_Adobe_Albedo', 'texture_cm':250},
 'Timber': {'color':[.13,.061,.023], 'roughness':.91, 'texture':'T_BB_RedwoodBark_Albedo', 'texture_cm':180},
 'DoorShadow': {'color':[.023,.013,.009], 'roughness':1.},
 'Sage': {'color':[.15,.20,.11], 'roughness':.97},
 'Needles': {'color':[.024,.12,.071], 'roughness':.93, 'foliage':True},
 'NeedlesLight': {'color':[.05,.21,.11], 'roughness':.94, 'foliage':True},
 'Bark': {'color':[.27,.105,.047], 'roughness':.96, 'texture':'T_BB_RedwoodBark_Albedo', 'texture_cm':320},
 'BarkDark': {'color':[.115,.048,.024], 'roughness':.98, 'texture':'T_BB_RedwoodBark_Albedo', 'texture_cm':320},
 'Moss': {'color':[.062,.135,.06], 'roughness':1.},
 'BasaltCoast': {'color':[.07,.095,.095], 'roughness':.94},
 'ForestFloor': {'color':[.048,.067,.033], 'roughness':1.},
 'Sea': {'color':[.023,.18,.20], 'roughness':.27, 'metallic':.12, 'water':True},
 'Foam': {'color':[.49,.67,.60], 'roughness':.78},
}


class Venue:
    def __init__(self, name):
        self.name=name;self.meshes={};self.instances=[]

    def mesh(self, short, material):
        name='SM_BB_ENV_'+short
        self.meshes[name]={'mesh':Mesh(),'material':material}
        return self.meshes[name]['mesh']

    def place(self, short, label, location=(0,0,0), scale=(1,1,1), yaw=0, shadow=True):
        name='SM_BB_ENV_'+short
        self.instances.append({'label':label,'mesh':name,'material':self.meshes[name]['material'],
             'location':list(location),'scale':list(scale),'yaw':yaw,'cast_shadow':shadow,'collision':'NoCollision'})

    def finish(self):
        return {'id':self.name, 'map':MAPS[self.name], 'meshes':[dict(v['mesh'].save(k),material=v['material']) for k,v in self.meshes.items()],
                'instances':self.instances}


def redrock():
    v=Venue('redrock')
    # Seven separately coloured depositional beds wrap a deep U-shaped alcove.
    # The open mouth faces -Y; its walls and underside clear the full cage.
    colors=('SandstoneDark','Sandstone','SandstoneLight','Sandstone','SandstoneDark','SandstoneLight','Sandstone')
    for layer,mat in enumerate(colors):
        mesh=v.mesh('RR_AlcoveBed%d'%layer,mat)
        za=-1800+layer*2800;zb=za+2800
        rows=5;segments=120;base=len(mesh.vertices)+1
        for j in range(rows+1):
            z=za+(zb-za)*j/rows
            for i in range(segments+1):
                a=-.12+(math.pi+.24)*i/segments
                und=.045*math.sin(9*a+z*.0005)+.021*math.cos(21*a-z*.0004)
                radial=1+und+.055*math.sin(z*.002)+.024*math.sin(z*.007)
                x=19000*math.cos(a)*radial
                y=2500+15000*math.sin(a)*radial
                mesh.vertex((x,y,z+160*math.sin(a*5+layer)))
        for j in range(rows):
            for i in range(segments):
                a=base+j*(segments+1)+i
                mesh.face(a,a+segments+1,a+segments+2,a+1)
        v.place('RR_AlcoveBed%d'%layer,'redrock / stratified alcove bed %02d'%layer)
    # A broad cap of red sandstone projects over the court. It is a real
    # closed slab with a sculpted soffit, not a plane or scenic billboard.
    roof=v.mesh('RR_Overhang','Sandstone')
    nx,ny=68,42
    for upper in (False,True):
        for j in range(ny+1):
            t=j/ny
            for i in range(nx+1):
                s=i/nx;x=-18800+37600*s
                front=-7800+1100*math.sin(s*math.pi*5)+650*math.cos(s*math.pi*11)
                y=front+(17700-front)*t
                z=10800+700*math.sin(s*math.pi*3)+350*math.cos(t*math.pi*5+s*7)
                z+=500*t+((4700+850*math.sin(s*12+t*7)) if upper else 0)
                roof.vertex((x,y,z))
    sheet=(nx+1)*(ny+1)
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i+1
            roof.face(a,a+nx+1,a+nx+2,a+1)
            roof.face(a+sheet,a+1+sheet,a+nx+2+sheet,a+nx+1+sheet)
    border=list(range(1,nx+2))+[(j+1)*(nx+1) for j in range(1,ny+1)]+[ny*(nx+1)+i for i in range(nx,0,-1)]+[j*(nx+1)+1 for j in range(ny-1,0,-1)]
    for a,b in zip(border,border[1:]+border[:1]):roof.face(a,b,b+sheet,a+sheet)
    v.place('RR_Overhang','redrock / great sculpted cliff overhang')
    # Broad canyon strata recede past the arena mouth in world space.
    rng=random.Random(4422)
    mesa=v.mesh('RR_DistantMesa','SandstoneLight')
    for k in range(12):
        x=-65000+k*11500;y=-55000-rng.uniform(0,15000)
        height=rng.uniform(5000,12000)
        mesa.ellipsoid((x,y,-1800+height*.5),(6500,rng.uniform(4500,8500),height),k,30,13,.16)
    v.place('RR_DistantMesa','redrock / distant canyon mesas',shadow=False)
    # A sandstone terrace supports the court while keeping the rebound floor.
    terrace=v.mesh('RR_Terrace','SandstoneDark')
    terrace.ellipsoid((0,1800,-4700),(17000,17000,4100),22,76,20,.045)
    v.place('RR_Terrace','redrock / canyon terrace')
    adobe=v.mesh('RR_AdobeRooms','Adobe');plaster=v.mesh('RR_AdobeParapets','AdobeLight')
    dark=v.mesh('RR_Recesses','DoorShadow');wood=v.mesh('RR_VigasLadders','Timber')
    for row in range(3):
        y=7800+row*2050
        for col in range(14):
            if row==2 and col in (0,13):continue
            x=-12800+col*1950+rng.uniform(-110,110)
            w=rng.uniform(1550,1930);depth=1900;h=rng.uniform(1100,1650)
            basez=row*850-300
            adobe.box((x,y,basez+h/2),(w,depth,h))
            # Thin contrasting coping and side parapets emphasize roof terraces.
            for xx in (x-w/2+55,x+w/2-55):plaster.box((xx,y,basez+h+95),(110,depth,190))
            plaster.box((x,y+depth/2-60,basez+h+95),(w,120,190))
            # Door and window recesses sit behind raised lintels in the facade.
            front=y-depth/2-3
            dark.box((x,front,basez+395),(310,12,650))
            plaster.box((x,front-20,basez+750),(420,80,110))
            for side in (-1,1):
                dark.box((x+side*w*.31,front,basez+h*.68),(220,12,260))
            for beam in range(5):
                xx=x-w*.4+beam*w*.2
                wood.tube((xx,y-depth/2-140,basez+h-120),(xx,y+depth/2+80,basez+h-120),50,sides=9)
            if (row+col)%3==0:
                bx=x+w*.3;ly=y-depth/2-170
                for side in (-1,1):wood.tube((bx+side*130,ly-200,basez),(bx+side*130,ly+30,basez+h+300),27,sides=8)
                for rung in range(9):
                    z=basez+(rung+1)*(h+230)/10
                    yy=ly-200+(z-basez)/(h+300)*230
                    wood.tube((bx-150,yy,z),(bx+150,yy,z),20,sides=7)
    # Round masonry lookout towers and roof-access openings flank the village.
    for side in (-1,1):
        x=side*14700;y=8100
        adobe.tube((x,y,-250),(x,y,3400),1100,990,48)
        plaster.tube((x,y,3330),(x,y,3550),1100,1090,48)
        dark.box((x,y-1103,800),(430,30,1550))
    for name,label in [('RR_AdobeRooms','terraced pueblo rooms'),('RR_AdobeParapets','adobe roof coping'),('RR_Recesses','recessed doors and windows'),('RR_VigasLadders','timber vigas and roof ladders')]:v.place(name,'redrock / '+label)
    rubble=v.mesh('RR_Talus','SandstoneLight');sage=v.mesh('RR_Sage','Sage')
    for k in range(110):
        side=rng.choice((-1,1));x=side*rng.uniform(10800,17000);y=rng.uniform(-6500,6600)
        rubble.ellipsoid((x,y,-200),(rng.uniform(130,650),rng.uniform(100,400),rng.uniform(120,510)),k,12,6,.22)
        if k%3==0:sage.ellipsoid((x+180,y,-20),(210,180,165),k,12,6,.28)
    v.place('RR_Talus','redrock / sandstone talus');v.place('RR_Sage','redrock / sagebrush')
    return v


def redwood_tree(v,index):
    rng=random.Random(700+index)
    bark=v.mesh('RW_Trunk%d'%index,'Bark' if index%2==0 else 'BarkDark')
    leaves=v.mesh('RW_Crown%d'%index,'Needles' if index%2==0 else 'NeedlesLight')
    height=13600+index*750;radius=490+index*75
    # Fluted, tapered bole; each ring shares vertices for continuous normals.
    levels=32;sides=52
    for j in range(levels+1):
        t=j/levels;z=t*height
        rr=radius*(1-.84*t)+radius*.58*math.exp(-t*16)
        cx=160*math.sin(t*2.6+index)-160*math.sin(index);cy=115*math.sin(t*3.7)
        for i in range(sides):
            a=math.tau*i/sides
            r=rr*(1+.13*math.cos(a*9)+.04*math.sin(a*17+z*.002))
            bark.vertex((cx+r*math.cos(a),cy+r*math.sin(a),z))
    for j in range(levels):
        for i in range(sides):
            a=j*sides+i+1;b=j*sides+(i+1)%sides+1
            bark.face(a,b,b+sides,a+sides)
    # Buttress roots flow into the duff instead of ending as a cylinder.
    for k in range(11):
        a=math.tau*k/11+rng.uniform(-.1,.1)
        bark.tube((math.cos(a)*radius*.48,math.sin(a)*radius*.48,1100),
                  (math.cos(a)*radius*3.1,math.sin(a)*radius*3.1,-80),radius*.36,65,11)
    # Asymmetric, tiered boughs with narrow clusters of geometric needles.
    # These are 3D leaf sprays, avoiding alpha-card overdraw.
    for tier in range(12):
        t=.47+tier*.042;z=t*height
        extent=(height*.20)*(1-t*.70)
        for branch in range(5):
            a=tier*1.91+branch*math.tau/5+rng.uniform(-.25,.25)
            length=extent*rng.uniform(.72,1.15)
            start=(0,0,z);end=(math.cos(a)*length,math.sin(a)*length,z+length*.14)
            bark.tube(start,end,max(32,105*(1-t)),14,9)
            for cluster in range(4):
                f=.36+cluster*.19
                c=(end[0]*f,end[1]*f,z+length*.14*f+170)
                leaves.ellipsoid(c,(length*.27,length*.21,250+length*.13),index+tier+branch+cluster,13,7,.26)
    leaves.ellipsoid((0,0,height-150),(500,550,1000),index,15,10,.16)


def redwoods():
    v=Venue('redwoods');rng=random.Random(8392)
    for index in range(3):redwood_tree(v,index)
    # Open sea lies south (-Y); the grove wraps behind and around the arena.
    positions=[]
    for row in range(3):
        for column in range(11):
            positions.append((-25000+column*4900+rng.uniform(-650,650),9700+row*6800+rng.uniform(-900,900)))
    for side in (-1,1):
        for k in range(8):positions.append((side*(15000+(k%3)*3900),-8100+(k//3)*4300+rng.uniform(-700,700)))
    for k,(x,y) in enumerate(positions):
        variant=k%3;scale=rng.uniform(.88,1.27);yaw=rng.uniform(0,360)
        for part in ('Trunk','Crown'):
            v.place('RW_'+part+str(variant),'redwoods / old growth %02d %s'%(k,part.lower()),(x,y,-500),(scale,scale,scale),yaw,shadow=part=='Trunk')
    floor=v.mesh('RW_ForestShelf','ForestFloor')
    # The forest bluff projects below the arena, with a scalloped cliff edge.
    nx,ny=60,40
    for j in range(ny+1):
        for i in range(nx+1):
            x=-39000+i*78000/nx;y=-10800+j*50000/ny
            z=-660+60*math.sin(x*.0007)*math.sin(y*.0008)
            floor.vertex((x,y,z))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i+1;floor.face(a,a+1,a+nx+2,a+nx+1)
    v.place('RW_ForestShelf','redwoods / coastal forest shelf')
    cliff=v.mesh('RW_CoastalBluff','BasaltCoast')
    for layer in range(8):
        z=-520-layer*1150
        for i in range(73):
            x=-42000+i*84000/72
            y=-10500+700*math.sin(x*.00042)+330*math.sin(x*.0017)+layer*420
            cliff.vertex((x,y,z+250*math.sin(x*.0003+layer)))
    for j in range(7):
        for i in range(72):
            a=j*73+i+1;cliff.face(a,a+73,a+74,a+1)
    v.place('RW_CoastalBluff','redwoods / weathered sea cliff')
    sea=v.mesh('RW_Ocean','Sea');nx,ny=100,80
    for j in range(ny+1):
        for i in range(nx+1):
            x=-220000+i*440000/nx;y=-8500-j*230000/ny
            z=-6100+55*math.sin(x*.00024+y*.00033)+24*math.sin(x*.00061-y*.00043)
            sea.vertex((x,y,z))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i+1;sea.face(a,a+nx+1,a+nx+2,a+1)
    v.place('RW_Ocean','redwoods / pacific ocean surface',shadow=False)
    stack=v.mesh('RW_SeaStacks','BasaltCoast');foam=v.mesh('RW_Surf','Foam')
    for k in range(17):
        x=rng.uniform(-95000,95000);y=rng.uniform(-85000,-21000)
        size=(rng.uniform(1700,4000),rng.uniform(1900,4000),rng.uniform(1700,3600))
        stack.ellipsoid((x,y,-5100),size,k,25,14,.21)
        # Geometric breaker crests around stack bases, slightly above sea.
        for arc in range(3):
            for aidx in range(26):
                a=aidx*math.tau/26; b=(aidx+1)*math.tau/26
                r=max(size[:2])*(1.02+arc*.22)
                foam.tube((x+r*math.cos(a),y+r*.75*math.sin(a),-6030),
                          (x+r*math.cos(b),y+r*.75*math.sin(b),-6030),22+arc*6, sides=4)
    v.place('RW_SeaStacks','redwoods / basalt sea stacks');v.place('RW_Surf','redwoods / distant breakers',shadow=False)
    moss=v.mesh('RW_MossRocks','Moss');fern=v.mesh('RW_Ferns','NeedlesLight')
    for k in range(170):
        x,y=rng.uniform(-28000,28000),rng.uniform(-9000,28000)
        if abs(x)<10800 and y<7000:continue
        if k%3==0:moss.ellipsoid((x,y,-480),(rng.uniform(220,800),rng.uniform(190,620),rng.uniform(180,600)),k,15,8,.2)
        for blade in range(7):
            a=blade*math.tau/7+k;length=rng.uniform(250,440)
            for leaf in range(7):
                t=(leaf+1)/8;c=(x+math.cos(a)*length*t,y+math.sin(a)*length*t,-510+math.sin(t*math.pi*.9)*length*.7)
                w=length*.15*(1-t*.65)
                p=fern.vertex(c)
                q=fern.vertex((c[0]+math.cos(a+.9)*w,c[1]+math.sin(a+.9)*w,c[2]+12))
                r=fern.vertex((c[0]+math.cos(a)*w*.5,c[1]+math.sin(a)*w*.5,c[2]+25))
                s=fern.vertex((c[0]+math.cos(a-.9)*w,c[1]+math.sin(a-.9)*w,c[2]+12))
                fern.face(p,q,r);fern.face(p,r,s)
    v.place('RW_MossRocks','redwoods / mossy boulder floor');v.place('RW_Ferns','redwoods / sword fern understory',shadow=False)
    log=v.mesh('RW_FallenLog','BarkDark');log.tube((-2800,0,270),(2800,0,410),410,320,32,flutes=.1)
    v.place('RW_FallenLog','redwoods / fallen giant',(13300,2500,-350),yaw=27)
    return v


def transformed(p, item):
    q=[p[k]*item['scale'][k] for k in range(3)];a=math.radians(item['yaw'])
    return (q[0]*math.cos(a)-q[1]*math.sin(a)+item['location'][0],
            q[0]*math.sin(a)+q[1]*math.cos(a)+item['location'][1],q[2]+item['location'][2])


def triangle_intersects_box(points, center, half):
    """Separating-axis triangle/AABB test; used to reject decorative intrusion."""
    p=[tuple(v[k]-center[k] for k in range(3)) for v in points]
    edges=[tuple(p[(i+1)%3][k]-p[i][k] for k in range(3)) for i in range(3)]
    axes=[(1,0,0),(0,1,0),(0,0,1),cross(edges[0],edges[1])]
    axes += [cross(e, a) for e in edges for a in ((1,0,0),(0,1,0),(0,0,1))]
    for axis in axes:
        if sum(x*x for x in axis)<1e-16:continue
        values=[sum(v[k]*axis[k] for k in range(3)) for v in p]
        radius=sum(abs(axis[k])*half[k] for k in range(3))
        if min(values)>radius or max(values)<-radius:return False
    return True


def validate_venue(v):
    # Deliberately larger than the real pyramid: the whole rectangular envelope
    # plus 250 cm over the apex remains empty, keeping sight and net clearance.
    top=dim.APEX_HEIGHT+250;bottom=-50
    center=(0,0,(top+bottom)/2);half=(dim.HALF_LENGTH+150,dim.HALF_WIDTH+150,(top-bottom)/2)
    checked=0
    for item in v.instances:
        mesh=v.meshes[item['mesh']]['mesh'];verts=[transformed(p,item) for p in mesh.vertices]
        for face in mesh.faces:
            points=[verts[i-1] for i in face]
            if triangle_intersects_box(points,center,half):
                raise ValueError('Scenery intersects protected arena envelope: '+item['label'])
            checked+=1
    return {'triangles_checked':checked,'protected_box_min':[-half[0],-half[1],bottom],
            'protected_box_max':[half[0],half[1],top], 'decorative_intrusions':0}


def generate():
    venues=[redrock(),redwoods()]
    manifest={'schema':VERSION,'units':'centimetres_z_up','ownership_tag':TAG,
       'source_map':'/Basketbroom/Maps/BB_Regulation','sporting_dimensions':dim.dimensions(),
       'materials':PALETTE,'venues':[],'collision':'Environment instances use NoCollision; existing sporting collision is preserved.',
       'native_status':'Original source ready for native import; this manifest does not claim native map or match integration.'}
    for venue in venues:
        audit=validate_venue(venue);record=venue.finish();record['clearance_audit']=audit
        manifest['venues'].append(record)
    path=OUTPUT/'environments_manifest.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generate',action='store_true');args=parser.parse_args()
    if not args.generate:parser.error('Use --generate')
    result=generate()
    print(json.dumps({'status':'generated','venues':[{'id':v['id'],'meshes':len(v['meshes']),'instances':len(v['instances']),
             'source_triangles':sum(m['triangles'] for m in v['meshes']), 'clearance':v['clearance_audit']} for v in result['venues']]}))
