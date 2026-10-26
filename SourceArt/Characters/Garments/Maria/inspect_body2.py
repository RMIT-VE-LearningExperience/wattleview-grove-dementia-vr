import bpy, mathutils, math
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_Maria_BodyMesh.fbx")
body=bpy.data.objects['SKM_Maria_BodyMesh.001']
arm=bpy.data.objects['root']
print("MW body", body.matrix_world)
print("MW arm", arm.matrix_world)
dg=bpy.context.evaluated_depsgraph_get()
ev=body.evaluated_get(dg); me=ev.to_mesh()
ws=[body.matrix_world@v.co for v in me.vertices]
print("evbbox",[min(w[i] for w in ws) for i in range(3)],[max(w[i] for w in ws) for i in range(3)])
raw=[v.co for v in body.data.vertices]
print("rawbbox",[min(w[i] for w in raw) for i in range(3)],[max(w[i] for w in raw) for i in range(3)])
# vertex group names
print([g.name for g in body.vertex_groups][:200])
# render
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
scn.render.resolution_x=600; scn.render.resolution_y=900
cam=bpy.data.cameras.new('c'); cam.type='ORTHO'; cam.ortho_scale=1.7
co=bpy.data.objects.new('c',cam); scn.collection.objects.link(co); scn.camera=co
for name,loc,rot in [('front',(0,-4,0.75),(math.radians(90),0,0)),('side',(4,0,0.75),(math.radians(90),0,math.radians(90)))]:
    co.location=loc; co.rotation_euler=rot
    scn.render.filepath=r"C:\Users\lawre\AppData\Local\Temp\claude\d--Unreal-Projects-WattleviewGrove\0f4118b8-f5c8-46a9-906a-e39aef141504\scratchpad\body_%s.png"%name
    bpy.ops.render.render(write_still=True)
