import bpy, mathutils
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Characters\Bodies\SKM_David_BodyMesh.fbx")
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, tuple(round(v,4) for v in o.scale), tuple(round(v,3) for v in o.rotation_euler), o.parent.name if o.parent else None)
    if o.type=='MESH':
        me=o.data
        print(" verts",len(me.vertices),"polys",len(me.polygons),"vgroups",len(o.vertex_groups), "mats",[m.name for m in me.materials], "uv",[u.name for u in me.uv_layers])
        bb=[o.matrix_world@mathutils.Vector(c) for c in o.bound_box]
        print(" bbox min",[round(min(v[i] for v in bb),3) for i in range(3)],"max",[round(max(v[i] for v in bb),3) for i in range(3)])
        for m in o.modifiers: print(" mod",m.type, getattr(m,'object',None))
    if o.type=='ARMATURE':
        arm=o.data
        print(" bones",len(arm.bones))
        for b in arm.bones:
            hw=o.matrix_world@b.head_local; tw=o.matrix_world@b.tail_local
            print("  B",b.name, b.parent.name if b.parent else None, [round(x,2) for x in hw],[round(x,2) for x in tw])
print("unit scale", bpy.context.scene.unit_settings.scale_length)
