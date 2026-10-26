"""Build the Wattleview Grove resident room blockout (UE 5.8, Python).

Greybox of Maria Russo's aged-care room for Story V2, sized and laid out so every
scripted beat works: photo by her recliner, table facing the garden window, TV
ahead-right of her seat, corridor door to her left, fan overhead. Also places the
three viewpoint cameras and placeholder characters.

Run headless:
  UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<this file>" -nosplash
  (-ExecutePythonScript closes the editor when the script returns.)

Re-runnable: rebuilds the map from scratch each time. Afterwards rerun, in the open editor:
build_lighting.py (palette, daylight, bake), build_story_sequence.py, build_story_director.py,
build_perception_layer.py, since this script discards everything they placed.

Coordinates (cm): X = 0 south wall -> 500 north (window) wall.
                  Y = 0 west (door) wall -> 450 east (bed/TV) wall.  Z up, floor at 0.
"""
import math

import unreal

MAP_PATH = "/Game/Wattleview/Maps/L_ResidentRoom"
MAT_DIR = "/Game/Wattleview/Materials/Blockout"
ROOM_X, ROOM_Y, ROOM_H, WALL = 500.0, 450.0, 270.0, 15.0

eas = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

CUBE = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
CYL = unreal.load_asset("/Engine/BasicShapes/Cylinder.Cylinder")
SPHERE = unreal.load_asset("/Engine/BasicShapes/Sphere.Sphere")


def log(msg):
    unreal.log("[ResidentRoom] " + msg)


# ---------------------------------------------------------------- materials
def base_material(name, unlit):
    path = f"{MAT_DIR}/{name}"
    if eas.does_asset_exist(path):
        return unreal.load_asset(path)
    mat = tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    col = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1))
    if unlit:
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        mel.connect_material_property(col, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        mel.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)
        rough = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -500, 200)
        rough.set_editor_property("parameter_name", "Roughness")
        rough.set_editor_property("default_value", 0.85)
        mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    return mat


M_LIT = None
M_UNLIT = None
_mi_cache = {}

# Palette: warm cream walls, light timber, pinks/florals, garden greens (page 3 reference).
PALETTE = {
    "Wall":      ((0.78, 0.72, 0.62), False),
    "Ceiling":   ((0.85, 0.83, 0.80), False),
    "Carpet":    ((0.32, 0.29, 0.27), False),
    "Timber":    ((0.55, 0.38, 0.22), False),
    "TimberDk":  ((0.35, 0.22, 0.12), False),
    "Pink":      ((0.70, 0.36, 0.40), False),
    "PinkLight": ((0.85, 0.62, 0.64), False),
    "Linen":     ((0.88, 0.86, 0.80), False),
    "Floral":    ((0.80, 0.55, 0.58), False),
    "Curtain":   ((0.72, 0.52, 0.50), False),
    "Rug":       ((0.60, 0.30, 0.30), False),
    "Metal":     ((0.25, 0.25, 0.26), False),
    "Black":     ((0.03, 0.03, 0.03), False),
    "Glass":     ((0.70, 0.80, 0.85), False),
    "White":     ((0.90, 0.90, 0.90), False),
    "Plant":     ((0.18, 0.40, 0.15), False),
    "Pot":       ((0.75, 0.70, 0.62), False),
    "Grass":     ((0.20, 0.42, 0.14), False),
    "Soil":      ((0.25, 0.17, 0.10), False),
    "FlowerRed": ((0.75, 0.12, 0.15), False),
    "FlowerYel": ((0.85, 0.70, 0.15), False),
    "FlowerPur": ((0.45, 0.25, 0.60), False),
    "Fence":     ((0.60, 0.55, 0.45), False),
    "Note1":     ((0.95, 0.85, 0.25), False),
    "Note2":     ((0.95, 0.45, 0.60), False),
    "Note3":     ((0.40, 0.80, 0.95), False),
    "Photo":     ((0.35, 0.55, 0.30), True),   # warm-lit garden photo: unlit so it reads in VR2
    "TVScreen":  ((0.10, 0.13, 0.18), True),
    "Sky":       ((0.45, 0.65, 0.90), True),
    "LampGlow":  ((0.95, 0.85, 0.65), True),
}


def mi(key):
    if key in _mi_cache:
        return _mi_cache[key]
    color, unlit = PALETTE[key]
    name = f"MI_BO_{key}"
    path = f"{MAT_DIR}/{name}"
    if eas.does_asset_exist(path):
        inst = unreal.load_asset(path)
    else:
        inst = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(inst, M_UNLIT if unlit else M_LIT)
    mel.set_material_instance_vector_parameter_value(inst, "Color", unreal.LinearColor(*color, 1.0))
    eas.save_loaded_asset(inst)
    _mi_cache[key] = inst
    return inst


# ---------------------------------------------------------------- spawn helpers
def _place(mesh, label, loc, scale, mat, yaw=0.0, folder=None):
    a = actors.spawn_actor_from_object(mesh, unreal.Vector(*loc), unreal.Rotator(0.0, 0.0, yaw))
    a.set_actor_label(label)
    a.set_actor_scale3d(unreal.Vector(*scale))
    comp = a.static_mesh_component
    comp.set_material(0, mi(mat))
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    if folder:
        a.set_folder_path(folder)
    return a


def box(label, x0, x1, y0, y1, z0, z1, mat, folder="Room"):
    """Axis-aligned box from min/max extents in cm (BasicShapes Cube is 100 cm, centred)."""
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    s = ((x1 - x0) / 100, (y1 - y0) / 100, (z1 - z0) / 100)
    return _place(CUBE, label, c, s, mat, folder=folder)


def cyl(label, x, y, z0, z1, diameter, mat, folder="Room"):
    return _place(CYL, label, (x, y, (z0 + z1) / 2), (diameter / 100, diameter / 100, (z1 - z0) / 100), mat, folder=folder)


def sphere(label, x, y, z, d, mat, folder="Room"):
    return _place(SPHERE, label, (x, y, z), (d / 100, d / 100, d / 100), mat, folder=folder)


def rotated_box(label, cx, cy, cz, sx, sy, sz, mat, yaw, folder="Room"):
    return _place(CUBE, label, (cx, cy, cz), (sx / 100, sy / 100, sz / 100), mat, yaw=yaw, folder=folder)


def chair(label, cx, cy, yaw, mat="Pink", arms=True, folder="Room/Furniture"):
    """Dining armchair, seat 45 cm high, facing +X rotated by yaw degrees."""
    r = math.radians(yaw)
    fx, fy = math.cos(r), math.sin(r)
    rx, ry = -math.sin(r), math.cos(r)

    def off(f, s):
        return cx + fx * f + rx * s, cy + fy * f + ry * s

    x, y = off(0, 0)
    rotated_box(f"{label}_Seat", x, y, 46, 50, 50, 8, mat, yaw, folder)
    x, y = off(-23, 0)
    rotated_box(f"{label}_Back", x, y, 75, 6, 50, 50, mat, yaw, folder)
    for i, (f, s) in enumerate([(20, -22), (20, 22), (-20, -22), (-20, 22)]):
        x, y = off(f, s)
        rotated_box(f"{label}_Leg{i}", x, y, 21, 4, 4, 42, "Timber", yaw, folder)
    if arms:
        for i, s in enumerate((-26, 26)):
            x, y = off(0, s)
            rotated_box(f"{label}_Arm{i}", x, y, 66, 45, 6, 5, "Timber", yaw, folder)


# ---------------------------------------------------------------- build
def build():
    global M_LIT, M_UNLIT
    M_LIT = base_material("M_Blockout", False)
    M_UNLIT = base_material("M_BlockoutUnlit", True)

    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    log("new blank map created")

    X, Y, H, T = ROOM_X, ROOM_Y, ROOM_H, WALL

    # Shell -----------------------------------------------------------------
    box("Floor", 0, X, 0, Y, -10, 0, "Carpet")
    box("Ceiling", -T, X + T, -T, Y + T, H, H + 10, "Ceiling")
    box("Wall_South", -T, 0, -T, Y + T, 0, H, "Wall")
    box("Wall_East", -T, X + T, Y, Y + T, 0, H, "Wall")
    # West wall with corridor door opening X 60..150, height 210.
    box("Wall_West_A", -T, 60, -T, 0, 0, H, "Wall")
    box("Wall_West_B", 150, X + T, -T, 0, 0, H, "Wall")
    box("Wall_West_Head", 60, 150, -T, 0, 210, H, "Wall")
    box("Door", 61, 149, -9, -4, 0, 209, "Timber", folder="Room/Door")
    box("Door_Handle", 135, 142, -3, 0, 100, 104, "Metal", folder="Room/Door")
    # North wall with garden window opening Y 100..350, sill 80, head 220.
    box("Wall_North_A", X, X + T, -T, 100, 0, H, "Wall")
    box("Wall_North_B", X, X + T, 350, Y + T, 0, H, "Wall")
    box("Wall_North_Sill", X, X + T, 100, 350, 0, 80, "Wall")
    box("Wall_North_Head", X, X + T, 100, 350, 220, H, "Wall")
    box("Window_SillBoard", X - 12, X + 2, 95, 355, 78, 82, "White", folder="Room/Window")
    for i, y in enumerate((100, 225, 350)):
        box(f"Window_Mullion{i}", X + 5, X + 10, y - 3, y + 3, 80, 220, "White", folder="Room/Window")
    box("Window_Transom", X + 5, X + 10, 100, 350, 217, 220, "White", folder="Room/Window")
    box("Curtain_L", X - 14, X - 4, 55, 100, 5, 240, "Curtain", folder="Room/Window")
    box("Curtain_R", X - 14, X - 4, 350, 395, 5, 240, "Curtain", folder="Room/Window")
    box("Skirting_West", 150, X, 0, 1.5, 0, 10, "TimberDk")

    # Furniture -------------------------------------------------------------
    F = "Room/Furniture"
    # Bed against east wall, head at the wall.
    box("Bed_Frame", 125, 230, 240, Y, 0, 45, "Timber", F)
    box("Bed_Mattress", 128, 227, 243, Y - 3, 45, 62, "Linen", F)
    box("Bed_Cover", 126, 229, 243, 400, 58, 64, "Floral", F)
    box("Bed_Blanket", 126, 229, 250, 300, 63, 66, "PinkLight", F)
    box("Bed_Headboard", 125, 230, Y - 8, Y, 0, 115, "Timber", F)
    box("Bed_Pillow", 140, 215, 405, 440, 62, 76, "White", F)
    box("Bed_Footboard", 125, 230, 238, 244, 0, 70, "Timber", F)
    # Bedside drawers + day-date clock + lamp.
    box("Bedside", 240, 292, 400, Y, 0, 62, "Timber", F)
    box("DayDateClock", 255, 275, 425, 432, 62, 76, "Black", F)
    cyl("BedsideLamp_Base", 280, 435, 62, 90, 12, "Pot", F)
    cyl("BedsideLamp_Shade", 280, 435, 88, 108, 26, "LampGlow", F)
    # Wardrobe on south wall + memory-box shelf.
    box("Wardrobe", 0, 62, 140, 300, 0, 205, "Timber", F)
    box("Shelf", 0, 28, 320, 410, 125, 128, "TimberDk", F)
    box("MemoryBox", 3, 25, 340, 372, 128, 143, "Pink", F)
    # Maria's recliner by the west wall, beside the photograph.
    box("Recliner_Seat", 245, 325, 20, 95, 20, 50, "Pink", F)
    box("Recliner_Back", 245, 325, 15, 35, 20, 105, "Pink", F)
    box("Recliner_ArmL", 240, 252, 20, 95, 20, 68, "Pink", F)
    box("Recliner_ArmR", 318, 330, 20, 95, 20, 68, "Pink", F)
    box("Recliner_Throw", 250, 320, 30, 60, 50, 54, "Floral", F)
    # Round table facing the window, three chairs.
    cyl("Table_Top", 400, 200, 71, 75, 95, "Timber", F)
    cyl("Table_Pedestal", 400, 200, 0, 71, 12, "TimberDk", F)
    cyl("Table_Foot", 400, 200, 0, 4, 55, "TimberDk", F)
    chair("Chair_Maria", 335, 200, 0)        # faces +X: garden window ahead, TV ahead-right
    chair("Chair_Second", 400, 268, -90)     # side of table; David pulls it in at 4:00
    chair("Chair_Third", 462, 175, 165)
    # Table dressing: vase, jug, glass, hairbrush, call bell.
    cyl("Vase", 432, 150, 75, 100, 9, "Glass", F)
    sphere("Vase_Flowers", 432, 150, 104, 18, "FlowerYel", F)
    cyl("Jug", 405, 162, 75, 98, 12, "Glass", F)
    cyl("Glass", 378, 225, 75, 86, 7, "Glass", F)
    rotated_box("Hairbrush", 372, 182, 76.5, 22, 6, 3, "PinkLight", 20, F)
    cyl("CallBell", 385, 165, 75, 79, 8, "White", F)
    # TV on a low cabinet against the east wall, ahead-right of Maria's seat.
    box("TV_Cabinet", 380, 490, Y - 45, Y, 0, 60, "Timber", F)
    box("TV_Body", 395, 480, Y - 25, Y - 18, 68, 120, "Black", F)
    box("TV_Screen", 398, 477, Y - 26, Y - 25, 71, 117, "TVScreen", F)
    # Tall lamp in the south-east corner.
    cyl("FloorLamp_Base", 30, 420, 0, 3, 30, "Metal", F)
    cyl("FloorLamp_Pole", 30, 420, 3, 155, 3, "Metal", F)
    cyl("FloorLamp_Shade", 30, 420, 150, 178, 38, "LampGlow", F)
    # Rug under the table.
    box("Rug", 295, 495, 105, 300, 0, 1, "Rug", F)
    # Ceiling fan.
    cyl("Fan_Rod", 250, 225, 245, H, 4, "White", F)
    cyl("Fan_Hub", 250, 225, 238, 248, 18, "White", F)
    for i, yaw in enumerate((0, 120, 240)):
        r = math.radians(yaw)
        rotated_box(f"Fan_Blade{i}", 250 + 38 * math.cos(r), 225 + 38 * math.sin(r), 241,
                    60, 12, 1.5, "TimberDk", yaw, F)
    # Ceiling light panel.
    box("CeilingLight", 230, 270, 120, 330, H - 3, H, "LampGlow", F)

    # Wall dressing ----------------------------------------------------------
    D = "Room/Dressing"
    # The photograph: Maria and Enzo in a green backyard, beside her recliner.
    box("Photo_Frame", 330, 380, 0, 3, 125, 170, "TimberDk", D)
    box("Photo_Image", 334, 376, 3, 3.5, 129, 166, "Photo", D)
    # Calendar crowded with sticky notes, on the west wall.
    box("Calendar", 175, 235, 0, 1.5, 115, 195, "White", D)
    notes = [(180, 185, "Note1"), (195, 170, "Note2"), (212, 182, "Note3"), (222, 160, "Note1"),
             (186, 150, "Note3"), (205, 140, "Note2"), (218, 128, "Note1"), (182, 125, "Note2")]
    for i, (x, z, k) in enumerate(notes):
        box(f"StickyNote{i}", x, x + 9, 1.5, 2.0, z, z + 9, k, D)
    # Family gallery above the bed.
    for i, (x0, z0, w, h) in enumerate([(135, 150, 30, 40), (175, 160, 45, 32), (230, 150, 28, 38),
                                        (150, 200, 35, 28), (200, 198, 30, 30)]):
        box(f"Gallery_{i}", x0, x0 + w, Y - 3, Y, z0, z0 + h, "TimberDk", D)
    # Plants on the window sill.
    for i, y in enumerate((130, 320)):
        cyl(f"SillPot{i}", X - 8, y, 82, 96, 14, "Pot", D)
        sphere(f"SillPlant{i}", X - 8, y, 104, 22, "Plant", D)

    # Garden outside the window ---------------------------------------------
    G = "Garden"
    box("Garden_Ground", X + T, X + 2500, -1500, 2000, -30, -20, "Grass", G)
    beds = [(700, 40, 520, "FlowerRed"), (700, 620, 300, "FlowerYel"), (900, -120, 600, "FlowerPur"),
            (1100, 100, 800, "FlowerRed")]
    for i, (x, y0, length, flower) in enumerate(beds):
        box(f"GardenBed{i}", x, x + 90, y0, y0 + length, -20, 10, "Soil", G)
        for j in range(int(length // 45)):
            colour = flower if j % 3 else "Plant"
            sphere(f"GardenBed{i}_Flower{j}", x + 45, y0 + 22 + j * 45, 22, 32, colour, G)
    box("Garden_Fence", X + 2000, X + 2010, -1500, 2000, -20, 160, "Fence", G)
    for i, (x, y, h) in enumerate([(1500, -300, 420), (1700, 600, 520), (1300, 1100, 380)]):
        cyl(f"Tree{i}_Trunk", x, y, -20, h * 0.5, 25, "TimberDk", G)
        sphere(f"Tree{i}_Canopy", x, y, h * 0.65, h * 0.6, "Plant", G)
    # Sky backdrop: unlit, PICO-safe (no sky atmosphere on mobile LDR).
    for sky_box in (box("Sky_North", X + 3000, X + 3010, -3000, 3500, -30, 2500, "Sky", G),
                    box("Sky_Top", X, X + 3010, -3000, 3500, 2500, 2510, "Sky", G),
                    box("Sky_West", X, X + 3010, -3010, -3000, -30, 2500, "Sky", G),
                    box("Sky_East", X, X + 3010, 3500, 3510, -30, 2500, "Sky", G)):
        sky_box.static_mesh_component.set_cast_shadow(False)   # otherwise it shades the garden

    # Lighting -----------------------------------------------------------------
    # No exposure on device (mobile LDR): keep raw light values near 1.
    # Australian morning sun from the north-east through the north-facing window:
    # light travels south-west and down, so it enters the room and side-lights the garden.
    sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(X + 200, 225, 400),
                                        unreal.Rotator(0.0, -35.0, 235.0))
    sun.set_actor_label("Sun_Morning")
    lc = sun.light_component
    lc.set_intensity(1.2)
    lc.set_light_color(unreal.LinearColor(1.0, 0.88, 0.72, 1.0))
    sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(250, 225, 200), unreal.Rotator(0, 0, 0))
    sky.set_actor_label("SkyLight")
    # A captured sky needs a recapture pass that never runs in a headless build, so feed the
    # skylight a fixed daylight cubemap; without it every shadow renders pitch black.
    slc = sky.light_component
    slc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    slc.set_editor_property("cubemap", unreal.load_asset("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"))
    slc.set_intensity(0.5)
    fill = actors.spawn_actor_from_class(unreal.PointLight, unreal.Vector(250, 225, 230), unreal.Rotator(0, 0, 0))
    fill.set_actor_label("RoomFill")
    fill.light_component.set_intensity(25.0)
    fill.light_component.set_attenuation_radius(700.0)
    fill.light_component.set_light_color(unreal.LinearColor(1.0, 0.93, 0.85, 1.0))
    fill.light_component.set_cast_shadows(False)
    for a in (sun, sky, fill):
        a.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        a.set_folder_path("Lighting")

    # Cameras: the three viewpoints ----------------------------------------------
    def cam(label, loc, target):
        loc_v = unreal.Vector(*loc)
        rot = unreal.MathLibrary.find_look_at_rotation(loc_v, unreal.Vector(*target))
        c = actors.spawn_actor_from_class(unreal.CineCameraActor, loc_v, rot)
        c.set_actor_label(label)
        c.set_folder_path("Cameras")
        c.get_cine_camera_component().set_editor_property("current_focal_length", 12.0)
        return c

    # Eye heights: standing 165 cm (David), 155 cm (Maria), seated 115 cm.
    cam("VP_David_Door", (105, 40, 165), (300, 150, 130))
    cam("VP_David_Table", (360, 150, 165), (335, 200, 100))
    cam("VP_David_Seated", (348, 262, 115), (335, 200, 110))
    cam("VP_Maria_Standing", (355, 60, 155), (355, 0, 147))
    cam("VP_Maria_Seated", (340, 200, 115), (700, 200, 90))
    cam("CAM_Corner", (480, 25, 225), (300, 230, 90))

    # Placeholder characters (mannequins until the MetaHumans exist) ---------
    idle = unreal.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle")

    def stand_in(label, mesh_path, loc, facing):
        """facing: direction the character faces (0 = +X). The UE5 mannequin mesh faces +Y,
        so the actor yaw is facing - 90."""
        yaw = facing - 90.0
        mesh = unreal.load_asset(mesh_path)
        if mesh is None:
            log(f"missing mesh {mesh_path}; skipping {label}")
            return None
        a = actors.spawn_actor_from_object(mesh, unreal.Vector(*loc), unreal.Rotator(0.0, 0.0, yaw))
        a.set_actor_label(label)
        a.set_folder_path("Characters")
        if idle:
            sk = a.skeletal_mesh_component
            sk.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            sk.set_editor_property("animation_data", unreal.SingleAnimationPlayData(anim_to_play=idle))
        return a

    stand_in("Maria_StandIn", "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple", (355, 68, 0), -90)
    stand_in("David_StandIn", "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple", (105, 45, 0), 45)
    stand_in("Gardener_StandIn", "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple", (745, 300, -20), 180)

    # Player start at David's door position, facing into the room.
    ps = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(105, 40, 90), unreal.Rotator(0.0, 0.0, 45.0))
    ps.set_actor_label("PlayerStart_David")

    ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)
    log(f"saved {MAP_PATH}: {ok}")
    if not ok:
        raise RuntimeError("map save failed")


build()
