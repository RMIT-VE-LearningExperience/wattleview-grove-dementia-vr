import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_Maria_BodyMesh.fbx")
body=bpy.data.objects['SKM_Maria_BodyMesh.001']
names={g.index:g.name for g in body.vertex_groups}
vs=[(body.matrix_world@v.co, v) for v in body.data.vertices]
def show(label, cond, n=12):
    s=[(w,v) for w,v in vs if cond(w)]
    s.sort(key=lambda t:-t[0].z)
    print(label, len(s))
    for w,v in s[:n]:
        gs=sorted([(g.weight,names[g.group]) for g in v.groups if g.weight>0.01],reverse=True)
        print("  ",tuple(round(c,3) for c in w), [(n_,round(x,2)) for x,n_ in gs])
show("armtop", lambda w: w.x>0.1 and w.z>1.10 and w.z<1.2)
show("thightop", lambda w: w.x>0 and w.z<0.66 and w.z>0.6 and w.x<0.25, 8)
show("knee", lambda w: w.x>0 and abs(w.z-0.414)<0.01 and w.x<0.25, 6)
show("elbow", lambda w: w.x>0 and abs(w.z-1.02)<0.01 and w.x>0.2, 6)
show("forearm", lambda w: w.x>0 and abs(w.z-0.96)<0.008 and w.x>0.2, 6)
