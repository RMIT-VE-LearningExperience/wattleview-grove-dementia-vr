"""Preview colours for the material slot names in CONVENTIONS.md (linear RGB).

FBX files carry the Principled base colour, not Blender's viewport colour, so preview tools
colour imported pieces by slot name instead. Unreal assigns real materials by the same names.
"""
PALETTE = {
    "M_Timber": (0.55, 0.40, 0.25), "M_TimberDark": (0.22, 0.13, 0.07),
    "M_PaintedTimber": (0.85, 0.84, 0.80), "M_UpholsteryPink": (0.72, 0.42, 0.42),
    "M_UpholsteryCream": (0.78, 0.70, 0.58), "M_Linen": (0.88, 0.88, 0.86),
    "M_FloralCover": (0.70, 0.52, 0.60), "M_Crochet": (0.80, 0.55, 0.45),
    "M_Metal": (0.60, 0.61, 0.63), "M_Brass": (0.70, 0.52, 0.22),
    "M_PlasticBlack": (0.03, 0.03, 0.03), "M_PlasticWhite": (0.85, 0.85, 0.85),
    "M_Screen": (0.02, 0.03, 0.05), "M_Ceramic": (0.85, 0.83, 0.78),
    "M_Glass": (0.55, 0.70, 0.75), "M_Plant": (0.15, 0.40, 0.12),
    "M_PlantDark": (0.06, 0.22, 0.05), "M_Flower": (0.95, 0.80, 0.15),
    "M_FlowerRed": (0.80, 0.10, 0.10), "M_Rug": (0.62, 0.50, 0.33),
    "M_Paper": (0.92, 0.91, 0.86), "M_Photo": (0.35, 0.55, 0.30),
    "M_Gold": (0.80, 0.62, 0.20), "M_LampShade": (0.90, 0.84, 0.70),
    "M_Curtain": (0.85, 0.82, 0.74), "M_Bark": (0.25, 0.18, 0.12),
    "M_Soil": (0.20, 0.13, 0.08), "M_Grass": (0.25, 0.48, 0.15),
    "M_Terracotta": (0.65, 0.32, 0.18), "M_Rubber": (0.10, 0.10, 0.10),
    "M_Sky": (0.45, 0.65, 0.92),
    # room shell
    "M_WallPaint": (0.80, 0.77, 0.71), "M_Ceiling": (0.85, 0.84, 0.81),
    "M_Carpet": (0.45, 0.42, 0.38), "M_DoorTimber": (0.62, 0.47, 0.32),
}


def colour_for(name):
    base = name.split(".")[0]
    return PALETTE.get(base)
