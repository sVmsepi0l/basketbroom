"""author original basketbroom broom and wand meshes, in centimeters.

run outside Unreal: python Tools/build_broom_equipment.py --generate-source
no downloads, copied game meshes, editor writes, gameplay or map changes.
the obj exports compensate for the ue legacy importer's y reflection. the
manifest records both source bounds and intended unreal bounds.
"""
from pathlib import path
import hashlib
import json
import math
import sys

root = Path(__file__).resolve().parents[1]
source = root / "SourceArt/Equipment"
mount = "/Basketbroom/Art/Equipment"
generator = "Basketbroom.FlightEquipment.v1"
materials = {
    "Wood": {"name": "m_bb_equipwood", "color": [.205, .077, .027], "roughness": .49, "metallic": .0, "grain": .15},
    "Leather": {"name": "m_bb_equipleather", "color": [.037, .024, .017], "roughness": .73, "metallic": .0, "grain": .055},
    "Bristles": {"name": "m_bb_equipbristles", "color": [.26, .158, .060], "roughness": .84, "metallic": .0, "grain": .10},
    "Copper": {"name": "m_bb_equipcopper", "color": [.43, .196, .066], "roughness": .38, "metallic": .78, "grain": .025},
}


def add(a, b): return tuple(a[i] + b[i] for i in range(3))
def sub(a, b): return tuple(a[i] - b[i] for i in range(3))
def scale(a, value): return tuple(x*value for x in a)
def dot(a, b): return sum(a[i]*b[i] for i in range(3))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def length(a): return math.sqrt(dot(a, a))
def unit(a):
    distance = length(a)
    if distance < 1e-9: raise valueerror("zero-length equipment tangent")
    return scale(a, 1/distance)


def catmull(points, subdivisions=4):
    """sample a clamped catmull-rom centerline without extrapolating endpoints."""
    result = []
    for i in range(len(points)-1):
        a, b, c, d = points[max(0, i-1)], points[i], points[i+1], points[min(len(points)-1, i+2)]
        for j in range(subdivisions):
            t = j/subdivisions
            result.append(tuple(.5*((2*b[k]) + (-a[k]+c[k])*t +
                (2*a[k]-5*b[k]+4*c[k]-d[k])*t*t + (-a[k]+3*b[k]-3*c[k]+d[k])*t*t*t) for k in range(3)))
    return result + [tuple(points[-1])]


class Mesh:
    """closed swept tubes with longitudinal uvs; one material/draw per layer."""
    def __init__(self):
        self.vertices, self.uvs, self.faces = [], [], []

    def vertex(self, point, uv):
        self.vertices.append(tuple(point)); self.uvs.append(tuple(uv))
        return len(self.vertices)

    def tube(self, points, radii, sides=10, ellipse=1.0):
        if len(points) < 2: raise valueerror("tube needs two distinct centers")
        if isinstance(radii, (int, float)): radii = [float(radii)]*len(points)
        if len(radii) != len(points) or min(radii) <= 0: raise valueerror("invalid tube radius")
        rings, distance = [], 0.0
        previous_u = none
        for i, center in enumerate(points):
            tangent = unit(sub(points[min(i+1, len(points)-1)], points[max(0, i-1)]))
            seed = (0., 0., 1.) if abs(tangent[2]) < .9 else (0., 1., 0.)
            u = unit(cross(tangent, seed))
            if previous_u is not none and dot(u, previous_u) < 0: u = scale(u, -1.)
            v = cross(tangent, u); previous_u = u
            if i: distance += length(sub(center, points[i-1]))
            ring = []
            for j in range(sides+1):
                angle = math.tau*j/sides
                offset = add(scale(u, math.cos(angle)*radii[i]), scale(v, math.sin(angle)*radii[i]*ellipse))
                ring.append(self.vertex(add(center, offset), (j/sides, distance/10.)))
            rings.append(ring)
        for a, b in zip(rings, rings[1:]):
            for j in range(sides): self.faces.append((a[j], a[j+1], b[j+1], b[j]))
        self.faces.extend((tuple(reversed(rings[0][:-1])), tuple(rings[-1][:-1])))

    def line(self, a, b, radius, sides=8): self.tube([a, b], radius, sides)

    def band(self, x, y, z, radius, width, sides=16):
        self.tube([(x-width/2, y, z), (x+width/2, y, z)], radius, sides)

    def helix(self, start, end, center_y, center_z, radius, turns, thickness, steps_per_turn=14):
        count = max(3, int(turns*steps_per_turn))
        points = [(start+(end-start)*i/count, center_y+radius*math.cos(math.tau*turns*i/count),
                   center_z+radius*math.sin(math.tau*turns*i/count)) for i in range(count+1)]
        self.tube(points, thickness, 5)

    def save(self, name, material):
        path = source / (name + ".obj")
        lines = ["# original basketbroom flight equipment; cm, z up; unreal y = -obj y", "o " + name, "s 1"]
        # reflect vertex y and reverse winding together; this preserves normals
        # after unreal performs its documented importer coordinate conversion.
        lines.extend("v %.6f %.6f %.6f" % (x, -y, z) for x, y, z in self.vertices)
        lines.extend("vt %.6f %.6f" % uv for uv in self.uvs)
        lines.extend("f " + " ".join("%d/%d" % (v, v) for v in reversed(face)) for face in self.faces)
        path.write_text("\n".join(lines)+"\n", encoding="ascii")
        triangles = sum(len(f)-2 for f in self.faces)
        bounds = [[min(p[i] for p in self.vertices) for i in range(3)],
                  [max(p[i] for p in self.vertices) for i in range(3)]]
        return {"name": name, "file": path.relative_to(ROOT).as_posix(), "material": material,
                "vertices": len(self.vertices), "polygons": len(self.faces), "triangles": triangles,
                "ue_bounds_cm": bounds, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def broom():
    wood, leather, bristles, copper, accent = (mesh() for _ in range(5))
    # swept solid timber, with the original saddle and grip mounting coordinates.
    centers = catmull([(-119, 0, -8), (-89, 0, -10), (-28, 0, -9), (43, 0, -8),
                      (99, 0, -6), (145, 0, -1.5), (165, 0, 2)], 4)
    wood.tube(centers, [3.55-(i/(len(centers)-1))*1.3 for i in range(len(centers))], 12, .93)
    wood.tube(catmull([(43, 0, -8), (43, 0, -2), (43, 0, 7)], 3), 2.15, 10)
    wood.tube(catmull([(43, -18, 7), (43, -8, 7), (43, 0, 7), (43, 8, 7), (43, 18, 7)], 2), 2.7, 12)
    # small oval saddle pad sits on the spar, not inside the animated pelvis.
    leather.tube(catmull([(-21, 0, -5.5), (-14, 0, -5.0), (8, 0, -4.7), (23, 0, -5.0)], 3),
                 [3.3, 4.3, 5.2, 5.8, 6.0, 6.0, 6.0, 5.7, 5.0, 4.0], 12, .44)
    for sign in (-1, 1):
        leather.tube([(43, sign*4.5, 7), (43, sign*16.8, 7)], 3.05, 12)
        # fine raised seams across each hand grip.
        for index in range(6):
            y = sign*(5.3+index*2.02)
            copper.tube([(43, y-.16, 7), (43, y+.16, 7)], 3.11, 12)
    leather.band(-104, 0, -8.5, 6.2, 12, 18)
    leather.band(-120, 0, -9.5, 9.0, 7, 18)
    leather.helix(-124, -98, 0, -8.5, 6.8, 7, .48)
    for x, z, radius in ((-98, -8.5, 6.45), (-111, -9., 7.3), (-124, -9.5, 9.35), (98, -6, 3.48), (139, -2., 3.15)):
        copper.band(x, 0, z, radius, 1.1, 18)
    # three layers of individually separated reeds. no opaque cone shell.
    for layer, count, reach, spread in ((0, 9, 75, 9), (1, 14, 87, 15), (2, 19, 100, 20)):
        for index in range(count):
            angle = math.tau*index/count + layer*.41
            variation = math.sin(index*2.39996+layer)*3.6
            points = []
            for step in range(6):
                t = step/5.
                flare = (2.4+layer*1.75)*(1-t) + spread*math.sin(t*math.pi*.69)
                points.append((-106-(reach+variation)*t,
                    math.cos(angle)*flare + math.sin(t*math.pi)*math.sin(angle*3)*.9,
                    -8.5+math.sin(angle)*flare-7*t*t))
            bristles.tube(points, [1.6-layer*.10, 1.63, 1.55, 1.30, .83, .18], 7, .8)
    # twin open footrests match the authored quinn soles at approximately -60.
    for sign in (-1, 1):
        copper.tube(catmull([(4, sign*2, -10), (8, sign*13, -28), (16, sign*21, -54),
                           (24, sign*22, -60)], 3), 1.25, 8)
        copper.tube(catmull([(13, sign*17, -60), (17, sign*28, -60),
                           (40, sign*28, -60), (44, sign*17, -60)], 3), 1.55, 8)
        for x in (22, 28, 34): copper.line((x, sign*17, -60), (x, sign*28, -60), .7, 6)
        # two small team-painted heel plates and a narrow shaft band.
        accent.line((17, sign*25.5, -58.5), (38, sign*25.5, -58.5), 1., 8)
    accent.band(106, 0, -5.1, 3.45, 8., 18)
    accent.band(-113, 0, -9., 7.65, 3., 18)
    return (("sm_bb_broomwood", wood, "wood"), ("sm_bb_broomleather", leather, "leather"),
            ("sm_bb_broombristles", bristles, "bristles"), ("sm_bb_broomcopper", copper, "copper"),
            ("sm_bb_broomaccent", accent, "team"))


def wand():
    wood, leather, copper = mesh(), mesh(), mesh()
    # local +z points toward the existing lumos tip. the mount is the grip butt.
    wood.tube(catmull([(0, 0, 0), (0, 0, 8), (.11, 0, 14), (.23, .10, 23),
                      (.12, .04, 34), (0, 0, 44)], 3),
              [1.3-(i/15.)*1.13 for i in range(16)], 12)
    leather.tube([(0, 0, .5), (0, 0, 2), (0, 0, 8.4), (0, 0, 10.2)], [1.28, 1.46, 1.38, 1.1], 12)
    # a restrained helix and beadwork instead of broad primitive cylinders.
    points = [(1.45*math.cos(math.tau*5*i/80), 1.45*math.sin(math.tau*5*i/80), 1.2+8*i/80) for i in range(81)]
    leather.tube(points, .18, 5)
    for z, radius, height in ((.45, 1.4, .6), (10.6, 1.48, .65), (12.1, 1.26, .36), (13.2, 1.19, .30)):
        copper.tube([(0, 0, z-height/2), (0, 0, z+height/2)], radius, 16)
    # three carved copper leaf inlays hug the taper and converge toward the tip.
    for j in range(3):
        angle = math.tau*j/3
        points = [(math.cos(angle)*r+.17, math.sin(angle)*r+.05, z) for r, z in
                  ((1.15, 13.7), (1.04, 16), (.88, 20), (.72, 24), (.54, 29))]
        copper.tube(points, [.13, .15, .14, .10, .04], 5)
    return (("sm_bb_wandwood", wood, "wood"), ("sm_bb_wandleather", leather, "leather"),
            ("sm_bb_wandcopper", copper, "copper"))


def validate(meshes):
    total = 0
    for name, mesh, material in meshes:
        if not mesh.vertices or not mesh.faces or len(mesh.vertices) != len(mesh.uvs): raise valueerror("empty mesh " + name)
        if not all(math.isfinite(value) for p in mesh.vertices+mesh.uvs for value in p): raise valueerror("nonfinite geometry " + name)
        for face in mesh.faces:
            if len(face) < 3 or min(face) < 1 or max(face) > len(mesh.vertices): raise valueerror("invalid face " + name)
            a = mesh.vertices[face[0]-1]
            area = sum(length(cross(sub(mesh.vertices[face[i]-1], a), sub(mesh.vertices[face[i+1]-1], a)))/2 for i in range(1, len(face)-1))
            if area < 1e-8: raise valueerror("degenerate polygon " + name)
        triangles = sum(len(face)-2 for face in mesh.faces)
        if triangles > 6500: raise valueerror("per-layer geometry budget exceeded: " + name)
        total += triangles
    if total > 16000: raise valueerror("combined broom/wand geometry budget exceeded")
    return {"finite_geometry": true, "valid_indices": true, "nondegenerate_polygons": true,
            "total_triangles_broom_and_wand": total, "budget_triangles": 16000}


def generate_source():
    SOURCE.mkdir(parents=True, exist_ok=true)
    meshes = broom() + wand()
    checks = validate(meshes)
    assets = [mesh.save(name, material) for name, mesh, material in meshes]
    manifest = {"generator": generator, "original_geometry": true, "units": "centimeters",
                "coordinate_contract": "obj y is inverse unreal y; winding is also reflected",
                "decorative_only": true, "component_collision": "nocollision", "maps_modified": false,
                "broom_mount": {"location": [0, 0, 0], "scale": [1, 1, 1], "rotation": [0, 0, 0]},
                "cockpit_broom_mount": {"location": [55, 30, -48], "scale": [1, 1, 1], "rotation": [0, 0, 0]},
                "wand_mount": {"tip_axis": "+z", "length_cm": 44, "location": "existing start", "scale": [1, 1, 1]},
                "pose_fit_cm": {"grip_center": [43, 0, 7], "hand_targets": [[46, -9, 10], [46, 9, 10]],
                                "foot_targets": [[26, -22, -53], [26, 22, -53]], "footrest_height": -60},
                "materials": materials, "checks": checks, "assets": assets,
                "rendered_validation": "not_run", "frame_time_validation": "not_run"}
    (source / "broom_equipment_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    if "--generate-source" in sys.argv:
        result = generate_source()
        print(json.dumps({"status": "source_generated", "assets": len(result["assets"]), "checks": result["checks"]}))
    else:
        print(json.dumps({"status": "not_run", "required_argument": "--generate-source"}))
