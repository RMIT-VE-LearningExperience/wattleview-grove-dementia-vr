import bpy
import json
import sys

path = sys.argv[sys.argv.index('--') + 1]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for block in list(bpy.data.meshes):
    bpy.data.meshes.remove(block)

bpy.ops.import_scene.fbx(filepath=path, use_anim=False, automatic_bone_orientation=False)
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH']
arms = [o for o in scene.objects if o.type == 'ARMATURE']
result = {
    'path': path,
    'objects': [(o.name, o.type, o.parent.name if o.parent else None,
                 tuple(round(v, 9) for v in o.scale), tuple(round(v, 9) for v in o.location)) for o in scene.objects],
    'mesh_count': len(meshes),
    'armature_count': len(arms),
    'meshes': [],
    'armatures': [],
}
for obj in meshes:
    world_points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    mins = tuple(round(min(p[i] for p in world_points), 9) for i in range(3))
    maxs = tuple(round(max(p[i] for p in world_points), 9) for i in range(3))
    result['meshes'].append({
        'name': obj.name,
        'vertices': len(obj.data.vertices),
        'polygons': len(obj.data.polygons),
        'loops': len(obj.data.loops),
        'uv_layers': [(uv.name, len(uv.data)) for uv in obj.data.uv_layers],
        'materials': [m.name if m else None for m in obj.data.materials],
        'groups': len(obj.vertex_groups),
        'modifiers': [(m.name, m.type, getattr(m, 'object', None).name if getattr(m, 'object', None) else None) for m in obj.modifiers],
        'bbox_world_min': mins,
        'bbox_world_max': maxs,
    })
for obj in arms:
    result['armatures'].append({'name': obj.name, 'bones': len(obj.data.bones),
                                'roots': [b.name for b in obj.data.bones if b.parent is None]})
print('CODEX_IMPORT_RESULT=' + json.dumps(result, sort_keys=True))
