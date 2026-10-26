"""Build Maria's perception layer in L_ResidentRoom (mobile-safe, no post-processing).

Everything reads MPC_Perception, which LS_Story animates and BP_StoryDirector gates with
MariaView (1 only in Maria's viewpoint). So in David's and the observer's views the layer is
invisible, and in Maria's view it follows the script beats:

  PerceptionOverlay  inside-out sphere on Anchor_Maria, drawn over everything:
                     EdgeDark -> darkened vision edges (from screen position, so it follows
                     the head); Warmth -> warm (+) / cool (-) tint; Softness -> light haze.
  PhotoGlow          warm additive halo behind the wall photograph (frame hides its centre).
  GardenerHalo       warm additive halo around the gardener.
  Memory_*           backyard overlay on the table: tomato stakes, basil, fig tree, hose.
  TV screen          TVOn (both views) and a grey blur in Maria's view.

Cost: one translucent full-view pass (overlay) plus small additive sprites. Profile on the
PICO 4 Ultra before adding more.

Run in the open editor:  exec(open(r"<this file>").read())
Re-runnable: rebuilds materials and replaces the layer actors.
"""
import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
MAT_DIR = "/Game/Wattleview/Materials/Perception"
MPC_PATH = "/Game/Wattleview/Materials/MPC_Perception"
FOLDER = "Story/Perception"

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
MP = unreal.MaterialProperty

SPHERE = unreal.load_asset("/Engine/BasicShapes/Sphere.Sphere")
CUBE = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
CYL = unreal.load_asset("/Engine/BasicShapes/Cylinder.Cylinder")
PLANE = unreal.load_asset("/Engine/BasicShapes/Plane.Plane")


def log(msg):
    unreal.log("[Perception] " + msg)


# --------------------------------------------------------------- material helpers
class Graph:
    def __init__(self, name, blend, unlit=True, two_sided=False, no_depth=False):
        # Rebuild in place: deleting a material that placed actors use opens a modal
        # "assets in use" dialog, which blocks scripted runs.
        path = f"{MAT_DIR}/{name}"
        if eas.does_asset_exist(path):
            self.mat = unreal.load_asset(path)
            mel.delete_all_material_expressions(self.mat)
        else:
            self.mat = tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
        m = self.mat
        m.set_editor_property("blend_mode", blend)
        if unlit:
            m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        m.set_editor_property("two_sided", two_sided)
        if no_depth:
            m.set_editor_property("disable_depth_test", True)
        self.mpc = unreal.load_asset(MPC_PATH)
        self.y = 0

    def _new(self, cls):
        self.y += 120
        return mel.create_material_expression(self.mat, cls, -800, self.y)

    def param(self, name):
        e = self._new(unreal.MaterialExpressionCollectionParameter)
        e.set_editor_property("collection", self.mpc)
        e.set_editor_property("parameter_name", name)
        return e

    def const(self, v):
        e = self._new(unreal.MaterialExpressionConstant)
        e.set_editor_property("r", float(v))
        return e

    def const3(self, rgb):
        e = self._new(unreal.MaterialExpressionConstant3Vector)
        e.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
        return e

    def op(self, cls, a, b=None, a_pin="A", b_pin="B"):
        e = self._new(cls)
        mel.connect_material_expressions(a, "", e, a_pin)
        if b is not None:
            mel.connect_material_expressions(b, "", e, b_pin)
        return e

    def mul(self, a, b):
        return self.op(unreal.MaterialExpressionMultiply, a, b)

    def add(self, a, b):
        return self.op(unreal.MaterialExpressionAdd, a, b)

    def sub(self, a, b):
        return self.op(unreal.MaterialExpressionSubtract, a, b)

    def lerp(self, a, b, alpha):
        e = self._new(unreal.MaterialExpressionLinearInterpolate)
        mel.connect_material_expressions(a, "", e, "A")
        mel.connect_material_expressions(b, "", e, "B")
        mel.connect_material_expressions(alpha, "", e, "Alpha")
        return e

    def sat(self, a):
        return self.op(unreal.MaterialExpressionSaturate, a, a_pin="")

    def absval(self, a):
        return self.op(unreal.MaterialExpressionAbs, a, a_pin="")

    def out(self, expr, prop, pin=""):
        mel.connect_material_property(expr, pin, prop)

    def finish(self):
        mel.layout_material_expressions(self.mat)
        mel.recompile_material(self.mat)
        eas.save_loaded_asset(self.mat)
        return self.mat


def overlay_material():
    """Edge darkening + warm/cool tint + haze, gated by MariaView."""
    g = Graph("M_PerceptionOverlay", unreal.BlendMode.BLEND_TRANSLUCENT, two_sided=True, no_depth=True)
    maria = g.param("MariaView")
    edge_amt = g.param("EdgeDark")
    warmth = g.param("Warmth")
    soft = g.param("Softness")

    # Distance from the centre of each eye's viewport: 0 centre .. ~0.7 corners.
    screen = g._new(unreal.MaterialExpressionScreenPosition)
    centre = g._new(unreal.MaterialExpressionConstant2Vector)
    centre.set_editor_property("r", 0.5)
    centre.set_editor_property("g", 0.5)
    dist = g._new(unreal.MaterialExpressionDistance)
    mel.connect_material_expressions(screen, "ViewportUV", dist, "A")
    mel.connect_material_expressions(centre, "", dist, "B")
    # edge = saturate((dist - 0.25) * 2.2) ^ 2  -> 0 in the middle, 1 at the rim
    ramp = g.sat(g.mul(g.sub(dist, g.const(0.25)), g.const(2.2)))
    edge = g.mul(ramp, ramp)
    edge_alpha = g.mul(edge, edge_amt)

    # Tint: cool blue-grey for negative warmth, amber for positive.
    is_warm = g.sat(g.mul(warmth, g.const(1000.0)))
    tint = g.lerp(g.const3((0.45, 0.55, 0.80)), g.const3((1.0, 0.75, 0.45)), is_warm)
    tint_alpha = g.mul(g.absval(warmth), g.const(0.16))

    # Haze: soft light veil that lowers contrast ("everything else is soft").
    haze_alpha = g.mul(soft, g.const(0.22))
    haze_col = g.const3((0.92, 0.90, 0.86))

    # Combine: edges go dark; centre carries tint + haze.
    centre_alpha = g.add(tint_alpha, haze_alpha)
    centre_col = g.lerp(haze_col, tint, g.sat(g.mul(tint_alpha, g.const(4.0))))
    colour = g.lerp(centre_col, g.const3((0.0, 0.0, 0.0)), g.sat(g.mul(edge_alpha, g.const(3.0))))
    alpha = g.mul(g.sat(g.add(centre_alpha, edge_alpha)), maria)

    g.out(colour, MP.MP_EMISSIVE_COLOR)
    g.out(alpha, MP.MP_OPACITY)
    return g.finish()


def glow_material(name, param, colour, strength, radial_uv=False):
    """Additive warm glow: colour * strength * param * MariaView * falloff.

    radial_uv: falloff from the UV centre (flat cards). Otherwise Fresnel falloff, which
    suits spheres seen from outside (bright centre, soft rim)."""
    g = Graph(name, unreal.BlendMode.BLEND_ADDITIVE, two_sided=True)
    amount = g.mul(g.param(param), g.param("MariaView"))
    if radial_uv:
        uv = g._new(unreal.MaterialExpressionTextureCoordinate)
        centre = g._new(unreal.MaterialExpressionConstant2Vector)
        centre.set_editor_property("r", 0.5)
        centre.set_editor_property("g", 0.5)
        dist = g._new(unreal.MaterialExpressionDistance)
        mel.connect_material_expressions(uv, "", dist, "A")
        mel.connect_material_expressions(centre, "", dist, "B")
        soft = g.sat(g.sub(g.const(1.0), g.mul(dist, g.const(2.0))))
    else:
        fres = g._new(unreal.MaterialExpressionFresnel)
        soft = g.sub(g.const(1.0), fres)
    g.out(g.mul(g.mul(g.const3(colour), g.const(strength)), g.mul(amount, g.mul(soft, soft))),
          MP.MP_EMISSIVE_COLOR)
    return g.finish()


def memory_material(name, colour):
    """Backyard memory: lit-looking unlit colour, opacity Memory * MariaView."""
    g = Graph(name, unreal.BlendMode.BLEND_TRANSLUCENT)
    g.out(g.const3(colour), MP.MP_EMISSIVE_COLOR)
    g.out(g.mul(g.param("Memory"), g.param("MariaView")), MP.MP_OPACITY)
    return g.finish()


def tv_material():
    """TV screen: news when TVOn; in Maria's view a flat grey blur instead."""
    g = Graph("M_TVScreen", unreal.BlendMode.BLEND_OPAQUE)
    tv_on = g.param("TVOn")
    maria = g.param("MariaView")
    news = g.const3((0.18, 0.28, 0.45))      # placeholder for a news video texture
    grey = g.const3((0.35, 0.35, 0.36))
    picture = g.lerp(news, grey, maria)
    off = g.const3((0.01, 0.01, 0.012))
    g.out(g.lerp(off, picture, tv_on), MP.MP_EMISSIVE_COLOR)
    return g.finish()


# --------------------------------------------------------------- actors
def find(label):
    for a in acts.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def clear_folder():
    for a in acts.get_all_level_actors():
        if str(a.get_folder_path()).startswith(FOLDER):
            acts.destroy_actor(a)


def mesh_actor(label, mesh, loc, scale, mat, parent=None, yaw=0.0, pitch=0.0):
    a = acts.spawn_actor_from_object(mesh, unreal.Vector(*loc), unreal.Rotator(0.0, pitch, yaw))
    a.set_actor_label(label)
    a.set_actor_scale3d(unreal.Vector(*scale))
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_material(0, mat)
    c.set_cast_shadow(False)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    a.set_folder_path(FOLDER)
    if parent:
        a.attach_to_actor(parent, "", unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    return a


def ensure_mpc_param(name):
    mpc = unreal.load_asset(MPC_PATH)
    params = list(mpc.get_editor_property("scalar_parameters"))
    if not any(str(p.get_editor_property("parameter_name")) == name for p in params):
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", 1.0)
        params.append(p)
        mpc.set_editor_property("scalar_parameters", params)
        eas.save_loaded_asset(mpc)


def build():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PATH:
        les.load_level(MAP_PATH)
    ensure_mpc_param("TVOn")

    m_overlay = overlay_material()
    m_photo = glow_material("M_PhotoGlow", "PhotoGlow", (1.0, 0.78, 0.45), 0.9, radial_uv=True)
    m_halo = glow_material("M_GardenerHalo", "GardenerHalo", (1.0, 0.85, 0.55), 0.8)
    m_leaf = memory_material("M_Memory_Leaf", (0.20, 0.45, 0.16))
    m_tomato = memory_material("M_Memory_Tomato", (0.80, 0.15, 0.10))
    m_stake = memory_material("M_Memory_Stake", (0.45, 0.32, 0.18))
    m_hose = memory_material("M_Memory_Hose", (0.15, 0.50, 0.25))
    m_tv = tv_material()
    log("materials built")

    clear_folder()

    # Overlay around Maria's eyes; follows her anchor (standing -> seated cut).
    anchor = find("Anchor_Maria")
    loc = anchor.get_actor_location()
    # 2 m radius: depth test is off and the effect is screen-space, so size does not change the
    # look; it just guarantees the eye is always well inside (director snap radius is 40 cm).
    ov = mesh_actor("PerceptionOverlay", SPHERE, (loc.x, loc.y, loc.z), (4.0, 4.0, 4.0), m_overlay, parent=anchor)
    ov.static_mesh_component.set_editor_property("translucency_sort_priority", 100)

    # Glow behind the photograph (frame spans X 330..380, Z 125..170 on the west wall).
    # Between the wall (Y=0) and the frame face (Y=3): the opaque frame hides the card's centre,
    # so only a warm halo shows around the photo and the image itself stays clear.
    mesh_actor("PhotoGlow", PLANE, (355, 1.5, 147.5), (1.3, 1.2, 1.0), m_photo, pitch=0.0, yaw=0.0).set_actor_rotation(
        unreal.Rotator(90.0, 0.0, 0.0), False)

    # Halo around the gardener; follows his blocking.
    gardener = find("Gardener_StandIn")
    g = gardener.get_actor_location()
    mesh_actor("GardenerHalo", SPHERE, (g.x, g.y, g.z + 95), (1.3, 1.3, 2.3), m_halo, parent=gardener)

    # Backyard memory (2:30-3:15): slim tomato vines on stakes set back by the window,
    # basil pots at the table edge, a hose lying across the table, a fig tree outside.
    for i, y in enumerate((125, 215, 305)):
        x = 482
        mesh_actor(f"Memory_Stake{i}", CYL, (x, y, 150), (0.025, 0.025, 1.5), m_stake)
        mesh_actor(f"Memory_TomatoVine{i}", SPHERE, (x - 3, y, 145), (0.16, 0.16, 0.85), m_leaf)
        for j, z in enumerate((120, 145, 170)):
            mesh_actor(f"Memory_Tomato{i}_{j}", SPHERE, (x - 10, y + (5 if j % 2 else -5), z),
                       (0.06, 0.06, 0.06), m_tomato)
    for i, (x, y) in enumerate([(425, 178), (425, 232)]):        # on the tabletop (r 47.5)
        mesh_actor(f"Memory_Basil{i}", SPHERE, (x, y, 81), (0.16, 0.16, 0.12), m_leaf)
    mesh_actor("Memory_FigTrunk", CYL, (620, 380, 120), (0.15, 0.15, 2.4), m_stake)
    mesh_actor("Memory_FigCanopy", SPHERE, (620, 380, 250), (2.2, 2.2, 1.6), m_leaf)
    mesh_actor("Memory_Hose", CYL, (395, 200, 77), (0.03, 0.03, 1.1), m_hose, yaw=0.0).set_actor_rotation(
        unreal.Rotator(0.0, 90.0, 75.0), False)

    # TV screen reads TVOn / MariaView.
    tv = find("TV_Screen")
    if tv:
        tv.static_mesh_component.set_material(0, m_tv)

    les.save_current_level()
    log("perception layer placed and saved")


build()
