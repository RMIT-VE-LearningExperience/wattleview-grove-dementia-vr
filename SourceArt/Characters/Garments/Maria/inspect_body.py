import bpy, mathutils
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_Maria_BodyMesh.fbx")
print("UNIT", bpy.context.scene.unit_settings.scale_length)
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, tuple(round(x,4) for x in o.location), tuple(round(x,4) for x in o.rotation_euler), tuple(round(x,4) for x in o.scale), o.parent.name if o.parent else None)
    if o.type=='MESH':
        me=o.data
        print("  verts",len(me.vertices),"polys",len(me.polygons),"vg",len(o.vertex_groups), "mats",[m.name for m in me.materials], "uv", [u.name for u in me.uv_layers])
        ws=[o.matrix_world@v.co for v in me.vertices]
        mn=[min(w[i] for w in ws) for i in range(3)]; mx=[max(w[i] for w in ws) for i in range(3)]
        print("  bbox", mn, mx)
        for m in o.modifiers: print("  mod", m.type, getattr(m,'object',None))
        print("  maxinf", max(len(v.groups) for v in me.vertices))
    if o.type=='ARMATURE':
        arm=o.data
        print("  bones", len(arm.bones))
        for b in arm.bones:
            hw=o.matrix_world@b.head_local; tw=o.matrix_world@b.tail_local
            print("  B", b.name, b.parent.name if b.parent else None, tuple(round(x,3) for x in hw), tuple(round(x,3) for x in tw))
