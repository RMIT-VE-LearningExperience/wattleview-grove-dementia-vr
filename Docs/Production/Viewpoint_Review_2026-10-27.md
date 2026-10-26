# Viewpoint capture review — 27 Oct 2026

An independent review of the six baked viewpoint captures (`Saved/Captures`, desktop SceneCapture right after the Production bake).
Six critics reviewed one viewpoint each and produced 58 raw findings. A skeptic re-checked every finding against the images, `placement.json` and the scripts, rejected 7 and merged the rest into the items below.
Brightness was out of scope: the desktop render is not truthful for the PICO, which has no exposure on mobile LDR.

Severity, then verdict: **confirmed** means clearly visible; **plausible** means likely but ambiguous. *Headset* means only judgeable on the device.

## 1. Gaze-start marker in the default David view: the caption renders dark brown on a busy background, and the disc sits on the window right beside the white gardener
*high · confirmed* — seen in VP_David_Door

- **Object:** StartTarget / StartTarget_Disc / StartTarget_Text (build_gaze_start.py, build_story_director.py)
- **Evidence:** In a 3x crop of VP_David_Door, 'Look at the light to begin' samples about RGB 116,83,39, but the script sets 235,225,205. The text sits over the sill, the geraniums, the vase flowers and the jug. The script never assigns a material, so the TextRender keeps its default lit material and is shaded. Seen from behind in VP_David_Seated it comes out near-white, which confirms the lighting dependence. The disc and ring (disc 238,236,229) straddle the centre mullion and sit next to the off-white gardener mannequin, so two white shapes compete for 'the light'. The runtime position does not fix this. Anchor_David t=0 is (105,40,165) at yaw 29.4 deg, so the marker lands at about (244,119,165), only about 2 deg right of the editor spawn and still over the window.
- **Fix:** build_gaze_start.py: give StartTarget_Text an unlit or emissive text material, and add a dark semi-opaque backing plate behind the disc and caption. build_story_director.py: add a per-view offset so the David marker lands on plain wall near Maria and the photo (for example yaw about -20 deg, or a fixed point around (300,70,150)), away from the window and the gardener.
- **Status:** **Fixed (27 Oct).** Caption uses UnlitText. David's marker turned -32° onto the plain wall between Maria and her photo (picked from candidate renders).

## 2. In Maria's view the gaze-start marker spawns about 100 cm behind the photo wall, so the student cannot see it
*high · confirmed* — seen in VP_Maria_Standing, VP_Maria_Seated

- **Object:** BP_StoryDirector marker placement with Anchor_Maria
- **Evidence:** No marker appears in VP_Maria_Standing, because the editor spawn (220,100,160) is behind the camera. The director wiring sets StartTarget = Anchor location + forward x GAZE_DISTANCE (160), with no trace and no per-view override. Anchor_Maria t=0 is (355,60,155) at yaw -90, so the marker lands at (355,-100,155), behind the wall at y=0 that holds Photo_Frame. GAZE_COS 0.993 gives a 6.8 deg cone. The print centre (z 147.5, 60 cm away) is 7.1 deg off that axis, so looking at the photo does not start the story, while glancing just above it starts the story with no visible prompt. This finding comes from the script logic; the capture cannot show it.
- **Fix:** build_story_director.py: line-trace along the anchor's forward vector and place the marker at min(GAZE_DISTANCE, hit - 10-20 cm), or add a per-view override. For Maria, the photograph could itself be the target (marker about (355,2,147.5), caption below the frame), with the gaze cone widened to about 0.985 for near targets.
- **Status:** **Fixed (27 Oct).** Per-view marker distance and yaw in BP_StoryDirector (`GAZE_VIEW`): Maria's marker is 50 cm out, in front of the photo. The marker scales with distance, so it covers the same angle in every view.

## 3. Both MetaHumans face about 90 deg away from their blocking direction: Maria looks at the window, not at Enzo's photo
*high · confirmed* — seen in VP_David_Door, VP_David_Seated, CAM_Corner

- **Object:** Maria_StandIn (BP_Maria), David_StandIn (BP_David); build_characters.place, build_story_sequence MESH_YAW_OFFSET
- **Evidence:** Maria stands at the photo spot (355,68), but in VP_David_Seated she is in clean profile facing +X (the window). In VP_David_Door her back is to the door and she faces the window. In CAM_Corner her face is toward the window-side camera. Her blocking is facing -90 (at the photo). David at the door faces about -X+Y (back to CAM_Corner, profile left in Seated) instead of 45 deg into the room. Both are off by the same +90 deg. stand_in() sets actor yaw = facing - 90 for the mannequin (which faces +Y). build_characters.place() reuses that actor rotation for the MetaHuman BPs, and build_story_sequence keys facing + MESH_YAW_OFFSET(-90) for MetaHuman actors too. So LS_Story will play with the same error. The Door critic blamed level placement versus frame 0; that is refuted, because the level placement for Maria already matches t=0 (355,68,-90).
- **Fix:** Correct the Body component's relative yaw inside BP_Maria, BP_David and BP_Enzo so each faces actor +Y like the mannequin. Or apply an extra -90 deg for MetaHuman-tagged actors in both build_characters.place() and build_story_sequence (is_mh offset). Re-run and confirm that Maria faces the photo at t=0 and David walks forwards.
- **Status:** **Fixed, with a different cause (27 Oct).** The Body orientation was correct (the MetaHumans face actor +Y like the mannequin), and LS_Story keys the right yaw. The level placement students see before the gaze had drifted from t=0, and the bodies had no idle. build_story_sequence.py now poses every blocking actor at its t=0 key and loops the retargeted idle on MetaHuman bodies.

## 4. Pure-black (0,0,0) pocket the full height of the window's east reveal, behind the right curtain and above the TV cabinet
*high · confirmed* — seen in VP_Maria_Seated, VP_David_Table

- **Object:** Curtains (right panel) / window reveal / Wall_East corner at x~480-500, y~400-450; TV_Cabinet top
- **Evidence:** In VP_Maria_Seated, pixels at (1465,80), (1465,320) and (1446,700) are exactly 0,0,0. They form a full-height slot between the right curtain panel and the window reveal and continue below the sill. The left reveal reads 110-180 per channel. VP_David_Table shows the same corner as an exact-black wedge between the curtain's outer fold and the TV, running onto the cabinet top at its window end (20,150 = 5,5,5). The black band directly under the screen is mostly the TV's own black bezel and stand, so it is not part of the defect. import_room_assets.py never makes M_Curtain Two Sided, although the review hand-off requires it, so texels facing the back of the single-sided curtain bake black.
- **Fix:** Make M_Curtain Two Sided, or give the panels thickness (the Solidify from audit issue 6). Consider turning off static shadow casting on the sheer curtain. Re-bake Production, then re-sample (1465,250) in VP_Maria_Seated and the TV-corner wedge in VP_David_Table; both should be well above 0.
- **Status:** **Partly fixed (27 Oct).** MI_Curtain is now two-sided and re-baked. The slot is dark brown now (mean RGB about 32,26,15), not 0,0,0. Check it on the headset.

## 5. Maria's cardigan texture aliases into high-contrast glyph noise
*high · confirmed · headset* — seen in VP_David_Door, VP_David_Seated, CAM_Corner

- **Object:** M_Cardigan (import_garments.py: wool_boucle, detail, strength 0.6, tiling 4.0); also the recliner and bed plaid throws
- **Evidence:** At 6x zoom the cardigan back in VP_David_Door is a blocky, letter-like speckle with no readable knit. The same speckle covers the whole garment in VP_David_Seated and CAM_Corner, and it is the noisiest surface in each frame, on the character the student watches. The plaid throws are high-contrast but still read as plaid on the desktop.
- **Fix:** import_garments.py: change M_Cardigan tiling 4.0 to about 1.5 and strength 0.6 to about 0.2-0.3, and keep full mip chains (no NoMipmaps or sharpen). Optionally lower the plaid contrast on the throws. Judge the result on the PICO, which has MSAA but no TAA.
- **Status:** **Mitigated (27 Oct).** Cardigan strength lowered 0.6 → 0.3 and tiling 4 → 1.5. Judge on the PICO. The plaid throws are unchanged.

## 6. CAM_Corner was moved by hand to the opposite (window-side) corner; a flat slab 15 cm from the lens blocks the left third, and the opening beat sits at the right edge
*medium · confirmed* — seen in CAM_Corner

- **Object:** CAM_Corner actor vs cam('CAM_Corner') / VIEWPOINTS['Anchor_Corner'] (80,330,225)
- **Evidence:** The frame shows the gallery wall (y=450) and the wardrobe wall head-on, with the window on the left. That is only possible from near (480,30), not from the scripted (80,330,225), which sits beside the bed. CAM_Corner is referenced only in build_resident_room.py, and the 26 Oct Lighting/Production capture already shows this hand-placed pose. A flat tan slab with a dark brown edge covers about x 100-580. In the 26 Oct capture that area showed curtain folds and the TV cabinet, so the slab is most likely the rebuilt curtain panel's end, point-blank. It hides the TV, the cabinet and Chair_Third. The photo and David are squeezed against the right edge. At runtime the Corner view uses Anchor_Corner at the scripted position, so this capture does not show what the student sees, and the next run of build_resident_room.py will silently move the camera back.
- **Fix:** Decide which corner to use, then write the same transform into cam('CAM_Corner') and VIEWPOINTS['Anchor_Corner']. Keep the camera at least about 30 cm from the curtain (x <= 445 if it stays on the window side). Have capture_viewpoints.py warn when CAM_Corner and Anchor_Corner differ.

## 7. Default launch framing: the recliner hides Maria from the hips down and the shot centres on the window and empty floor
*medium · confirmed* — seen in VP_David_Door

- **Object:** VP_David_Door / Anchor_David t=0 (105,40,165) -> (300,150,130); Recliner (285,51)
- **Evidence:** The recliner's wing, arm and throw fill about x 220-720, y 585-900, and Maria shows only from the hips up behind it. The frame centre is the window and the gardener. The photograph Maria is meant to be looking at is a small object at x 240-300, and the calendar is cut in half at the left edge. This is the first view every student gets.
- **Fix:** Change Anchor_David t=0 and cam('VP_David_Door') together. Either re-aim at about (340,80,135), so the recliner drops into the corner and Maria and the photo frame the shot, or step in to about (120,135,165). Re-capture.

## 8. Editor and pre-gaze state differs from LS_Story t=0: the gardener sits at the wrong spot hugging the mullion, and the cast is probably unanimated until the gaze completes
*medium · plausible · headset* — seen in VP_David_Door, VP_Maria_Seated

- **Object:** Gardener_StandIn (build_resident_room.py (745,300) vs BLOCKING t=0 (745,460)); BP_StoryDirector; intro fade
- **Evidence:** Confirmed part: the gardener is spawned at (745,300,-20) facing 180, but LS_Story keys him at (745,460,-20) facing 190. In VP_Maria_Seated he is cut by the centre mullion with his legs in the flower bed. In VP_David_Door he stands right beside the gaze disc. Inferred part: the director creates the LevelSequencePlayer but calls Play only after the gaze completes, so during the gaze period the student probably sees the level transforms with no body animation (Maria in A-pose), not just the editor. The intro fade is keyed [(0,1),(1.5,0)], so starting the story snaps to black.
- **Fix:** Set the level spawns to the BLOCKING t=0 transforms. Give the MetaHumans an idle outside the sequence, or evaluate LS_Story at t=0 at BeginPlay without playing it. Make the intro a short fade-out then fade-in instead of a snap to black. Have capture_viewpoints.py evaluate the sequence at each view's beat time (for example about 0:50 for VP_Maria_Seated).
- **Status:** **Partly fixed (27 Oct).** The gardener and the cast are now at their t=0 marks with an idle. Evaluating the sequence at BeginPlay is still open.

## 9. Blocky lightmap seams on the jug and vase, the nearest props in the centre of Maria's seated view
*medium · confirmed* — seen in VP_Maria_Seated, VP_David_Seated

- **Object:** Jug (SM_Jug), Vase (SM_Vase)
- **Evidence:** At 3x zoom the jug in VP_David_Seated shows vertical bright and dark rectangular blocks and hard steps that do not follow its shape. At 4x the vase in VP_Maria_Seated shows a vertical seam with a sideways step at mid-height. Neither mesh is in LIGHTMAP_RES, so default_lightmap_res() gives objects under 25 cm only 32 px. The jug's faceted grey handle and its 0.45 lightmap coverage are already in the review.
- **Fix:** Add SM_Jug and SM_Vase at 128 (and the small tabletop props at 64) to LIGHTMAP_RES, or set the tabletop props to use the volumetric lightmap (ForceVolumetric). Re-bake.
- **Status:** **Fixed (27 Oct).** Lightmap resolution is now 128 for the jug and vase and 64 for the call bell. Re-baked. The glass and hairbrush are Movable story props with no lightmap, so their look comes from the volumetric lightmap and the dynamic shadow.

## 10. Garment necklines: skin wedges poke out past the collar on both MetaHumans, and David's polo collar floats
*medium · confirmed* — seen in VP_David_Door, VP_David_Seated, CAM_Corner

- **Object:** BP_Maria cardigan, BP_David polo (import_garments.py fits)
- **Evidence:** CAM_Corner (2.5x): thin skin-coloured wedges stick out sideways over David's shirt at both shoulders, and an irregular black patch sits at his nape. VP_David_Seated (5x): David's collar is a thin dark strip lying diagonally across the back of his neck, with skin between it and the shirt yoke. VP_David_Door (6x): two small orange skin wedges stick out at Maria's shoulders on either side of the pale collar. Maria's case alone would be ambiguous, but David's is clear.
- **Fix:** Re-fit or re-weight the garment necklines to the neck and clavicle bones, or mask the body faces under the garments. Re-check in the A-pose and in the seated pose.

## 11. Sky shows through dashed slits along the window head and sill
*medium · confirmed · known* — seen in VP_David_Door

- **Object:** SM_WindowFrame / wall reveal
- **Evidence:** At 3x zoom, evenly spaced pale sky-blue dashes run along the window head (two rows) and along the sill edges. That colour can only come from the sky showing through a gap. The review lists a 2 mm slit round the frame as a light-leak risk; this render confirms it.
- **Fix:** Extend the frame lining and window board about 0.5-1 cm into the reveal, or add backing strips, then re-export SM_WindowFrame. Mark the slit as confirmed in Room_Asset_Review.md.

## 12. Parts of the viewer's own MetaHuman show at the bottom of Maria's POV
*medium · plausible · headset* — seen in VP_Maria_Standing

- **Object:** Maria_StandIn (BP_Maria) vs the director's BodyMaria/HiddenBody; capture_viewpoints.py
- **Evidence:** At 3x zoom, scattered dark dots and dithered maroon-brown strands rise from the bottom edge (x 600-850, y 780-900). The camera (355,60,155) is 8 cm in front of Maria's root at eye height. capture_viewpoints.py hides nothing. At runtime the director hides HiddenBody, but build_characters.place() destroys and respawns the stand-in and never re-links StoryDirector.BodyMaria. If the director was built before the swap, the reference is stale and IsValid skips the hide.
- **Fix:** Re-run build_story_director.py after build_characters.py (or re-link BodyMaria/BodyDavid in place()). Hide the viewer's own body in capture_viewpoints.py for the VP_Maria_* and VP_David_* captures. Verify in PIE with ?view=Maria.
- **Status:** **Capture-only, fixed (27 Oct).** capture_viewpoints.py hides the viewer's body and the start marker. At runtime the director hides the body.

## 13. All five gallery frames above the bed show the same blank olive insert
*medium · confirmed* — seen in VP_David_Door, CAM_Corner

- **Object:** Gallery_0..Gallery_4 (SM_PhotoFrame_Small/Wide picture slot)
- **Evidence:** Every gallery frame shows a flat olive fill (about 150,135,79) with no image, in both views. PHOTOS in import_room_assets.py only sets up SM_PhotoFrame_MariaEnzo. In a dementia room these frames should read as memory cues, not as empty frames.
- **Fix:** Create five M_Photo instances with period family photos (allow about 13% margin, because the picture UVs run under the mat) and assign them per Gallery actor.

## 14. Rug reads as a flat orange slab, with a dotted seam line just inside its stepped edge
*low · confirmed · headset* — seen in VP_David_Table, VP_David_Door

- **Object:** Rug (SM_Rug, M_Rug)
- **Evidence:** At 1.5x zoom the rug is a uniform saturated orange-tan close to the chair and table timber, and a 1-px dotted light line runs parallel to its sawtooth edge about 10 cm inside it. The pinked-felt fringe is already in the review; the flat colour and the dotted line are not.
- **Fix:** Cool and lighten the M_Rug tint, or add a larger-scale border pattern. Weld the fringe to the rug body (no coplanar overlap) so the dotted line goes away.

## 15. Young Maria's blouse in the wall photo shows skin and grey patches at the shoulders and stands off the body; the pose is stiff
*low · confirmed* — seen in VP_Maria_Standing

- **Object:** T_Photo_MariaEnzo (SKM_Maria_Outfit on BP_MariaYoung, shoot_wall_photo.py)
- **Evidence:** At 6x zoom, skin and grey patches poke above both shoulders of the boxy blouse. The couple stand apart with their arms hanging, and her eyes have pale rims. This is baked into the hero photo, viewed from 60 cm.
- **Fix:** Refit the outfit to the young body, add a pose (arm-in-arm or arm around her) in shoot_wall_photo.py, fix the eye repaint, then re-shoot and re-grade.

## 16. TV screen is a flat, uniform pale-blue glow
*low · confirmed* — seen in VP_David_Door, VP_David_Table

- **Object:** TV_Screen (M_TVScreen 'news' constant in build_perception_layer.py)
- **Evidence:** The screen samples a uniform 155,183,207 with no image. It reads as 'no signal' and is the brightest, most saturated object on its side of the frame, although the story needs news on, including a man on screen at 0:45.
- **Fix:** Feed a news still or media texture into M_TVScreen at a modest emissive strength.

## 17. Thin blue-grey line along the door architrave's outer edge
*low · confirmed* — seen in VP_David_Seated, CAM_Corner

- **Object:** SM_DoorFrame / door cut in the y=0 wall
- **Evidence:** At 3x zoom there is a continuous dotted blue line along the right architrave's outer edge in VP_David_Seated, and the same dotted blue line runs along the door frame in CAM_Corner. Nothing on that wall is blue, so it is most likely void or sky showing through a gap.
- **Fix:** Overlap the architrave onto the wall face by about 1 cm and close the jamb return. Add a dark backing box behind the door.

## 18. Wardrobe door gaps and plinth render as broken dashes, with a dotted bright line at the floor
*low · confirmed · headset* — seen in CAM_Corner, VP_David_Table

- **Object:** Wardrobe (SM_Wardrobe)
- **Evidence:** In CAM_Corner (2x) the door gaps and panel grooves are dashed dark lines and the base-to-floor junction is a row of light dots. VP_David_Table shows a black toe-kick strip along the base.
- **Fix:** Widen the reveals and bevels (at least 4-5 mm) and close the interior behind them. Close the plinth to the floor and repack UV1 (audit issue 11).

## 19. Blocky brightness steps along the cornice
*low · confirmed* — seen in VP_David_Door

- **Object:** SM_Cornice lightmap
- **Evidence:** At 2x zoom the cornice above the window wall changes brightness in hard rectangular steps along its run. The review notes that half its lightmap is spent on hidden faces.
- **Fix:** Unwrap UV1 as a continuous strip per wall with fewer islands, raise the lightmap resolution, and re-bake.

## 20. Bed linen hems show black hairlines, and the upright pillow reads as a hard plate
*low · confirmed* — seen in VP_David_Door

- **Object:** SM_BedLinen
- **Evidence:** At 2x zoom there are thin black lines along the bedspread hem and the sheet fold, and the upright pillow at the headboard has a thin, rigid silhouette.
- **Fix:** Give the hems a thin Solidify or a rolled edge plus lightmap padding, round the pillow edge, and re-bake.

## 21. Hairline seams at the room's inside corners (one bright, one dark)
*low · plausible* — seen in VP_David_Door, VP_David_Table

- **Object:** Shell wall corners (window-wall corner and the corner behind the bed head)
- **Evidence:** VP_David_Door shows a 1-2 px pale line along the full height of the window-wall corner. VP_David_Table shows a crisp near-black line in the corner behind the bed head (29,8,4 against 53-71 on either side). The review flags buried corner strips and duplicated corner volumes.
- **Fix:** Trim the overlapping corner volumes so each wall ends at the inside face, keep a 2% UV1 margin, and re-bake.

## 22. VP_David_Table is pitched about 49 deg down and pressed against the table and Maria's chair
*low · confirmed* — seen in VP_David_Table

- **Object:** cam('VP_David_Table') (360,150,165) -> (335,200,100)
- **Evidence:** The pitch works out to -49 deg. The frame is mostly tabletop, empty seat and carpet, and the bed head and clock are cut by the top edge. The eye is about 16 cm outside the table rim. This is a review camera only, not an Anchor_David key.
- **Fix:** Match it to the 0:09 key (332,112,165) looking at (355,60,150), or pull back and aim at about 25-30 deg pitch.

## 23. VP_David_Seated capture shows the 0:00 layout, not the 4:00 seated beat it is meant to check
*low · confirmed* — seen in VP_David_Seated

- **Object:** cam('VP_David_Seated') (348,262,115) vs Anchor_David 240 s key (368,268,118); capture_viewpoints.py
- **Evidence:** The frame centre falls on the empty recliner. Maria is standing at the photo and Chair_Second has not been moved in. The camera is about 21 cm from the 4:00 anchor.
- **Fix:** Set the camera to the 240 s anchor and evaluate LS_Story at 240 s before capturing.

## 24. Gaze text reads mirrored and washes out over the calendar and wardrobe in the review captures
*low · confirmed* — seen in VP_David_Seated, CAM_Corner

- **Object:** StartTarget_Text (two-sided TextRender, editor spawn yaw -150)
- **Evidence:** The caption reads backwards in both captures, and 'Look' disappears against the calendar in VP_David_Seated. At runtime the director turns the marker to face the active anchor, so the mirroring only affects captures and the editor, but it contaminates every review image. Inference only, not visible: the runtime Corner marker (anchor (80,330,225), 160 cm along yaw -41) lands at about (201,225,225), which is near the ceiling fan's height and radius (fan at (250,225), min_z 225), so check it for a clash with the spinning blades.
- **Fix:** Hide the Story/Start folder in capture_viewpoints.py except for the view the marker faces. Check the Corner marker position against the fan in PIE with ?view=Corner.
- **Status:** **Capture-only, fixed (27 Oct).** capture_viewpoints.py hides the editor-placed marker.

## 25. Hairbrush bristles render as sparse, broken one-pixel sticks
*low · confirmed · headset* — seen in VP_David_Seated, VP_David_Table

- **Object:** SM_Hairbrush
- **Evidence:** At 3x zoom the pins are thin dark vertical strokes, some disconnected from the pad. This is the key story prop, about 70 cm from the seated viewer.
- **Fix:** Use a masked bristle card or a normal-mapped pad with fewer, thicker pins.

## 26. Window has no glazing, so it reads as an open hole
*low · confirmed · headset* — seen in VP_Maria_Seated, VP_David_Door

- **Object:** SM_WindowFrame (glass deliberately omitted)
- **Evidence:** Neither pane shows any reflection, tint or sheen, and the garden is perfectly crisp right up to the frame, although the story describes the gardener as seen through glass.
- **Fix:** Add one cheap low-opacity or additive quad per sash, with no shadow casting and excluded from the bake.

## 27. Carpet reads as mottled or stained
*low · plausible · headset* — seen in VP_David_Table

- **Object:** M_Carpet (dirty_carpet, strength 0.55)
- **Evidence:** The floor shows blotchy light patches and streaks about 10-20 cm across, especially in the right half of the frame. The judgement is subjective, but it fits the 'dirty_carpet' source texture.
- **Fix:** Swap in a clean loop-pile texture, or lower strength to about 0.2 and raise tiling to 2-3.

## 28. Photo mat bevel shows a dark rust strip on its left inner edge
*low · confirmed* — seen in VP_Maria_Standing

- **Object:** SM_PhotoFrame_MariaEnzo mat bevel
- **Evidence:** At 5x zoom the left inner bevel is a 2-3 px dark brown band, while the top bevel is light.
- **Fix:** Assign the bevel faces to M_Paper, or give them their own lightmap island or a higher resolution.

## 29. No contact shadow under the characters' feet
*low · plausible · headset* — seen in CAM_Corner

- **Object:** MetaHuman characters (movable, in a baked scene)
- **Evidence:** In CAM_Corner, David's shoes on the carpet near the door show little or no grounding shadow. A movable skeletal mesh gets no baked shadow. The flat-black clothing is an exposure effect and is not reported.
- **Fix:** Add a cheap blob-shadow decal or card under each character's feet.

## 30. Wall photo crop and content: the mat cuts off Enzo's crown and both couples' feet, the print is full of placeholder low-poly plants, and the backdrop is crushed dark
*low · confirmed · known* — seen in VP_Maria_Standing

- **Object:** SM_PhotoFrame_MariaEnzo / T_Photo_MariaEnzo
- **Evidence:** Enzo's hair touches the top of the opening and the feet are cut off at the bottom. The fig leaves are flat stars, and the background behind the couple is near-black.
- **Fix:** Re-map the photo UVs to the visible opening, or widen the border in grade_wall_photo.py. Re-shoot after the revised fig and tomato meshes land, and raise the black floor.

## 31. Already-known asset items, confirmed in these captures
*low · confirmed · known* — seen in VP_David_Table, VP_David_Door, VP_Maria_Seated, VP_David_Seated

- **Object:** DayDateClock screen black; curtain pleat and hem razor edges plus the outer fold on the TV cabinet; vase daisy dark-green centres; low-poly garden trees, shrubs and flower beds; fence moire; recliner throw ragged edge; call bell on the table; Chair_Third flat back pad lining up with the sill; jug faceted handle
- **Evidence:** Each is visible as described by the critics: clock screen samples 10,10,10, thin stepped pleats, oversized dark daisy centres, faceted foliage, diagonal dash bands on the fence, flat throw with a torn-looking rear edge, the call bell's dangling coiled cord, and the chair rail lining up with the window board. All are already in Room_Asset_Review.md or the intersection audit.
- **Fix:** As already listed in the review and the audit: the MI_DayDateClockScreen override, Two Sided plus Solidify for the curtains, a brown slot for the flower eyes, the Fab foliage replacements, LOD or closed gaps for the fence, tucking the throw edge, moving the call bell, crowning Chair_Third's back pad, and smoothing the jug handle.

## Rejected by the skeptic

- Faint lightmap smudges and blocks on Wall_North around the photo frame: They are not visible at normal contrast in VP_Maria_Standing; the critic only saw them after a contrast stretch.
- Oversized black blotch on the west wall behind the recliner arm: At 2x zoom it reads as a plausible baked cast shadow of the recliner arm from the window light, with a soft, shaped edge, not as a leak or an invalid-texel artifact.
- David reads as a flat black cut-out: The near-black clothing in CAM_Corner comes from back-lighting and exposure (David's polo shows navy with folds in VP_David_Seated), and brightness is on the expected list. Only the contact-shadow part is kept, as plausible.
- Pre-gaze level placement explains Maria facing the window: Refuted. The level spawn (355,68) facing -90 already equals LS_Story t=0. The facing error is a MetaHuman mesh yaw offset, which is reported separately; only the gardener's spawn differs from the sequence.
- Black band under the TV screen in VP_David_Table: Most of that band is the TV's own black bezel and stand, which are black in every view. Only the exact-black wedge at the window corner is an artifact, and it is merged into the black-reveal item.
- Wardrobe pure-black toe-kick (as a separate defect): A shadowed recessed plinth is expected to be dark. Only the dashed and dotted line shimmer is kept, merged into the wardrobe item.
- Couple posed as a stiff lineup (as a separate item): This is a subjective composition note, merged into the young-Maria photo item rather than reported on its own.
