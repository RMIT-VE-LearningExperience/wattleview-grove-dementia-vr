import bpy, mathutils, math
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_Maria_BodyMesh.fbx")
body=bpy.data.objects['SKM_Maria_BodyMesh.001']
W=[body.matrix_world@v.co for v in body.data.vertices]
L=[w for w in W if w.x>0]
def rng(pts):
    if not pts: return None
    return [ (round(min(p[i] for p in pts),3), round(max(p[i] for p in pts),3)) for i in range(3)]
print("LEFT leg slices (x>0, x<0.3, z<0.7)")
for z in [0.62,0.6,0.55,0.5,0.45,0.414,0.38,0.34,0.30,0.28,0.25,0.2,0.15,0.1,0.07,0.04,0.02,0.0]:
    s=[p for p in L if abs(p.z-z)<0.006 and p.z<0.7]
    print(" z",z,len(s),rng(s))
print("feet all z<0.12 left", rng([p for p in L if p.z<0.12]))
print("leg top z max", max(p.z for p in L if abs(p.x)<0.3 and p.z<0.8))
arm=[p for p in L if p.z>0.75 and p.x>0.08]
print("arm zmax", max(p.z for p in arm), rng(arm))
# open boundary loops
import bmesh
bm=bmesh.new(); bm.from_mesh(body.data)
bm.transform(body.matrix_world)
be=[e for e in bm.edges if e.is_boundary]
print("boundary edges",len(be))
pts=[v.co.copy() for e in be for v in e.verts]
# cluster by region
for name,cond in [("armL",lambda p:p.x>0.05 and p.z>0.9),("armR",lambda p:p.x<-0.05 and p.z>0.9),("legL",lambda p:p.x>0 and p.z<0.8),("legR",lambda p:p.x<0 and p.z<0.8)]:
    s=[p for p in pts if cond(p)]
    print(name,len(s),rng(s))
    if s:
        c=sum(s,Vector())/len(s); print("  centroid",tuple(round(x,3) for x in c))
