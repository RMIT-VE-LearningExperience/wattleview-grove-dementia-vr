"""Gaze-to-start marker: students start the story by looking, no controller.

The PICO 4 Ultra Enterprise has no eye-tracking hardware, so "look to start" uses HEAD gaze:
BP_StoryDirector compares the camera's forward vector with the direction to StartTarget each
tick, fills MPC_Perception.GazeProgress over GAZE_SECONDS while the student looks at it, and
starts LS_Story when it is full.

Builds:
  M_GazeTarget     unlit, masked: warm core that brightens with progress + a ring that fills
                   clockwise with GazeProgress (polar angle of the UV).
  StartTarget      TargetPoint root (+X faces the viewer) with StartTarget_Disc (plane) and
                   StartTarget_Text ("Look at the light to begin"). The director moves it in
                   front of the active anchor at BeginPlay and hides it when the story starts.

Run in the open editor:  exec(open(r"<this file>").read())
"""
import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
MPC_PATH = "/Game/Wattleview/Materials/MPC_Perception"
MAT_PATH = "/Game/Wattleview/Materials/M_GazeTarget"

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def log(msg):
    unreal.log("[GazeStart] " + msg)


def ensure_mpc_param(name):
    mpc = unreal.load_asset(MPC_PATH)
    params = list(mpc.get_editor_property("scalar_parameters"))
    if not any(str(p.get_editor_property("parameter_name")) == name for p in params):
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", 0.0)
        params.append(p)
        mpc.set_editor_property("scalar_parameters", params)
        eas.save_loaded_asset(mpc)
    return mpc


class G:
    def __init__(self, mat):
        self.m, self.y = mat, 0

    def new(self, cls):
        self.y += 110
        return mel.create_material_expression(self.m, cls, -900, self.y)

    def c(self, v):
        e = self.new(unreal.MaterialExpressionConstant)
        e.set_editor_property("r", float(v))
        return e

    def c3(self, rgb):
        e = self.new(unreal.MaterialExpressionConstant3Vector)
        e.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
        return e

    def op(self, cls, a, b=None, pa="A", pb="B"):
        e = self.new(cls)
        mel.connect_material_expressions(a, "", e, pa)
        if b is not None:
            mel.connect_material_expressions(b, "", e, pb)
        return e

    def sat(self, a):
        return self.op(unreal.MaterialExpressionSaturate, a, pa="")

    def mask(self, a, channel):
        e = self.new(unreal.MaterialExpressionComponentMask)
        for ch in "rgba":
            e.set_editor_property(ch, ch == channel)
        mel.connect_material_expressions(a, "", e, "")
        return e

    def step(self, x, edge, sharp=60.0, above=True):
        """~1 where x > edge (or < edge if above=False), soft over 1/sharp."""
        d = self.op(unreal.MaterialExpressionSubtract, x, self.c(edge)) if above else \
            self.op(unreal.MaterialExpressionSubtract, self.c(edge), x)
        return self.sat(self.op(unreal.MaterialExpressionMultiply, d, self.c(sharp)))


def build_material(mpc):
    if eas.does_asset_exist(MAT_PATH):
        mat = unreal.load_asset(MAT_PATH)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_GazeTarget", "/Game/Wattleview/Materials", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    g = G(mat)

    progress = g.new(unreal.MaterialExpressionCollectionParameter)
    progress.set_editor_property("collection", mpc)
    progress.set_editor_property("parameter_name", "GazeProgress")

    uv = g.new(unreal.MaterialExpressionTextureCoordinate)
    centre = g.new(unreal.MaterialExpressionConstant2Vector)
    centre.set_editor_property("r", 0.5)
    centre.set_editor_property("g", 0.5)
    rel = g.op(unreal.MaterialExpressionSubtract, uv, centre)
    dist = g.new(unreal.MaterialExpressionDistance)
    mel.connect_material_expressions(uv, "", dist, "A")
    mel.connect_material_expressions(centre, "", dist, "B")

    core = g.step(dist, 0.22, above=False)                                   # inner disc
    ring = g.op(unreal.MaterialExpressionMultiply, g.step(dist, 0.36), g.step(dist, 0.46, above=False))

    # Polar angle 0..1 (clockwise from the top) for the fill.
    atan = g.new(unreal.MaterialExpressionArctangent2)
    mel.connect_material_expressions(g.mask(rel, "r"), "", atan, "Y")
    mel.connect_material_expressions(g.mask(rel, "g"), "", atan, "X")
    angle01 = g.op(unreal.MaterialExpressionAdd,
                   g.op(unreal.MaterialExpressionDivide, atan, g.c(6.2831853)), g.c(0.5))
    filled = g.sat(g.op(unreal.MaterialExpressionMultiply,
                        g.op(unreal.MaterialExpressionSubtract, progress, angle01), g.c(200.0)))

    warm = g.c3((1.0, 0.86, 0.62))
    core_bright = g.op(unreal.MaterialExpressionLinearInterpolate, g.c(0.8), g.c(1.0), pa="A", pb="B")
    mel.connect_material_expressions(progress, "", core_bright, "Alpha")
    ring_bright = g.op(unreal.MaterialExpressionLinearInterpolate, g.c(0.35), g.c(1.0), pa="A", pb="B")
    mel.connect_material_expressions(filled, "", ring_bright, "Alpha")
    light = g.op(unreal.MaterialExpressionAdd,
                 g.op(unreal.MaterialExpressionMultiply, core, core_bright),
                 g.op(unreal.MaterialExpressionMultiply, ring, ring_bright))
    mel.connect_material_property(g.op(unreal.MaterialExpressionMultiply, warm, light), "",
                                  unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(g.op(unreal.MaterialExpressionMax, core, ring), "",
                                  unreal.MaterialProperty.MP_OPACITY_MASK)
    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    return mat


def build():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)
    mpc = ensure_mpc_param("GazeProgress")
    mat = build_material(mpc)

    for a in acts.get_all_level_actors():
        if a.get_actor_label().startswith("StartTarget"):
            acts.destroy_actor(a)

    # Placed in front of David's door viewpoint; the director re-places it per viewpoint.
    root = acts.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(220, 100, 160), unreal.Rotator(0, 0, -150))
    root.set_actor_label("StartTarget")
    root.set_folder_path("Story/Start")
    root.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)

    disc = acts.spawn_actor_from_object(unreal.load_asset("/Engine/BasicShapes/Plane.Plane"),
                                        unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    disc.set_actor_label("StartTarget_Disc")
    disc.set_folder_path("Story/Start")
    c = disc.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_material(0, mat)
    c.set_cast_shadow(False)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    disc.attach_to_actor(root, "", unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET,
                         unreal.AttachmentRule.KEEP_WORLD, False)
    # Plane normal is +Z; pitch -90 turns it to +X (toward the viewer). 24 cm across.
    disc.root_component.set_editor_property("relative_rotation", unreal.Rotator(0.0, -90.0, 0.0))
    disc.set_actor_relative_scale3d(unreal.Vector(0.24, 0.24, 0.24))

    text = acts.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    text.set_actor_label("StartTarget_Text")
    text.set_folder_path("Story/Start")
    tr = text.text_render
    tr.set_text(unreal.Text("Look at the light to begin"))
    tr.set_world_size(7.0)
    tr.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    tr.set_text_render_color(unreal.Color(235, 225, 205, 255))
    # The default text material is lit: by the window it rendered dark brown, from behind near
    # white. Unlit keeps the caption the same warm white in every view.
    tr.set_text_material(unreal.load_asset("/Engine/EngineMaterials/UnlitText"))
    tr.set_mobility(unreal.ComponentMobility.MOVABLE)
    text.attach_to_actor(root, "", unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET,
                         unreal.AttachmentRule.KEEP_WORLD, False)
    text.root_component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -24.0))

    # Re-link a placed director (recreating StartTarget breaks its reference).
    for a in acts.get_all_level_actors():
        if a.get_actor_label() == "StoryDirector":
            a.set_editor_property("StartTarget", root)
            log("StoryDirector.StartTarget re-linked")

    les.save_current_level()
    log("StartTarget placed and saved")


build()
