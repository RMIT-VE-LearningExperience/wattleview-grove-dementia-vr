import sys, bpy
sys.path.append(bpy.utils.system_resource('SCRIPTS', path="addons_core"))
from io_scene_fbx import parse_fbx
path = sys.argv[sys.argv.index('--')+1]
root, ver = parse_fbx.parse(path)
print("version", ver)
def find(e, name):
    return [c for c in e.elems if c.id == name]
for e in root.elems:
    if e.id == b'GlobalSettings':
        for p in find(e, b'Properties70')[0].elems:
            print("GS", [x.decode() if isinstance(x,bytes) else x for x in p.props])
objs = find(root, b'Objects')[0]
cnt={}
for e in objs.elems:
    if e.id==b'Model':
        name=e.props[1].split(b'\x00')[0].decode(); typ=e.props[2].decode()
        cnt[typ]=cnt.get(typ,0)+1
        props={}
        for p70 in find(e,b'Properties70'):
            for p in p70.elems:
                k=p.props[0].decode()
                if k in ('Lcl Translation','Lcl Rotation','Lcl Scaling','PreRotation','RotationActive','InheritType'):
                    props[k]=[round(x,3) if isinstance(x,float) else x for x in p.props[4:]]
        if typ!='LimbNode' or name in ('root','pelvis','spine_01','thigh_l','clavicle_l'):
            print("Model", name, typ, props)
    elif e.id in (b'Geometry', b'Deformer', b'Pose'):
        cnt[e.id.decode()]=cnt.get(e.id.decode(),0)+1
print(cnt)
