# Character recreation reference

Updated: 28 October 2026

## Intent

Recreate the Wattleview Grove cast as MetaHumans from the approved character concepts.  Anatomy,
identity, age, hair and body proportions are reviewed before any final garments are built.  The
production room uses the approved reference-v1 assemblies while garment development continues.

## Approved concept mapping

| Character | Concept image | Direction |
|---|---|---|
| Maria | `SourceArt/Characters/References/Concepts/Maria_Elderly_Concept.png` | Provisional elderly version. Rebuild only after Maria at about 40 is approved, preserving the younger identity's eyes, nose, mouth, cheekbones and jaw while adding age, silver hair and posture changes. |
| Maria (about 40) | `SourceArt/Characters/References/Concepts/Maria_Enzo_Young_Photo_Concept.png` | Master Maria identity, based on the photograph and 1980s references: thick dark hair with an open forehead, centre or soft side part, strong crown volume and broad turned-out curls around the jaw and shoulders; light warm-olive complexion; expressive dark eyes; oval face; defined cheekbones; refined prominent nose; narrower lower face; and subtle age detail appropriate to approximately 40. This is not the short silver style intended for Maria at 80. Avoid both caricature and an over-smoothed youthful face. |
| David | `SourceArt/Characters/References/Concepts/David_CareWorker_Concept.png` | Younger male care worker, lighter complexion, neat dark hair, friendly face and average-fit build. Glasses and staff accessories are a later garment/accessory pass. |
| Gardener | `SourceArt/Characters/References/Concepts/Gardener_Concept.png` | Older outdoor worker, receding grey hair, full grey beard and stockier practical build. He replaces the current outdoor mannequin after approval. |
| Enzo (about 40) | `SourceArt/Characters/References/Concepts/Maria_Enzo_Young_Photo_Concept.png` | Italian man at approximately 40, matching the age shown in the photograph: dark swept-back hair, clean-shaven face, warm Mediterranean colouring and a healthy average build. He is not an elderly interpretation. |

## MetaHuman source assets: reference v1

The following source assets are the reproducible identity masters:

- `/Game/MetaHumans/Src/MariaReference`
- `/Game/MetaHumans/Src/MariaAge40Reference`
- `/Game/MetaHumans/Src/DavidReference`
- `/Game/MetaHumans/Src/GardenerReference`
- `/Game/MetaHumans/Src/EnzoReference`

Their reproducible specifications live in:

- `SourceArt/Characters/References/character_reference_v1.json`
- `SourceArt/Characters/References/maria_reference_v1.json` (Maria's initial isolated pass)

Preview renders are in `Saved/MetaHumans/` as `<Name>_front.png`,
`<Name>_three_quarter.png` and `<Name>_full.png`.

## Current status

- The reference set contains five source characters: elderly Maria, Maria at about 40, David,
  the gardener and Enzo at about 40.
- Maria and Enzo's age-40 versions are derived from the same photograph and retain an explicitly
  Italian/Mediterranean identity direction.
- Maria at about 40 is the master identity. Elderly Maria remains provisional and is not a likeness
  target for the younger character; she will be aged forward from the approved age-40 version.
- All five references were auto-rigged, downloaded and assembled as Optimized/Medium MetaHumans on
  28 October 2026. Runtime assemblies are under `/Game/MetaHumans/<ReferenceName>`.
- `/Game/Wattleview/Maps/L_ResidentRoom` now uses `BP_MariaReference`, `BP_DavidReference`,
  `BP_EnzoReference` and `BP_GardenerReference`. Maria at about 40 is assembled separately as
  `BP_MariaAge40Reference` for the later memory/story pass and does not replace elderly Maria.
- Each production character currently wears the approved neutral default outfit: a white T-shirt
  and white shorts. This outfit is locked for the current Pico review build.
- Retargeted idle, walk and sit clips are stored per approved body under
  `/Game/Wattleview/Animations/MH/<ReferenceName>`, and `LS_Story` has been rebound to the replacement
  actors and those clips.
- Glasses, identification badge, jewellery, cast, gardener hat/apron/gloves, shoes and final story
  clothing remain deferred until the anatomy and identity pass is accepted.

## Pico review build

- Development/ASTC build produced and installed on the connected PICO 4 Ultra Enterprise on
  28 October 2026.
- Artifact: `Build/Profiles/PICO/Development/20261028-151913/Android_ASTC/`
- Package: `com.rmit.wattleviewgrove` (version `0.1.0`, version code `1`).
- Device-side launch reached `com.epicgames.unreal.GameActivity` with the process alive and no
  immediate fatal exception. The headset was asleep during the automated launch check, so visual
  comfort, appearance and performance still require an in-headset review after waking it.

## Review rule

Approve each character from front, three-quarter, profile/full-body and neutral-pose views.  Do not
accept a character because an outfit hides neck, shoulder, arm or torso defects.

Character sheets use a medium-grey background and a neutral inspection-light rig: broad soft key
and fill, restrained skylight, readable shadows and protected highlights. Skin, pale hair and the
white inspection garment must retain texture and tonal detail; clipped or glamour-style highlights
are a failed validation render. All characters use the same rig and front, three-quarter and
full-body framing so comparisons are meaningful.
