# Wattleview Grove: Asset Shortlist

## 1. Purpose and status

| | |
|---|---|
| Date | 2026-10-26 |
| Status | **Identified, not purchased.** Nothing was bought, and no accounts were created or used. |
| Project | `D:\Unreal-Projects\WattleviewGrove-ue58`: UE 5.8.4, Blueprint-only, PICO 4 Ultra Enterprise. Earlier research notes that mention `WattleviewGrove58` mean an old scratch copy. Ignore it. |
| Audience | Lawrence (project lead), deciding what to buy later. |
| Meanwhile | Placeholders are being rebuilt in Blender with the free Poly Haven CC0 assets in section 3. |

This is one list of candidate assets for Maria Russo's room, the garden seen through the north-facing window, Maria's Italian kitchen-garden memory and the sky. Every entry was checked against the mobile VR budget. Section 5 covers the MetaHuman route for the cast.

**Budget applied to every entry:** 72 fps on standalone PICO (mobile forward renderer, Mobile HDR off, MSAA, baked lighting). That means modest polycounts, few materials per mesh, 1-2K textures, and no Nanite, Lumen, virtual textures or translucency-heavy assets. Every licence must allow use in an educational product.

**How the entries were checked**
- **Fab.** Listing data came from Fab's own JSON endpoints, read in a browser tab on 2026-10-26, because fab.com blocks plain fetches. Prices, licence tiers, tech specs, supported UE versions and the "Generated with AI" flag all come from that data. Gallery screenshots were not reviewed, so style match is not visually confirmed.
- **Dekogon packs.** Per-mesh contents and low-poly tri counts are in Notion docs that did not render. Contents such as the recliner, ceiling fan, vase, figurines and hose are inferred from tags and descriptions.
- **Poly Haven.** Slugs, CC0 status and polycounts came from polyhaven.com and api.polyhaven.com on 2026-10-26.

---

## 2. Recommended Fab purchases

### Licence, price and import notes

- **Fab Std** = Fab Standard License. The Personal and Professional tiers grant the same rights. The tier depends on the buyer's gross revenue: above USD 100k in the previous 12 months means Professional ([Fab licence docs](https://dev.epicgames.com/documentation/fab/licenses-and-pricing-in-fab)). If RMIT buys, Professional applies. **Budget on the Pro price.** It can be far above Personal: Megascans Common Basil Herb is USD 3.99 Personal but USD 39.99 Professional.
- **UE Mkt** = the legacy Unreal Engine Marketplace licence on migrated listings, sold at one price.
- **Prices are USD list prices.** Fab showed AUD for this account. Interior prices were captured in AUD and converted at about 1.42, the ratio implied by Fab's own tiers. Multiply by about 1.42 for AUD.
- **Sale.** Dekogon packs are 30% off until 1 Nov 2026, but the tables keep list prices as the budget figure.
- **Free items** still have to be claimed with an Epic account, which is Lawrence's step.
- **Engine versions.** Many packs stop at UE 5.3-5.7. Add such a pack to a project on its highest supported version, then Migrate the content into WattleviewGrove-ue58. **Never copy a pack's `DefaultEngine.ini` or other config.** It would break the PICO setup.
- **Import rules for every pack:**
  - Dekogon packs ship Nanite and low-poly duplicates. Use the low-poly meshes only, with Nanite off.
  - Cap Android textures at 1024-2048.
  - Merge or reduce materials.
  - Replace translucent glass and sheer fabric with opaque or masked materials.
  - Check lightmap UVs, since the lighting is baked.
  - On FBX assets with OpenGL normal maps, flip the normal map's green channel.

**Priority**
- **Must:** needed for the look, with no adequate free or quick Blender route.
- **Should:** saves clear time or quality over the Blender or Poly Haven route.
- **Could:** optional. It overlaps with free assets or is quick to model.

### 2.0 Summary: Must and Should

| Priority | Pack (publisher) | Pro price (USD) |
|---|---|---|
| Must | Rural Australia (Epic) | Free |
| Must, pick one | Vegetable Plants (Dexsoft Games) **or** 3D Farm & Vegetable Plants Mega Pack (HKhalife) | 59.99 or 69.99 |
| Should | Suburbs VOL.3 - Retro Furniture (Dekogon Studios) | 52.99 |
| Should | Hospital Room (3DEverything) | 29.99 |
| Should | Round Table And Chairs Game Prop (Vilson Pistori) | Free |
| Should | Virgin Mary (3D Scan) (Eddie Mauro), as a source mesh only | Free |
| Should | Garden Flowers Pack (letsmakecoolart) | 39.99 |
| Should | Garden Plants Pack (G-Star) | 19.99 |
| Should | Fig (TtjDjg) leaf atlas (ScansLibrary) | 14.99 |
| Should | Realistic Trees 2 (Defuse Studios) | 9.99 |
| Should | Lawn Grass surface (Quixel Megascans) | Free |
| | **Total, Must + Should** | **USD 227.93-237.93 (about AUD 324-338)** |

### 2.1 Interior furniture and fixtures

| Item | Pack (publisher) | USD Personal / Pro | Licence | UE / format | Mobile notes | Priority | Link |
|---|---|---|---|---|---|---|---|
| Period dining armchairs, dresser, clock, retro cabinet | Suburbs VOL.3 - Retro Furniture (Dekogon Studios) | 34.99 / 52.99 | Fab Std | Not captured | Nanite + low-poly duplicates: use low-poly. Contents from tags. On sale. | Should | [Fab](https://www.fab.com/listings/c00f221a-7054-4a74-b26a-e97e35318c90) |
| Small round table with chairs | Round Table And Chairs Game Prop (Vilson Pistori) | Free / Free | Fab Std | Not captured | Specs not captured: inspect after claiming. Poly Haven round_wooden_table_02 + GreenChair_01 meet the same need. | Should | [Fab](https://www.fab.com/listings/a3924239-c6a6-40a0-be7e-8d3165442aa1) |
| Tall floor lamp, interior fixtures (tagged ceiling fan) | Lighting VOL.1 - Interior (Dekogon Studios) | 24.99 / 37.99 | Fab Std | Not captured | Use low-poly. The cheaper ~USD 12.99 (AUD 18.48) tier is "UEFN - Reference only" and **cannot be used in UE**. Poly Haven has no floor lamp, but one is a quick Blender build. On sale. | Could | [Fab](https://www.fab.com/listings/2b4161a5-8a6b-438d-89fd-1cfaa5f82ddf) |
| Recliner by the window | Suburbs VOL.2 - Couches and Sofas (Dekogon Studios) | 29.99 / 34.99 | Fab Std | Not captured | **Recliner inferred from tags only: confirm before buying.** No mobile-ready lift recliner exists on Fab (see 2.6). On sale. | Could | [Fab](https://www.fab.com/listings/0ce37894-fa6c-47da-b63b-ea9e108b9e8a) |
| Wardrobe, bedside drawers | Old Furniture Props (Typical Tris) | 14.99 / 39.99 | Fab Std | UE 4.26-5.5: migrate | All textures 4096: downscale to 1-2K. 1 material + 66 MIs, has LODs. | Could | [Fab](https://www.fab.com/listings/ae2ae107-e3a0-4833-b907-3cb422af4644) |
| Wardrobe, bedside, bed (budget) | Vintage Bedroom (GamaLand) | 6.99 / 14.99 | Fab Std | UE <=5.5: migrate | Low-poly; textures 512-2048. | Could | [Fab](https://www.fab.com/listings/1af621e1-ff70-4293-859f-c7724541732c) |
| Armchairs, sofa, table, cabinet, clock, table lamp | Old Living Furniture Pack (Denisa Buta) | 9.99 / 19.99 | Fab Std | Not captured | Very low poly per the listing. | Could | [Fab](https://www.fab.com/listings/abef2444-c105-406f-93ce-2c6510135c9e) |
| Armchair, cabinet, overbed table, meal props | Hospital room pack (Danilo Guedes) | 14.99 / 17.99 | Fab Std | UE <=5.7: migrate | 2048 and 4096 textures: downscale the 4K. Its privacy curtain looks like a hospital ward, not a home. | Could | [Fab](https://www.fab.com/listings/3ef32c46-3796-4bb1-b980-7f5086de5b58) |
| TV (low cabinet sourced separately) | Flat Screen TV - Motel - Game Ready - PBR (PropHaus) | 1.99 / 6.99 | Fab Std | Not captured | Specs not captured. A TV is also a simple Blender box. | Could | [Fab](https://www.fab.com/listings/ced3031c-21af-4e1b-a304-e88501a36e64) |
| Ceiling fan | Ceilling fans collection (A.D) | 4.99 / 9.99 | Fab Std | Not captured | Specs not captured. Alternative: decimate Poly Haven ceiling_fan. | Could | [Fab](https://www.fab.com/listings/eb5ab0b9-42e2-4144-8ee2-8316f1a6e33d) |
| Rugs | Suburbs VOL.11 - Rugs (Dekogon Studios) | 14.99 / 22.99 | Fab Std | Not captured | Use low-poly. A bevelled plane with a CC0 texture also works. On sale. | Could | [Fab](https://www.fab.com/listings/6b7471d6-1f9f-4a69-9aaa-2a2f60684578) |
| Curtains | Curtains_pack Vol.1 (StAlker) | 29.99 (one price) | UE Mkt | UE <=5.3: migrate via a 5.3 project | 500-7,500 verts, no LODs, 5 materials / 31 MIs. Curtains are simple in Blender, so this buy is low value. | Could | [Fab](https://www.fab.com/listings/bbcf64b3-c740-476a-9c77-2301c3083f25) |
| Adjustable bed (reference) | Hospital - Hospital Bed 01 - PBR Game Ready (Dekogon Studios) | 5.99 / 9.99 | Fab Std | **FBX only, no UE format** | 8,007 tris, 3 meshes, 2 materials, 2K, OpenGL normals: flip the green channel in UE. Fine for mobile, but it is a hospital bed, not a domestic-style aged-care bed. Main use: reference for the Blender bed rebuild. On sale (AUD 5.96 / 9.94). | Could | [Fab](https://www.fab.com/listings/fb90615c-0f23-4fff-8a88-1cea9ea4b47d) |

### 2.2 Props

| Item | Pack (publisher) | USD Personal / Pro | Licence | UE / format | Mobile notes | Priority | Link |
|---|---|---|---|---|---|---|---|
| Water jug, plastic glass, clock, bedside table, chairs, lamps | Hospital Room (3DEverything) | 24.99 / 29.99 | Fab Std | **UE 5.5 only:** add to a 5.5 project, migrate to 5.8 | 47 models, 200-2,800 verts each, 1024 textures; 49 materials, no LODs. Best jug-and-glass source, since dedicated jug listings are 56k-112k tris. Give the glass an opaque material. | Should | [Fab](https://www.fab.com/listings/e8aa1d5c-47f0-44ab-ba3e-07c54876d25b) |
| Madonna figurine | Virgin Mary (3D Scan) (Eddie Mauro) | Free / Free | Fab Std | FBX / GLB / Blender only | **Needs decimation, not drop-in:** 145,602 tris / 72,803 verts in one mesh. Decimate in Blender to about 2-5k tris and bake normal + colour maps to 512-1K. | Should | [Fab](https://www.fab.com/listings/0e0f589c-47e4-4ded-96ae-da1a295508aa) |
| Hairbrush (story prop: David leaves it on the table at 4:30-5:00) | HairBrush pack (AG1983) | ~6.99 / ~8.99 (AUD 9.94 / 12.79) | Not captured | Not captured | 3 brushes, about 11k tris in total. Fine for mobile, but quick to model. | Could | [Fab](https://www.fab.com/listings/7e44751a-0d65-477e-9adc-9ea6af924d38) |
| Picture frames, family photo wall, photos on the wardrobe | Configurable Frames and Photos Set (PacoChan) | 19.99 / 19.99 | Fab Std | Not captured | Specs not captured. Poly Haven frames + postcards cover this. Use our own licensed photos. | Could | [Fab](https://www.fab.com/listings/84ab54d9-dbd7-4025-93a7-5c43ff924b1a) |
| Vase, figurines, small decor | Suburbs VOL.25 - Knick Knacks (Dekogon Studios) | 29.99 / 39.99 | Fab Std | Not captured | Use low-poly. Contents inferred from tags. On sale. | Could | [Fab](https://www.fab.com/listings/82d1eab5-bb6d-48bf-bf44-62b4d534ec9a) |

### 2.3 Exterior and garden

| Item | Pack (publisher) | USD Personal / Pro | Licence | UE / format | Mobile notes | Priority | Link |
|---|---|---|---|---|---|---|---|
| Australian eucalypts, native trees, logs, rocks | Rural Australia (Andrew Svanberg Hamilton, published by Epic) | Free | UE Mkt (legacy Epic content licence) | UE <=5.4: migrate | 85 photogrammetry meshes. Research rates it the only eucalypt source that can work on mobile. Per-mesh tris not captured: check them, and bake impostors for distant trees. | Must | [Fab](https://www.fab.com/listings/1c1467ce-a2f5-4be1-8988-9069f90a8571) |
| Kitchen-garden memory: tomatoes on stakes, potted basil, climbing beans | 3D Farm & Vegetable Plants Mega Pack - Game Ready Foliage (HKhalife) | 39.99 / 69.99 | Fab Std | **UE 5.7 only:** migrate | 52 meshes, 184 materials, textures up to 4096: downscale. Covers basil. | Must, pick one | [Fab](https://www.fab.com/listings/b8f99c18-72d8-4583-a0ad-0234da6c4792) |
| Tomatoes and other vegetables (lighter alternative) | Vegetable Plants (Dexsoft Games) | 19.99 / 59.99 | Fab Std | UE <=5.4: migrate | 50 meshes incl. tomatoes, peppers, zucchini, eggplant; has LODs; 2K. Better mobile spec, but no basil listed. | Must, pick one | [Fab](https://www.fab.com/listings/0140fd51-cc26-4036-ab03-4038621191b4) |
| Roses, peonies, climbing roses (Maria's flower garden) | Garden Flowers Pack (letsmakecoolart) | 29.99 / 39.99 | Fab Std | UE 4.26-5.7: migrate | 42 assets, up to 8,740 tris, 2K atlas. Instance sparingly in beds. | Should | [Fab](https://www.fab.com/listings/3efda6b5-448f-4174-94d9-c19d81bbb0c2) |
| Suburban shrubs, ivy, mixed flowers, grass | Garden Plants Pack (G-Star) | 13.99 / 19.99 | Fab Std | Not captured | 53 meshes. Specs not captured. | Should | [Fab](https://www.fab.com/listings/fc4db7e0-415a-4c09-8fd8-8446d4eedd27) |
| Fig tree (memory garden) | Fig (TtjDjg) (ScansLibrary) | 2.99 / 14.99 | Fab Std | Material | Scanned fig-leaf atlas, for leaf cards on a low-poly Blender fig. Fab has no mobile-ready fig tree. | Should | [Fab](https://www.fab.com/listings/374dadff-7809-4718-8e69-24a8f8203ca3) |
| Suburban trees behind the garden, through the window | Realistic Trees 2 (Defuse Studios) | 9.99 / 9.99 | Fab Std | Not captured | 45 trees in Urban, Fall and Dead sets. Described as mobile-friendly, but specs not captured. | Should | [Fab](https://www.fab.com/listings/70ddf6b7-18c6-4955-a320-80e4ad940918) |
| Main lawn surface | Lawn Grass surface (Quixel Megascans) | Free / Free | Fab Std | Not captured | 2x2 m scan. Make the lawn a textured ground plane: wall-to-wall alpha grass blows the overdraw budget. Poly Haven leafy_grass is the CC0 alternative. | Should | [Fab](https://www.fab.com/listings/f50d1f4a-d91a-41c2-86ad-10c4ffe7f658) |
| Grass cards for bed edges and the lawn border | Natural Grass Set Vol.01 (RT Assets) | 10.99 / 33.99 | Fab Std | Not captured | 20 grass meshes, listed as "Grass Region: Australia". Alpha cards: use sparsely. | Could | [Fab](https://www.fab.com/listings/24a34c22-9220-46e4-b694-3dc9bc389197) |
| Lots of flowering plants to fill beds | Flowers and Plants Nature Part 1 (Dragon Motion) | 29.99 / 59.99 | Fab Std | Not captured | 414 plants + 28 spline plants. Overlaps with G-Star and letsmakecoolart. | Could | [Fab](https://www.fab.com/listings/052dddb7-3b05-49ae-bf8f-f9234fd3ac05) |
| Raised flower beds, planters | Buildings VOL.16 - Flower Beds (Dekogon Studios) | 21.99 / 36.99 | Fab Std | Not captured | 197 meshes, half Nanite, half low-poly; low-poly tri counts unverified. On sale. Poly Haven planter_box_02 covers the basic need. | Could | [Fab](https://www.fab.com/listings/ea5cad22-a53e-41bc-a5f0-2169ecfdc2af) |
| Yard props: hose (tag only), outdoor chairs, statue, paths | Suburbs VOL.27 - Outdoor and Yard Spaces (Dekogon Studios) | 34.99 / 47.99 | Fab Std | Not captured | 277 meshes, Nanite + low-poly. 30% off until 1 Nov 2026. | Could | [Fab](https://www.fab.com/listings/01dc6bc8-c44a-42ce-8ead-0c435e87ae52) |
| Patio chairs, tables, bench | Backyard and Patio props (Tirgames Assets) | 29.99 / 59.99 | Fab Std | Not captured | 85 meshes. | Could | [Fab](https://www.fab.com/listings/ce6a2273-8d59-4bff-9ff9-1f9e10acf6bf) |
| General garden props: benches, pots, fences, 9 blueprints | Garden Environment (Dragon Motion) | 4.99 / 9.99 | Fab Std | Not captured | 84 meshes. Cheap general-purpose pack. | Could | [Fab](https://www.fab.com/listings/06003f78-9a59-4fb8-abbc-14dc276f0b4a) |

### 2.4 Sky

The preferred route is free: a CC0 Poly Haven pure-sky HDRI (section 3.3), tonemapped to an LDR equirect PNG at 2-4K on an unlit sphere or hemisphere. Mobile HDR is off, so the sky is only a backdrop; the sun patch on the floor comes from the baked directional light. The Fab skies are fallbacks, and none was confirmed to include a fully cloudless clear-blue sky.

| Item | Pack (publisher) | USD Personal / Pro | Licence | UE / format | Mobile notes | Priority | Link |
|---|---|---|---|---|---|---|---|
| Photographic sky dome | Skies (Leeyo Atelier) | 15.99 / 23.99 | Fab Std | Not captured; Windows target only | 25 equirect skies + sphere/hemisphere meshes. **8192x4096 sky textures: downscale to 2-4K for Android.** | Could | [Fab](https://www.fab.com/listings/965789b8-08e8-4c5a-a57b-0b69a497c1d0) |
| Photographic skies | Sky Pack: 25 Skies (Joost Vanhoutte) | 34.99 | UE Mkt | UE <=5.4 | 8192x2048, rated 4.92 from 25 reviews. Not fully checked. | Could | [Fab](https://www.fab.com/listings/1f3a46d5-d34a-48f8-8505-282ff862f426) |
| Photographic skies | Fantastic Skies Pack | 19.99 | UE Mkt | Not captured | **Not checked.** Publisher and link not captured. | Could | - |

### 2.5 On hold until RMIT has a policy on AI-generated assets

Fab marks these three `isAiGenerated=true`. Other packs were rejected for this flag, so these wait for RMIT's policy. None is needed, because Blender routes exist.

| Pack (publisher) | USD Personal / Pro | Notes | Link |
|---|---|---|---|
| Knitted Blanket Pack (WonderFuel) | 18.99 / 34.99 | **Dropped from the shortlist.** Also heavy: 19 materials, 95 textures at 2K, and 4,500-16,500 tris for each low-poly blanket. Build the crochet blanket in Blender instead. | [Fab](https://www.fab.com/listings/551a56a1-1504-46f5-a743-34140706969a) |
| Religious Paintings Vol. 1 (AJK 3D) | 19.99 / 29.99 (AUD 28.43 / 42.66) | Contents not checked. | [Fab](https://www.fab.com/listings/9e8381da-d449-458b-a981-58a476226de0) |
| Realistic Low Poly Eucalyptus Tree Pack 107M (Hadi Tree) | 2.99 | 2-3k tris, mobile-suitable on paper. The only cheap alternative to Rural Australia. | Not captured |

### 2.6 Checked and not recommended

| Pack (publisher) | USD Personal / Pro | Why not | Use instead | Link |
|---|---|---|---|---|
| The Retirement Home (Sousinho Games) | 54.99 / 94.99 | **Virtual textures, no LODs, 4K textures on hero props, UE <=5.6** (5.1-5.6). 233 materials / 225 MIs / 740 textures. It is the only aged-care room kit found. | Style and layout reference only | [Fab](https://www.fab.com/listings/c2c65cc2-4646-41d9-b80b-9da5dc2ebdb6) |
| Recliners ASHLEY (viz351) | 19.99 / 59.99 | **Not mobile-ready:** 13,454 / 17,932 / 23,619 verts per model, all textures 4096, no LODs, UE <=5.5. | Reference for the Blender lift recliner | [Fab](https://www.fab.com/listings/06ff78b7-7164-4658-858a-1016a6afb4bc) |
| Rosary (Francesco Milanese) | ~8.99 / ~19.99 (AUD 12.79 / 28.43) | 32.7k tris. | Blender curve + array of beads | [Fab](https://www.fab.com/listings/e4707f69-220a-420b-b7ee-a2b0216a08de) |
| Call Bell (weeray) | - | A counter/desk bell, not an aged-care pendant handset. | Blender | [Fab](https://www.fab.com/listings/325b5145-fbd1-4ef7-8feb-9547f6f12240) |
| Hose Reel (PropHaus) | 1.99 / 6.99 | 4K textures, no tech sheet. | Blender curve with bevel | [Fab](https://www.fab.com/listings/2a704e14-f4da-4429-8929-f1ba80735f29) |
| Common Basil Herb (Quixel Megascans) | 3.99 / 39.99 | Poor value at the Pro tier. | HKhalife potted herbs, or Blender | [Fab](https://www.fab.com/listings/f73ef585-d712-42ed-b969-f276f9f1e818) |
| Dedicated water-jug listings (e.g. Francesco Milanese 507d0ba1) | - | 56k-112k tris. | 3DEverything jug, or Poly Haven jug_01 | - |
| Infinity packs (UE0Infinity): ceiling fan, wardrobe, TV cabinet, floor lamp | - | Up to 3.6M tris; Substrate; Nanite. | - | - |
| Archinteriors Vol 14 (Evermotion, ba7128fc) | 89.99 | High-poly archviz. | - | - |
| Hospital Ward (papaya795) | - | Nanite + virtual textures. | - | - |
| Hotel low-poly pack (Ultima Store) | - | Marked AI-generated; 4K textures. | - | - |
| Family Portraits Photos (n3kded) | - | Marked AI-generated. | Our own licensed photos | - |
| Daz3D recliners | - | About 240k tris. | - | - |
| Ficus Carica (Razor 3D); Ultimate Farm Trees (CropCraft); fig FBX (gold3dlab) | 7.99; 39.99 / 99.99; 39.99 | Nanite or high-poly; CropCraft also uses 4K. | ScansLibrary fig leaf atlas + Blender | - |
| Australian Garden Essentials Pack 30 / Australian Native Trees Pack 31 (3DGardenPlants) | up to 249.99 | High-poly, no LODs, tuned for Lumen and dynamic lighting. | Rural Australia; cards | - |

**Seen but not shortlisted (not fully checked):**
- Hospital Room / 60 Assets (PackDev): ~USD 29.99 / 59.99 (AUD 42.66 / 85.34). UE 4.26-5.7, 1-4K textures, 77 materials. [Fab](https://www.fab.com/listings/f8f0a5b9-8260-40f4-8f9d-0507334a1df6)
- Modern Hospital Environment (Leartes, 48910fc0): ~USD 49.99 / 99.99 (AUD 71.12 / 142.25). UE 5.1-5.8, 4 LODs but 192 materials.
- Garden Flowers and Herbs Pack (Greenworks): USD 34.99, 264 meshes, 4 LODs down to billboards. UE <=5.3, desktop only.
- Sticky notes (n3kded): USD 9.99. Simple to model, and Poly Haven office_notepads already covers it. [Fab](https://www.fab.com/listings/f59528a8-d091-4da8-98f4-e8f44fd29a2e)

**Open questions for Lawrence**
- Who is the purchasing entity? That decides the licence tier. Budget here assumes Professional.
- What is RMIT's policy on AI-generated assets? It decides section 2.5.

---

## 3. Free Poly Haven CC0 assets we will use now

All are CC0: no attribution needed, and fine for commercial and educational use. Polycounts come from api.polyhaven.com on 2026-10-26. Download textures at 1-2K to match the 1024-2048 Android cap. The Blender MCP can pull these directly.

### 3.1 Models

| Need | Slug | Link | Notes |
|---|---|---|---|
| Bedside drawers | painted_wooden_nightstand | [link](https://polyhaven.com/a/painted_wooden_nightstand) | 470 tris. Drop-in. |
| Small round table | round_wooden_table_02 | [link](https://polyhaven.com/a/round_wooden_table_02) | 4,254 tris. |
| Armchairs at the round table | GreenChair_01 | [link](https://polyhaven.com/a/GreenChair_01) | 4,213 tris. Can be retextured with floral upholstery. |
| Recliner by the window (stand-in only) | mid_century_lounge_chair | [link](https://polyhaven.com/a/mid_century_lounge_chair) | 6,148 tris. Not a lift recliner; the Blender build replaces it. |
| Wardrobe covered in photos | painted_wooden_cabinet_02 | [link](https://polyhaven.com/a/painted_wooden_cabinet_02) | 966 tris. Scale it to wardrobe proportions; add photos as postcard or plane meshes. |
| Low cabinet under the TV | small_wooden_table_01 | [link](https://polyhaven.com/a/small_wooden_table_01) | 3,410 tris. |
| Ceiling fan | ceiling_fan | [link](https://polyhaven.com/a/ceiling_fan) | **16,356 tris: decimate in Blender to about 2-3k.** |
| Day-date clock (frame and body only) | wall_clock | [link](https://polyhaven.com/a/wall_clock) | 3,658 tris. Analogue: replace the face with a day-date texture. |
| Family photos (standing frames on the drawers and table) | standing_picture_frame_02 | [link](https://polyhaven.com/a/standing_picture_frame_02) | 2,986 tris. Swap in our own licensed photos. |
| Wall photograph of young Enzo | hanging_picture_frame_02 | [link](https://polyhaven.com/a/hanging_picture_frame_02) | 3,678 tris. The picture is a MetaHuman portrait render (section 5). |
| Water jug | jug_01 | [link](https://polyhaven.com/a/jug_01) | 5,770 tris. Ceramic, so it looks domestic rather than like a care-home plastic jug. |
| Vase | ceramic_vase_02 | [link](https://polyhaven.com/a/ceramic_vase_02) | 2,756 tris. Modern style. |
| Cushions on the recliner and bed | throw_pillows_01 | [link](https://polyhaven.com/a/throw_pillows_01) | 6,362 tris. Red patterned fabric: retexture with a floral. |
| Sticky notes beside the calendar | office_notepads | [link](https://polyhaven.com/a/office_notepads) | 666 tris. |
| Memory box (stand-in) | CheeseBox_01 | [link](https://polyhaven.com/a/CheeseBox_01) | 884 tris. A round wooden box; model a proper keepsake box later. |
| Photos and cards stuck to the wardrobe | postcard_set_01 | [link](https://polyhaven.com/a/postcard_set_01) | 2,720 tris. Swap textures for family photos. |
| Potted plant on the windowsill or table | potted_plant_04 | [link](https://polyhaven.com/a/potted_plant_04) | 6,097 tris, a succulent. The only light Poly Haven potted plant: potted_plant_01 is 96k, _02 is 70k. |
| Raised kitchen-garden bed, flower-bed edging | planter_box_02 | [link](https://polyhaven.com/a/planter_box_02) | **10,944 tris: decimate.** |
| Terracotta pot for basil (pot only) | planter_pot_clay | [link](https://polyhaven.com/a/planter_pot_clay) | 3,080 tris. Mossy, worn finish. |
| Garden hose (memory garden) | garden_hose_wall_mounted_01 | [link](https://polyhaven.com/a/garden_hose_wall_mounted_01) | **11,684 tris: decimate**, or build a bevelled curve. |
| Garden bench seen through the window | painted_wooden_bench | [link](https://polyhaven.com/a/painted_wooden_bench) | 630 tris. |
| Flower beds (colour) | flower_gazania | [link](https://polyhaven.com/a/flower_gazania) | **25,819 tris: do not instance across beds.** Use it as a card or texture source, or place it very sparsely. |
| Bed and border filler | shrub_sorrel_01 | [link](https://polyhaven.com/a/shrub_sorrel_01) | 3,319 tris. Instance sparingly. |
| Garden tree | jacaranda_tree | [link](https://polyhaven.com/a/jacaranda_tree) | **312,356 tris: bake an impostor or billboard in Blender.** Every Poly Haven tree is 150k-17M tris. |

### 3.2 Textures

| Need | Slug | Link | Notes |
|---|---|---|---|
| Painted plaster wall | beige_wall_001 | [link](https://polyhaven.com/a/beige_wall_001) | |
| Timber-look floor | laminate_floor_02 | [link](https://polyhaven.com/a/laminate_floor_02) | |
| Light timber: furniture, trim, skirting, door | white_oak_veneer | [link](https://polyhaven.com/a/white_oak_veneer) | |
| Carpet | dirty_carpet | [link](https://polyhaven.com/a/dirty_carpet) | Poly Haven's only carpet. Faded and discoloured: clean up the albedo. |
| Floral fabric: cushions, upholstery, bedspread | floral_jacquard | [link](https://polyhaven.com/a/floral_jacquard) | Poly Haven's only floral fabric. Dark (black) base: re-tint. |
| Plain fabric: curtains, bed linen | rough_linen | [link](https://polyhaven.com/a/rough_linen) | |
| Crochet blanket (stand-in texture) | wool_boucle | [link](https://polyhaven.com/a/wool_boucle) | Looped wool, not granny-square crochet. A stand-in until a crochet texture is made. |
| Jute rug | hessian_380 | [link](https://polyhaven.com/a/hessian_380) | Apply to a bevelled plane. |
| Ensuite floor tiles | interior_tiles | [link](https://polyhaven.com/a/interior_tiles) | |
| Garden soil: vegetable and flower beds | farm_soil | [link](https://polyhaven.com/a/farm_soil) | |
| Lawn | leafy_grass | [link](https://polyhaven.com/a/leafy_grass) | Apply to ground planes. Every Poly Haven grass mesh is 200k-1.6M tris. |
| Tree bark (eucalypts) | bark_bluegum | [link](https://polyhaven.com/a/bark_bluegum) | |

### 3.3 Sky HDRIs

| Need | Slug | Link | Notes |
|---|---|---|---|
| Clear blue sky, midday: **recommended primary** | qwantani_noon_puresky | [link](https://polyhaven.com/a/qwantani_noon_puresky) | Tagged clear and midday, with no "partly cloudy" tag. Confirm visually. |
| Clear sky, midday (alternative) | kloofendal_43d_clear_puresky | [link](https://polyhaven.com/a/kloofendal_43d_clear_puresky) | Tagged both "clear" and "partly cloudy", so it may show cloud. **Check visually before choosing it.** |
| Clear sky, lower sun | syferfontein_18d_clear_puresky | [link](https://polyhaven.com/a/syferfontein_18d_clear_puresky) | Sun at 18 degrees, tagged morning-afternoon. A reference for a longer sun patch on the floor. |

Mobile route: the HDRIs are 16-24K. Tonemap one to an LDR equirect PNG at 2-4K and map it onto an unlit sphere or hemisphere, since Mobile HDR is off.

---

## 4. Gaps: no good source, model in Blender

| Item | Why there is no good source | Blender approach | Reference / partial source |
|---|---|---|---|
| Adjustable aged-care bed in domestic style (timber head and foot boards, floral bedding) | Fab has hospital beds, or The Retirement Home (unsuitable). Poly Haven old_bed_frame is a 50k-tri rusty metal frame; vintage_day_bed is a daybed. | Rebuild with 2 materials and 1-2K textures. | Dekogon Hospital Bed 01 (8k tris) for the mechanism and proportions |
| Lift recliner | Nothing mobile-ready: the Ashley models are 13-24k verts with 4K textures; Daz3D's are about 240k tris. | Model, with floral or vinyl upholstery. | Ashley models as reference; mid_century_lounge_chair as stand-in |
| Nurse call bell / pendant (the "buzzer") | Only desk and counter bells. | A simple handset with a cable. | - |
| Day-date dementia clock | Only generic digital and alarm clocks. | Use the wall_clock body or a box, with a day-date face texture. | wall_clock |
| Wall calendar with sticky notes | Only generic desk or flip calendars. | Plane + printed texture. | office_notepads for the notes |
| Memory box | Only generic wooden or jewellery boxes. | A lidded box with photos and keepsakes. | CheeseBox_01 stand-in |
| Rosary | The Fab rosary is 32.7k tris. | Curve + array of beads, plus a small crucifix. | - |
| Crochet blanket | The Fab pack is AI-flagged and heavy, and there is no granny-square texture. | A cloth-draped plane + a granny-square texture. | wool_boucle stand-in |
| Floral textiles: curtains, bedspread, cushions | No floral, mobile-ready set. | Simple meshes + a floral texture. | floral_jacquard (re-tint), throw_pillows_01 |
| Curtains and rod | None on Poly Haven; the Fab pack is low value. | Cloth sim or sculpted folds. Opaque, no sheers. | rough_linen |
| Rug geometry | None on Poly Haven. | Bevelled plane. | hessian_380, dirty_carpet |
| Flat-screen TV | Poly Haven has only CRTs. | Box + screen material. | PropHaus TV (USD 1.99 / 6.99) if preferred |
| Tall floor lamp | None on Poly Haven. | Lathe or cylinder + shade. No translucency. | Dekogon Lighting VOL.1 (Could) |
| Drinking glass | Translucency costs too much; none on Poly Haven. | An opaque or masked "plastic" cup. | 3DEverything plastic glass |
| Hairbrush (story prop) | A Fab pack exists but is optional. | Quick model. A 1K texture is enough. | HairBrush pack (AG1983) |
| Madonna figurine | No mobile-ready figurine. | Decimate the free Virgin Mary scan to about 2-5k tris and bake 512-1K maps, or model a simple one. | Virgin Mary (3D Scan) |
| Crucifix, holy pictures, prayer cards | No mobile-ready set; the AJK paintings are AI-flagged. | Planes and frames with our own licensed or public-domain images. | - |
| Family photos | AI-flagged portrait packs were rejected. | Our own licensed photos in Poly Haven frames and postcards. Young Enzo comes from a MetaHuman render. | standing/hanging_picture_frame_02, postcard_set_01 |
| Fig tree | Fab's fig trees are Nanite or high-poly. | Low-poly trunk + leaf cards. | ScansLibrary fig leaf atlas |
| Kitchen-garden props: tomato stakes, twine, wire cages, terracotta pots, watering can | No good mobile pack. | Simple builds. | planter_pot_clay |
| Garden hose | No dedicated mobile hose. | Curve with a bevel. | garden_hose_wall_mounted_01 (decimate) |
| Australian native shrubs (grevillea, bottlebrush, kangaroo paw) | High-poly only, with no LODs. | Cards from photos or scans, at distance only. | - |
| Tree impostors | Poly Haven trees are 150k-17M tris. | Bake impostors or billboards. | jacaranda_tree, Rural Australia |
| Room architecture: north-facing window frame, door, skirting, ceiling | Poly Haven has no interior kit. | A modular Blender kit with lightmap UVs. | beige_wall_001, white_oak_veneer |
| MetaHuman clothing: David's uniform, Enzo's work shirt, Maria's dress and cardigan | Only WI_DefaultGarment ships with MetaHuman. | Model the garments and skin them to the MetaHuman body skeleton (section 5). | - |

---

## 5. MetaHuman pipeline for UE 5.8 on PICO

**Basis**
- UE 5.8.4 source: `Engine/Plugins/MetaHuman/MetaHumanCharacter`, mainly `MetaHumanCharacterEditorSubsystem.h` and `Subsystem/MetaHumanCharacterBuild.h`.
- Epic's bundled Python examples in `Content/Python/examples`.
- A headless editor probe in a throwaway scratch project. It copied the preset Walter, opened it for editing, read the 1,397 face-model coefficients and the 30 body measurements, applied an aged skin texture and generated the face textures locally. Assembly then stopped at "Character is not rigged", as expected.

No project files were edited.

### 5.1 The one manual blocker: Epic MetaHuman cloud sign-in

- **The stored token has expired.** A headless test on 2026-10-26 found a stored Epic MetaHuman cloud token on this machine that no longer works. The error is `EOS_Auth_InvalidRefreshToken`, logged as "Auto-Rigging of Face failed with code Login Failed".
- **What it blocks.** Face auto-rigging and the texture-source download are cloud calls, and assembly will not run until both are done. **Rigging, texture download and assembly are all blocked until Lawrence signs in.**
- **Action (Lawrence, once).**
  1. Open WattleviewGrove-ue58 in the editor.
  2. Start a cloud action on a MetaHuman Character, such as Auto-Rig.
  3. Sign in with his own Epic account when the EOS Account Portal browser window opens.
- **After sign-in.** EOS stores a persistent token, and the Python steps then run unattended, including headless `UnrealEditor-Cmd`. Don't pass `-NoMetaHumanAccountPortalLoginFallback` on the sign-in run, because it turns off the browser sign-in. If the token expires again, the same error comes back.
- **Limits.** Claude cannot sign in or create accounts. Character data is sent to Epic's MetaHuman services.

Two prerequisites need approval or an install, not manual editor work:
- **Enable the plugin.** Add `{"Name": "MetaHumanCharacter", "Enabled": true}` to `WattleviewGrove-ue58/WattleviewGrove.uproject`, then restart the editor.
  - On 2026-10-26 the .uproject enabled only OpenXR, PICOController, PythonScriptPlugin, EditorScriptingUtilities and UnrealMCPython.
  - The plugin is `EnabledByDefault=false` and `IsBetaVersion=true`, and it pulls in MeshModelingToolset, LiveLink and others.
  - This is a project-file edit, so it needs Lawrence's go-ahead.
- **Install Core Data.** Add the launcher's optional "MetaHuman Creator Core Data" component for UE 5.8.4 (see the project's CLAUDE.md).

### 5.2 What is scriptable

| Step | Python? | How / notes |
|---|---|---|
| Enable plugin | Text edit | See 5.1. Needs approval. |
| Cloud sign-in | **No** | Manual, once (5.1). |
| Create character | Yes | `EditorAssetLibrary.duplicate_asset('/MetaHumanCharacter/Optional/Presets/<Name>', '/Game/MetaHumans/Src/<Char>')`. The UI's `InitializeFromPreset` is C++ only. There are 29 presets, shipped without rig or textures. Presets with "High" wrinkles: Grace, Lani, Lorenzo, Sook-ja, Walter. |
| Open for edit | Yes | `try_add_object_to_edit` / `remove_object_to_edit`. Works in a commandlet. |
| Face shape | Partly | Mix the 1,397 face coefficients of two or three presets (`get_face_model_coefficients` / `set_face_model_coefficients`, then `commit_face_state`). Move the 91 landmarks with `translate_face_landmarks`. Per-region blending is C++ only. To fit to a Blender head: `import_from_template` / `conform_to_target_meshes`. |
| Body | Partly | 30 constraints via `get_body_constraints` / `set_body_constraints`, then `commit_body_state`. Includes Height (136.6-222.6 cm), Fat, Masculine/Feminine, Muscularity, Waist and Hip. The fixed/legacy body type is not exposed: use the UI, or a preset that already has it. A stooped posture belongs in animation. |
| Skin and ageing | Yes | `commit_skin_settings`: tone u/v, face/body texture index, roughness, freckles, redness. Runs locally, no cloud call. High-wrinkle face texture indices (from `texture_attributes.json`): 4, 11, 19, 20, 21, 47, 48, 50-55, 69, 70, 71, 90, 109, 120, 121, 127, 140, 151. Source has no age slider. |
| Eyes, teeth, lashes | Yes | `commit_eyes_settings` (sclera tint for age). `commit_head_model_settings` (teeth `worn_down`, `plaque_amount`, `receding_gums`; lashes `salt_and_pepper`). |
| Grooms | Yes | Add wardrobe items to the Hair, Eyebrows, Beard, Mustache, Eyelashes and Peachfuzz slots; grey them with `Whiteness` / `Melanin`. 95 groom items ship. |
| Clothing | Partly | Only WI_DefaultGarment ships. Make garments in Blender and skin them to the MetaHuman skeleton. Wrapping one as a Wardrobe Item may need the UI, because `PrincipalAsset` was not confirmed settable from Python. Simpler on mobile: attach it after the build as a Leader Pose skeletal mesh and mask the hidden body faces. |
| Face auto-rig (cloud) | Yes, after sign-in | `request_auto_rigging` with `rig_type=JOINTS_ONLY`, `blocking=True`. Blendshapes exist only at LOD0, which mobile never uses. |
| Texture source download (cloud) | Yes, after sign-in | `request_texture_sources` with `blocking=True`. Assembly requires it. |
| Assemble | Yes, after both cloud steps | `build_meta_human` with `pipeline_type=OPTIMIZED`, `pipeline_quality=MEDIUM`, output to `/Game/MetaHumans`. |
| Custom pipeline: own LODs, texture caps, follicle-map size | Partly (UI) | Python cannot reach these properties. Make a child Blueprint of `BP_DefaultLegacyPipeline_Medium` and edit it in the UI, then remap it in `Config/DefaultMetaHumanCharacter.ini` (plain text). Fallback with no UI: stock Medium plus the post-build hardening below. |
| Post-build mobile hardening | Yes | Texture `max_texture_size` (2048 head/body, 1024 eyes/teeth/hair) and `never_stream`. Set min LOD so LOD3 is the best Android LOD. Turn groom physics off. Save with `save_asset(path, only_if_is_dirty=False)` and confirm the .uasset mtime changed. |
| Place in level | Yes | Place the built Actor Blueprint and drive it from Sequencer. `spawn_meta_human_actor` gives only a transient preview. |
| Young Enzo photo | Yes | Duplicate Enzo and mix the face 60-70% toward a younger male preset (Mateo, Jorge or Dominic). Use low-wrinkle skin and dark hair (Melanin about 0.8, Whiteness 0). Do a Cinematic build on desktop only, render one portrait with HighResShot or Movie Render Queue, apply sepia, and use it as a 1K texture in the frame. No runtime cost. |
| Facial animation | Partly | Bake audio-to-face (MetaHuman Animator) offline in the editor, then play it through Sequencer. |
| Headset measurement | Manual | Package, deploy, and read stat unit and metrics with the headset worn (the proximity sensor gates rendering). |

### 5.3 Cast starting points

| Character | Base | Body | Skin and grooms | Build quality |
|---|---|---|---|---|
| Maria (82) | Mix of High-wrinkle presets (candidates: Grace, Lani, Sook-ja). Check in the viewport that she reads as an Italian woman in her 80s. | About 155 cm, softer, fuller | High-wrinkle index. Grey `WI_Hair_S_Updo` or `WI_Hair_M_BobCurly`. Right-arm injury as a skin decal (Story V2). | Medium |
| David (early 30s) | Mix of younger male presets | About 178 cm | Low-wrinkle index, medium stubble. `WI_Hair_S_Clean`, `WI_Beard_S_Stubble`. | Medium |
| Enzo (late husband) | Lorenzo or Walter base | **Same as David.** Story V2 has Enzo share David's body rig and animation so the two can cross-fade in place. The research suggested a 170 cm, heavier Enzo, which conflicts with this: Lawrence to decide. | High-wrinkle index. Grey `WI_Hair_S_RecedeMessy` or `WI_Hair_S_HairLoss`, plus `WI_Mustache_S_Full`. | Medium |
| Young Enzo (photo) | Copy of Enzo (see 5.2) | - | Dark hair, low wrinkles | Cinematic, desktop render only |
| Gardener | Any preset | - | - | Low (seen at a distance only) |

Preset picks came from texture attributes, not thumbnails, so check each one visually before committing.

### 5.4 Recommended mobile settings

| Area | Setting | Basis |
|---|---|---|
| Build | UE Optimized, **Medium**: face LODs 3/5/7, body LODs 1/2/3. LOD3 head textures baked at 2K, generated face textures at 1K, body at 2K. | Pipeline defaults read from the engine |
| Low tier | Face LODs 5/7 (about 560 head verts, 70 joints), body 2/3, generated textures at 512. Distant characters only, such as the gardener. Too coarse for Maria at under 1 m. | Same |
| Best Android LOD | LOD3: head about 2,500 verts, body about 1,507, hair cards about 3,000 verts, 283 face joints. No blendshapes or animated maps. | Epic platform table |
| Textures | Max 2048 for head and body; 512-1024 for eyes, teeth and hair. The follicle map is 4K in every tier: cap it with device-profile `MaxLODSize=2048` or a per-texture `max_texture_size`. Keep virtual-texture outputs off. | Epic |
| Hair | Cards or meshes only (strands need geometry the device lacks). Prefer brows, stubble and peach fuzz pre-baked into the skin, which is automatic at face LOD5 and below, over separate groom components. | Engine source; Epic |
| Rig | `JOINTS_ONLY`, and keep `bOptimizeBoneCounts=True`. Leave `bUnpackRigLogic=False` unless profiling says otherwise. | Engine source |
| Skin | Keep the baked MetaHuman skin (Subsurface Profile). In 5.8 source, mobile forward shades it with a pre-integrated curvature lookup and no screen-space pass, so it works with forward + MSAA. **That contradicts the project README** ("Subsurface Profile -> mobile deferred"). Not yet verified on the PICO; the fallback is a Default Lit material instance on the head. | Engine source |
| Android cvars, in `Config/Android/AndroidEngine.ini` `[ConsoleVariables]` | `Compat.MAX_GPUSKIN_BONES=75`; `r.EarlyZPass=3`; `r.Mobile.EarlyZPassOnlyMaterialMasking=1`; `r.HairStrands.MinLOD=3`. Optionally `r.HairStrands.UseCardsInsteadOfStrands=1`, but only if every groom has cards; otherwise the hair is invisible. | Epic Android recommendations |
| Early-Z check | The current AndroidEngine.ini, from the VR template, says a full depth pre-pass is slow on standalone XR. Measure the early-Z settings on the headset before keeping them. | Project config |
| Lighting | Characters are movable. They get stationary or movable direct light plus volumetric-lightmap indirect light from the baked scene. Tune brightness on the device only (Mobile HDR off, so no exposure). | Project notes |
| Draw calls | Keep Mobile Multi-View on (the template default). After the first build, check `BP_MetaHuman_Legacy_Medium` for translucent eye-occlusion or tear meshes, and remove them if the build allows. | - |

### 5.5 Risks

- **Cloud dependency.** Rigging and texture download need Lawrence's Epic sign-in, and the stored token has already expired once. Character data goes to Epic.
- **Beta plugin.** MetaHumanCharacter is marked `IsBetaVersion=true`, and Python API signatures changed between 5.6, 5.7 and 5.8.
- **Pipeline settings aren't scriptable.** LOD lists, texture caps and follicle-map size need either a child Blueprint edited in the UI or a post-build fix-up pass.
- **Preset duplication.** The UI's preset path also aligns the face DNA to the body and resets cached skin data, while duplicating copies the asset as-is. Take one character through rigging and assembly before building all three.
- **Unverified preset picks.** They were chosen from texture attributes, not by looking at them.
- **VR performance.** LOD3 carries 283 face joints, over the 75-bone limit for one draw, so meshes split into many sections and draw calls. Each character also costs RigLogic CPU time.
  - Three animated MetaHumans at 72 fps on the XR2 Gen 2 is unproven.
  - The Enzo/David cross-fade renders two full characters at once, with dithered opacity.
  - The headset measurement decides. LOD5 (70 joints) is the fallback for background shots.
- **Mobile skin shading** is unverified on the device (see 5.4).
- **Hair cards** can shimmer under MSAA in LDR, and groom binding needs GPU skinning/compute on Vulkan. Test early; baked or mesh hair is the fallback.
- **Clothing** has to be modelled and skinned in Blender. ChaosOutfitAsset resizing adds complexity; a Leader Pose attachment is simpler.
- **Silent saves.** `save_asset` defaults to saving only if dirty, so programmatic edits can silently go unsaved. Always pass `only_if_is_dirty=False` and check the mtime.
- **Licensing.**
  - Per Epic's search snippet and CG Channel's coverage, MetaHumans made with UE 5.6 or later fall under the standard UE EULA. They are free under USD 1M revenue, and may be used in workflows that include AI tools but not to train or improve AI models.
  - The full licence page needs a login and was not read. Read it before relying on these terms.
  - The old Maria asset (5.5 era) was made under the previous MetaHuman EULA. Re-authoring in 5.8 removes that ambiguity.
  - Third-party Fab hair or outfits carry their own licences.

### 5.6 Sources

- [MetaHuman platform support and LOD specs](https://dev.epicgames.com/documentation/metahuman/platform-support-and-lod-specifications-for-metahumans)
- [MetaHuman requirements and configuration settings](https://dev.epicgames.com/documentation/metahuman/requirements-and-configuration-settings-for-metahumans-in-unreal-engine)
- [MetaHuman 5.7 release notes](https://dev.epicgames.com/documentation/metahuman/metahuman-5-7-release-notes)
- [MetaHuman license page](https://www.metahuman.com/license) (login required)
- [CG Channel on the June 2025 licence change](https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/)
- [Fab licences and pricing](https://dev.epicgames.com/documentation/fab/licenses-and-pricing-in-fab)
