"""Conservative OBJ axis proof shared by environment staging and repair.

Only identity and the witnessed Y reflection are accepted; topology and signed
bounds must agree on every imported mesh. Symmetric meshes cannot prove sign.
"""

def bounds_errors(source,actual):
    mirrored=[[source[0][0],-source[1][1],source[0][2]],[source[1][0],-source[0][1],source[1][2]]]
    error=lambda expected:max(abs(actual[i][j]-expected[i][j]) for i in range(2) for j in range(3))
    return error(source),error(mirrored)

def classify(source,actual,source_triangles,actual_triangles):
    if source_triangles!=actual_triangles:raise ValueError('Imported environment topology differs')
    same,flip=bounds_errors(source,actual)
    if min(same,flip)>.1:raise ValueError('Unexplained imported environment axis transform')
    return {'identity_error_cm':same,'mirror_y_error_cm':flip,
            'orientation':'ambiguous_symmetric' if same<=.1 and flip<=.1 else 'identity' if same<=.1 else 'mirror_y'}

def combined_sign(rows):
    evidence={r['orientation'] for r in rows if r['orientation']!='ambiguous_symmetric'}
    if len(evidence)!=1:raise ValueError('No single evidenced handedness across asymmetric meshes')
    return -1 if next(iter(evidence))=='mirror_y' else 1

def audit(unreal,manifest,art):
    rows=[]
    for venue in manifest['venues']:
        for source in venue['meshes']:
            mesh=unreal.EditorAssetLibrary.load_asset(art+'/Meshes/'+source['name'])
            if not isinstance(mesh,unreal.StaticMesh):raise ValueError('Missing exact imported environment mesh')
            box=mesh.get_bounding_box();bounds=[[float(box.min.x),float(box.min.y),float(box.min.z)],[float(box.max.x),float(box.max.y),float(box.max.z)]]
            count=int(mesh.get_num_triangles(0))
            row=classify(source['bounds'],bounds,source['triangles'],count)
            row.update(name=source['name'],source_sha256=source['sha256'],source_bounds=source['bounds'],imported_bounds=bounds,triangles=count)
            rows.append(row)
    return {'actor_y_compensation':combined_sign(rows),'meshes':rows,
            'proof_scope':'Exact triangle counts and signed bounds; asymmetric meshes prove global handedness, not a per-vertex export comparison.'}
