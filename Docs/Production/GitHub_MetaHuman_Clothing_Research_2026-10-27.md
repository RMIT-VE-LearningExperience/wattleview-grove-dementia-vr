<!-- Research sweep run 27 Oct 2026 (four GitHub/web searches, three verification passes, one synthesis). Research only: nothing was cloned, installed or run. -->

# MetaHuman garments for Wattleview Grove: GitHub and engine research

**Scope.** I checked about 70 candidates. "Verified" means I read the README, source or licence on the web or through read-only `gh`. "Inferred" means my own reasoning, not tested. Nothing was cloned, installed or run.

**Licence rule of thumb.** GPL tools are fine as internal tooling. Code we port into our own scripts should come from MIT, BSD or Apache sources: rin-23, yamahigashi, GarmentCode, FreeSewing, Dem Bones. MetaHuman meshes and DNA stay under Epic's MetaHuman terms whatever tool touches them. The research notes say derived assets are restricted to use with UE. That conflicts with my recollection that Epic loosened this around UE 5.6. I did not verify either. It doesn't matter while everything stays in UE.

## Bottom line

- **P2 and P3 are best solved by the engine, not by GitHub.** UE already has GeometryScript `TransferBoneWeightsFromMesh` with `InpaintWeights`, which implements the same Epic paper as the GitHub repos. It also has the MetaHuman wardrobe **hidden face maps**. GitHub adds four things: a full-torso source body in Blender (Character DNA), armhole and sleeve-cap maths to port for P1 (GarmentCode, FreeSewing), offline cloth-to-weights (Dem Bones), and cheap skirt motion (KawaiiPhysics).
- **Test this first (inferred, cheap to check).** The Optimized body's missing torso is probably the default T-shirt's `BodyHiddenFaceMap` being applied at assembly. In the 5.7/5.8 source, `RemoveAndShrinkGeometry` runs on the body mesh at assembly. If we re-assemble Maria with the default top removed, the same build may give a full-torso body. That would be the ideal weight-transfer source.
- **The PC editor and the headset may not match.** Epic's LOD spec says mobile uses body LOD3 at best, and body correctives exist only at LOD0–1. Garment weights tuned on `clavicle_out` or `upperarm_out/fwd` in the PC editor may behave differently on the PICO (inferred). Judge garments against the LOD that ships.
- **Nothing on GitHub builds a low-poly set-in or raglan sleeve procedurally.** We write that ourselves, porting the maths from GarmentCode and FreeSewing.
- **Version.** Two of the picks below depend on the 5.8 move: hidden face maps on plain skeletal-mesh garments (pick 2), and the local MCPython copy, which is pinned to 5.7 (pick 8).

---

## 1. Top picks

### 1. UE built-in weight transfer: GeometryScript `TransferBoneWeightsFromMesh` (InpaintWeights) + `SkinWeightModifier` (relevance 9)

- **Links:** [TransferBoneWeightsOptions (Python API)](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/GeometryScriptTransferBoneWeightsOptions), [StripLODGeometry](https://dev.epicgames.com/documentation/unreal-engine/API/Editor/SkeletalMeshEditor/USkeletalMeshEditorSubsystem/StripLODGeometry)
- **What it is:** Epic's in-engine version of "Robust Skin Weights Transfer via Weight Inpainting", plus a scriptable skin-weight editor.
- **Solves:** P3 (main), P4, P7, P5.
- **How we'd use it:** a post-import step in our MCPython garment importer.
  1. Copy the full-torso body and the garment into DynamicMeshes with `copy_mesh_from_skeletal_mesh`.
  2. Call `transfer_bone_weights_from_mesh` with `INPAINT_WEIGHTS`, `OutputTargetMeshBones=TargetBones`, RadiusPercentage about 0.05, NormalThreshold about 30 and SmoothingStrength about 0.1 (the Chaos Cloth node's defaults).
  3. Leave `LayeredMeshSupport` on, so the blouse collar under the cardigan transfers correctly.
  4. Put an `InpaintMask` on the sleeve-cap ring and the collar band, so those are inpainted rather than copied.
  5. Write back with `copy_mesh_to_skeletal_mesh`.
  6. Run `SkinWeightModifier`: `EnforceMaxInfluences(4)`, `PruneAllWeights(0.01)`, `NormalizeAllWeights`, `CommitWeightsToSkeletalMesh`.
  7. Use `prune_bone_weights` to strip head and face bones that leak into collars.

  One script covers Maria, David and Enzo, and re-skinning needs no Blender round trip.
- **Related APIs:**
  - `StripLODGeometry(mesh, LOD, mask, threshold)` builds per-outfit body LODs from a UV0 mask. Its convention is the reverse of the hidden face maps: non-black pixels strip triangles.
  - `RemoveHiddenTriangles` (fast winding number) works on a merged body+garment mesh.
  - Use these on the body only; don't strip the RigLogic-driven face.
- **Licence:** UE EULA.
- **Maturity:** shipping engine API. The 5.8 Python pages are labelled Experimental. I verified the headers in the local 5.7 and 5.8 installs.
- **Caveats:**
  - It needs a source body with a torso (see the Bottom line and pick 3).
  - The DynamicMesh round trip may lose morph targets, LODs or bone attributes (inferred risk; check this).
  - The transfer itself has no influence cap.
  - Forum reports (unverified) say collars pick up head influence.

### 2. MetaHuman wardrobe hidden face maps: `HeadHiddenFaceMapTexture` / `BodyHiddenFaceMapTexture` (relevance 8)

- **Link:** [UMetaHumanOutfitEditorPipeline](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MetaHumanDefaultEditorPipeline/UMetaHumanOutfitEditorPipeline)
- **What it is:** per-garment masks that delete, and optionally shrink, face and body skin triangles when the MetaHuman is assembled.
- **Solves:** P2 (the proper fix for the shoulder-skin skirt), P4, P6, P5.
- **How we'd use it:** replace the WPO sink in the skin material.
  1. Register the cardigan, blouse, polo and flannel as wardrobe items on each MetaHuman Character asset.
  2. Paint a head map in the face mesh's UV space: black where the skirt is covered (removed), a grey band at the neckline. Paint a body map for the torso and the arms under sleeves.
  3. Set `MaxShrinkDistance` to about 0.3–0.5 cm. The default is 0, which means off; with a value, edges are pulled in rather than cut.

  The triangles are removed once, at assembly, on every LOD. That means no per-frame cost and fewer triangles at LOD3.

  To make the masks procedurally (inferred workflow): run a CharMorph-style ray test of each garment against the face and body meshes in Blender, then bake the covered vertices into a texture in the matching UV layout.
- **Version support:**
  - 5.6: body map only.
  - 5.7: head and body maps, but only on the Chaos Outfit pipeline.
  - 5.8: also on plain skeletal-mesh wardrobe items, so our Blender garments qualify after the 5.8 move.
- **Licence:** UE EULA / MetaHuman EULA.
- **Maturity:** production (part of the shipping Creator pipeline). Verified in the local engine source.
- **Caveats:**
  - It applies only to wardrobe items plus a re-assembly, not to meshes attached directly to the actor (inferred from the code path).
  - The Creator preview uses a material mask, while assembly removes geometry. Check the assembled mesh, not the preview.
  - When several garments carry maps, they are merged, but the thresholds reset to defaults and the largest shrink distance wins.
  - Driving it from Python means setting the pipeline's properties and triggering assembly (inferred, untested).

### 3. Full-torso MetaHuman in Blender: [poly-hammer/character-dna-addon](https://github.com/poly-hammer/character-dna-addon) + the build pattern from [creategamecharacters/metahuman-to-glb](https://github.com/creategamecharacters/metahuman-to-glb) (relevance 8 / 6)

- **What it is:**
  - Character DNA imports `head.dna` and `body.dna` from a DCC export and evaluates RigLogic live in Blender, including the body RBF correctives.
  - metahuman-to-glb shows `MetaHumanCharacterEditorSubsystem.build_meta_human(...)` with pipeline type CINEMATIC, OPTIMIZED or DCC, from stock UE Python with no C++.
- **Solves:** P3, P5, P1 (a fitting surface), P2, P7.
- **How we'd use it:**
  1. In UE, script a DCC build of Maria, David and Enzo, following metahuman-to-glb stage 00.
  2. In headless Blender 5.0, import `body.dna`. It gives a full torso and the real skeleton. Use it as the fitting surface for the garment generator and as the weight-transfer source.
  3. With RBF evaluation on, pose arm raise, forward reach and shrug, so the correctives move as they do in UE. Measure garment clipping per pose before the FBX export.
- **Licence:** Character DNA is GPL-3.0; it bundles MIT OpenRigLogic, and its Pro tier is paid. metahuman-to-glb is MIT.
- **Maturity:**
  - Character DNA: usable, open beta, 0.14.5 (2026-10-20). Its manifest covers Blender 4.5–5.3; it is tested on 4.5 and 5.2.
  - metahuman-to-glb: usable, tested on UE 5.7.
- **Caveats:**
  - Character DNA installs through Poly Hammer's portal, which needs an account, and the compiled bindings aren't in git. That adds friction for headless runs.
  - Blender 5.0 and background mode are not in its tested matrix. Inferred OK, because Python 3.11 bindings exist.
  - That `body.dna` holds the full torso is inferred.
  - Whether metahuman-to-glb's build parameters work on 5.8 is unverified.

### 4. Armhole, sleeve-cap and collar geometry: [maria-korosteleva/GarmentCode](https://github.com/maria-korosteleva/GarmentCode) + [FreeSewing (Codeberg)](https://codeberg.org/freesewing/freesewing) (relevance 7 / 5)

- **What it is:** parametric sewing-pattern code.
  - GarmentCode `sleeves.py` `ArmholeCurve`: a cubic Bezier armhole whose sleeve-cap curve is solved to equal length with matched tangents, rotated by the sleeve's rest angle against the shoulder slope, with an optional `standing_shoulder`. `collars.py` covers V, square, curvy and circle necklines, a lapel and a turtle neck.
  - FreeSewing: `hugo` (raglan), `brian`/`breanna` (sleeve cap), `simon` (collar, collar stand, yoke), `penelope` (pencil skirt).
- **Solves:** P1 (main), P4, P5.
- **How we'd use it:** port the maths; don't import the packages.
  1. In the Blender generator, build the torso's armhole loop and the sleeve's first ring from one shared seam polyline. The cap length equals the armhole length, and the tangents match at the underarm and the shoulder point.
  2. Drive the shoulder slope and sleeve angle per character.

  The sleeve is then joined to the torso along a real armhole curve instead of plugged in as a tube, which removes the shoulder step. Port `hugo`'s lines for a raglan variant.

  For P4, build the blouse collar and the cardigan neckline from offset copies of one neckline curve, with `simon`'s collar stand as the reference.
- **Licence:** both MIT. GarmentCode's draping simulator fork is non-commercial; avoid it.
- **Maturity:**
  - GarmentCode: usable, lightly maintained (v2.0.2), pinned to Python 3.9 and numpy<2.
  - FreeSewing: production, JavaScript, active on Codeberg (the GitHub copy is archived).
- **Caveats:**
  - Both produce 2D patterns. Turning them into a low-poly skinnable mesh is our job.
  - GarmentCode has no raglan sleeve and no shirt collar stand.
  - I verified only FreeSewing's design manifests and file lists, not its drafting maths.
  - Both use a different measurement model from MetaHuman.

### 5. Weight inpainting in Blender, only if skinning stays Blender-side: [rin-23/RobustSkinWeightsTransferCode](https://github.com/rin-23/RobustSkinWeightsTransferCode) (MIT), [sentfromspacevr/robust-weight-transfer](https://github.com/sentfromspacevr/robust-weight-transfer) (GPL-3.0), [yamahigashi/MayaTransferInpaintWeights](https://github.com/yamahigashi/MayaTransferInpaintWeights) (MIT) (relevance 7 / 8 / 4)

- **What it is:** three implementations of the same Epic paper.
  - rin-23: the official reference, about 200 lines of Python plus libigl.
  - robust-weight-transfer: a complete Blender add-on with distance and normal thresholds, an inpaint mask, smoothing and a 4-bone limit.
  - yamahigashi: a Maya tool whose maths uses only numpy and scipy.
- **Solves:** P3, P4, P5.
- **How we'd use it:** replace the nearest-surface weight copy in the headless generator. The cleanest route is to take rin-23's logic and do the Laplacian solve with `scipy.sparse`, following yamahigashi's functions. That avoids both libigl and GPL. We add our own 4-influence prune and renormalise. The unmatched vertices double as an armpit and collar diagnostic.
- **Caveats:**
  - robust-weight-transfer depends on libigl 2.5.1, which has no Python 3.13 wheel, so it is broken upstream on Blender 5.1/5.2. Blender 5.0 (Python 3.11) should work (inferred).
  - Its `limit_mask` does not renormalise, and it pip-installs dependencies at runtime.
  - Loose parts such as separate buttons or collar pieces get no matches; weld them or handle them separately.
  - Redundant if we adopt pick 1. Choose one side, not both.

### 6. Cloth simulation to skin weights: [electronicarts/dem-bones](https://github.com/electronicarts/dem-bones) + [loonghao/py-dem-bones](https://github.com/loonghao/py-dem-bones) (relevance 6)

- **What it is:** an SSDR solver. It computes linear-blend skin weights, and optionally helper-bone animation, that reproduce an example mesh animation.
- **Solves:** P3, P8, P6.
- **How we'd use it:**
  1. Simulate the cardigan and skirt offline with Blender cloth, over the story animation or an arm range-of-motion clip.
  2. Solve 4-influence weights against a locked `metahuman_base_skel`. Either use the CLI with `--nnz=4 --nTransIters=0`, or set `demLock=true` on the joints from our FBX SDK canonicalizer. Alternatively, call py-dem-bones' native class with `lockM` inside Blender 5.0; a cp311 wheel exists.

  The shoulder and hem behaviour from the simulation then plays back as plain linear-blend skinning on the PICO.
- **Licence:** BSD-3-Clause. The precompiled binaries carry third-party licences, including the FBX SDK.
- **Maturity:** dem-bones is production but dormant (v1.2.1, 2021). py-dem-bones is usable (v0.13.1, 2026-10-05, 14 stars).
- **Caveats:**
  - New helper bones next to locked bones are not turnkey: issue #21 reports bones stuck at the origin.
  - Quality drops on meshes with several shells (issue #32).
  - py-dem-bones has no cp313 wheel, its simple API clears the bone locks (use the low-level class), and its Unreal adapter is a stub.

### 7. [pafuhana1213/KawaiiPhysics](https://github.com/pafuhana1213/KawaiiPhysics) (relevance 6)

- **What it is:** a pseudo-physics AnimGraph node for bone chains, with capsule, plane and physics-asset collision.
- **Solves:** P8 (the mobile-viable substitute for cloth), P6, P5.
- **How we'd use it:**
  - Give Maria's skirt and the cardigan front and hem a few chain bones in the generator.
  - Drive each garment with a small AnimBP: Copy Pose or Leader Pose, plus a KawaiiPhysics node with thigh and pelvis capsules and a BoneConstraint to keep the skirt off the legs.
  - Use the KawaiiPhysicsSequencer track to damp the physics across cuts in the Level Sequence.
  - Share one settings DataAsset across all three characters.
- **Licence:** MIT.
- **Maturity:** production (3.4k stars). v1.21.0 ships zips for UE 5.3–5.8.
- **Caveats:**
  - Use v1.21.0 or later; earlier releases restricted the runtime module, which broke Android builds. A user confirmed Android works after the fix.
  - The README warns that Blueprint-only projects can fail to package. Ours is already treated as code-based by UAT because of OpenXR, so it should compile for Android (inferred; confirm with one packaging run).
  - It adds an AnimBP and anim-thread cost per character, and no mobile benchmarks are published.

### 8. Automation and coverage testing: [GenOrca/unreal-mcp](https://github.com/GenOrca/unreal-mcp) (already installed) + [Epic PythonAutomationTest](https://dev.epicgames.com/documentation/unreal-engine/write-editor-tests-with-python-in-unreal-engine) (relevance 7 / 6)

- **What it is:** our existing MCP (Apache-2.0, extended by adding `ue_<name>()` Python functions, no C++), and Epic's Python test framework with `AutomationLibrary` screenshots and reference-image comparison.
- **Solves:** P7, and validation for P2.
- **How we'd use it:** add three things.
  1. `ue_import_garment()`. The current `import_fbx` has no skeleton parameter, so skeletal imports create a new skeleton. Set `FbxImportUI.skeleton = metahuman_base_skel`, then run pick 1's weight steps and assign the material instances.
  2. `ue_skin_coverage_test()`. Copy the existing vision capture code, swap the skin to an unlit highlight or custom-stencil material, capture from fixed CineCameras at key Level Sequence frames, and count skin pixels.
  3. A `test_coverage_<char>.py` per character in `Content/Python`, so the Test Automation window runs the coverage test after every garment regeneration.
- **Maturity:** unreal-mcp is usable (v2.2.0 has precompiled 5.6/5.7/5.8 zips). PythonAutomationTest is production; the plugin is in the local 5.7 and 5.8 installs.
- **Caveats:**
  - The local 2.2.0 copy is pinned to 5.7. Use the 5.8 zip or `main` for the 5.8 project.
  - Four 5.8 crash issues are open with no maintainer reply. One of them, #68, is a batch asset import crash, so import one garment per call.
  - Use the unlit pass, because image comparison breaks under lighting changes.
  - Epic's page doesn't document headless or CI runs (inferred to work via `-ExecCmds "Automation RunTests"`).

---

## 2. Other relevant repos, by problem

| P | Repo | Licence | Rel. | Note |
|---|---|---|---|---|
| P1 | [openfashion-labs/ac9_cloth_retopo](https://github.com/openfashion-labs/ac9_cloth_retopo) | GPL-3.0+ | 5 | Retopologises garments in their flat pattern layout, with 1:1 vertex matching across seams. Blender 5.0+. Interactive, and expects a CLO/MD-style guide mesh. |
| P1 | [cgg-bern/quadwild-bimdf](https://github.com/cgg-bern/quadwild-bimdf) | GPL-3.0 | 3 | Quad-remesh CLI for a dense draped garment. Feature-line control in this fork is unverified; binaries are from 2023. |
| P1 | [goatchurchprime/blender-seams-to-sewing-pattern](https://github.com/goatchurchprime/blender-seams-to-sewing-pattern) | GPL-2.0 | 2 | Seam-marked mesh to flat panels to cloth sim. One-person experimental fork. |
| P1 | [whyoh/blender_clothing_tools](https://github.com/whyoh/blender_clothing_tools) | GPL-3.0 | 2 | Adds sewing edges between seams with equal vertex counts. From 2019; easy to rewrite in bpy. |
| P2 | [Upliner/CharMorph](https://github.com/Upliner/CharMorph) | GPL-3.0 | 6 | `calculate_mask`: a 26-direction ray test plus a near-distance check finds covered body vertices. Port it to author hidden face maps and per-outfit body meshes. Static per pose; the distance threshold assumes metres. |
| P2 | [makehumancommunity/mpfb2](https://github.com/makehumancommunity/mpfb2) | GPLv3 (assets CC0) | 4 | Delete-group plus Mask-modifier convention with a conservative boundary rule. Works only on MakeHuman topology. |
| P2 | [anticto/Mutable-Documentation](https://github.com/anticto/Mutable-Documentation/wiki) | none | 3 | Explains Mutable's Remove Mesh Blocks and Clip With UV Mask. The MetaHuman page dates from the Bridge era. |
| P2 | [ITemre/MutableGraphToolset](https://github.com/ITemre/MutableGraphToolset) | none (Fab) | 3 | Docs for a closed-source UE 5.8 Mutable MCP plugin. Only relevant if we adopt Mutable. |
| P3 | [EpicGames/OpenRigLogic](https://github.com/EpicGames/OpenRigLogic) | MIT | 5 | Official DNA and RigLogic library, including RBF and twist-swing. Use it through Character DNA's compiled bindings; we have no C++ toolchain. |
| P3 | Chaos Cloth `TransferSkinWeights` node (engine) | UE EULA | 3 | Source of good defaults (radius 0.05, normal 30, smoothing 0.1). Its MaxNumInfluences defaults to 8; set it to 4. |
| P3 | [Hunanbean/...Random-Pose-Generator](https://github.com/Hunanbean/Blender-to-UE-ML-Deformer-Plugin-Random-Pose-Generator) | GPL-3.0 | 3 | Idea only: fixed-seed random range-of-motion poses for garment stress tests and Dem Bones examples. We can write the ~30 lines ourselves. |
| P3 | [jin2687/rswt_maya](https://github.com/jin2687/rswt_maya) | 0BSD | 2 | C++ inpainting core with a ctypes wrapper. Its "skeleton gate" idea guards against head influence in collars. Tested on macOS only. |
| P3 | [TrevorHumble/corrective-shape-key-driver](https://github.com/TrevorHumble/corrective-shape-key-driver) | GPL-3.0 | 2 | Bone-driven corrective shape keys on garments, baked per frame. Morph targets cost on mobile, and auto-mirroring may not recognise MetaHuman's `_l`/`_r` names. |
| P3 | [meshonline/Surface-Heat-Diffuse-Skinning](https://github.com/meshonline/Surface-Heat-Diffuse-Skinning) | MIT | 2 | Voxel heat weights for accessories with no body surface to copy from, such as shoes. The binary is hosted off GitHub. |
| P3 | [Sporenoe3D/Mesh2Rig](https://github.com/Sporenoe3D/Mesh2Rig) | GPL-3.0+ | 2 | Turns a cloth sim into bone animation with heat weights. Weaker than Dem Bones and has no influence cap. |
| P3 | [TomohikoMukai/ssmik](https://github.com/TomohikoMukai/ssmik) | MIT | 2 | Removes skin penetration by IK on the skeleton. Maya only; an idea for garment helper joints. |
| P4 | [mio3io/mio3_copy_weight](https://github.com/mio3io/mio3_copy_weight) | GPL-3.0 | 2 | Copies weights between objects. The idea: identical weights on the blouse collar edge, cardigan neckline and face-skirt edge (about 10 lines of bpy). |
| P5 | [yamahigashi/MayaMeshRetarget](https://github.com/yamahigashi/MayaMeshRetarget) | MIT | 4 | RBF garment refit from one body to another, keeping buttons rigid. Maya only; reimplement in numpy if garments become hand-tuned. |
| P5 | [kevinpbuckley/VibeMetaHumans](https://github.com/kevinpbuckley/VibeMetaHumans) | MIT | 4 | Readable source for wardrobe and outfit parameters, reimport that keeps material slots, and leader-pose attachment. C++; the author calls it an untested first cut. |
| P5 | [Huangzizhou/cloth-fit](https://github.com/Huangzizhou/cloth-fit) | MIT | 3 | Intersection-free garment retargeting (SIGGRAPH 2025). C++ for Linux/macOS. Regenerating parametrically is cheaper for us. |
| P6 | [MetaHuman platform & LOD specs](https://dev.epicgames.com/documentation/metahuman/platform-support-and-lod-specifications-for-metahumans) (Epic docs) | docs | 7 | The budget sheet. Android: best LOD3 (head 2.5k verts, body 1.5k), hair cards only, 2048 textures, body correctives only at LOD0–1. |
| P6 | [oculus-samples/Unreal-Showdown](https://github.com/oculus-samples/Unreal-Showdown) | Showdown / UE EULA | 3 | Copy the PSO-cache recording workflow for the Level Sequence. The project itself runs only on Quest with the Oculus engine fork. |
| P6 | [qsfghjyutr/MetaHuman-DNA-Optimizer](https://github.com/qsfghjyutr/MetaHuman-DNA-Optimizer) | MIT | 2 | Prunes head DNA controls by cost. Needs Maya plus MetaHuman for Maya. |
| P6 | [HolotypePteLtd/metahuman_arkit_export](https://github.com/HolotypePteLtd/metahuman_arkit_export) | MIT | 2 | A 52-morph ARKit face as a fallback if RigLogic is too costly. Means leaving the MetaHuman face rig; 0 stars. |
| P6 | [effectustasi/unreal-groom-alembic-exporter](https://github.com/effectustasi/unreal-groom-alembic-exporter) | MIT | 2 | Exports grooms to Alembic for authoring custom hair cards. Needs a C++ compile. |
| P6 | [Ducklexander/metahuman-to-vrchat](https://github.com/Ducklexander/metahuman-to-vrchat) | MIT | 2 | Evidence that a LOD0 MetaHuman is about 110k triangles. Also a working headless Character DNA script (Blender 5.1). |
| P7 | [tumourlove/monolith](https://github.com/tumourlove/monolith) | MIT | 4 | MCP with precompiled 5.7/5.8 builds: posed skeletal-mesh preview capture, running automation tests, `get_vertex_data`. Its HTTP server listens on all network interfaces, so firewall it. |
| P7 | [ChiR24/Unreal_mcp](https://github.com/ChiR24/Unreal_mcp) | MIT | 4 | Ideas for importing onto an existing skeleton and for MetaHuman build actions. Source only, no binaries. Its `copy_weights` is nearest-vertex, so don't use it for garments. |
| P7 | [runreal/unreal-mcp](https://github.com/runreal/unreal-mcp) | MIT | 3 | Zero-compile fallback over Python Remote Execution if MCPython breaks on 5.8. Dormant. |
| P7 | [kevinpbuckley/VibeUE](https://github.com/kevinpbuckley/VibeUE) | MIT | 3 | Extends UE 5.8's experimental native MCP; its PIE-scenario-with-capture pattern fits the coverage test. Needs a compile or the Fab build. |
| P7 | [poly-hammer/BlenderTools](https://github.com/poly-hammer/BlenderTools) (Send to Unreal) | MIT | 3 | Compare its import options (skeleton reuse, LODs, material slots, reimport) with our canonicalizer and importer. |
| P7 | [jcksnvllxr80/ue-metahuman-mannequin-retargeter](https://github.com/jcksnvllxr80/ue-metahuman-mannequin-retargeter) | MIT | 2 | Scripted IK Rig and Retargeter creation for `metahuman_base_skel`. Tested on 5.7. |
| P7 | [Codeturion/unreal-api-mcp](https://github.com/Codeturion/unreal-api-mcp) | MIT (since 2026-07-19) | 2 | Per-version C++ API lookup, handy for 5.7 to 5.8 renames. Earlier versions were non-commercial, so pin a recent one. |
| P8 | Chaos Cloth Panel Editor / Cloth Asset / Outfit Asset (engine) | UE EULA | 3 | Android modules ship, but mobile cost is unmeasured, and each garment adds a component and a draw call. Worth one PICO test at most. |
| P8 | [cestnimaa/metahuman-md-exporter](https://github.com/cestnimaa/metahuman-md-exporter) | MIT | 3 | Exports the sequence as an Alembic avatar for Marvelous Designer. Needs C++ and is GUI-only; the same result is possible with `SequencerTools.export_level_sequence_fbx` plus a Blender replay. |
| P8 | [Dolorousrtur/ContourCraft](https://github.com/Dolorousrtur/ContourCraft) (+HOOD) | MIT code; SMPL non-commercial | 2 | Neural multi-layer cloth, offline only. Heavy CUDA setup and trained on SMPL bodies. |

---

## 3. Not worth it

- **chongdashu/unreal-mcp** (2.1k stars): stale since 2025-04, targets UE 5.5, needs a C++ build, has no LICENSE file, and has no material, skeletal-mesh or Sequencer tools.
- **VAST-AI-Research/UniRig**: ML auto-rigging onto its own skeletons. We need deterministic weights on `metahuman_base_skel` with 4 influences.
- **EpicGames/MayaMLDeformer**: needs Maya and high-resolution simulation ground truth, and adds morph targets and CPU inference per character on mobile.
- **EpicGames/MetaHuman-DNA-Calibration**: not updated for UE 5.6+ characters, restrictive licence, Python 3.7/3.9 only. OpenRigLogic replaces it.
- **maria-korosteleva/NvidiaWarp-GarmentCode**: licensed for "research or evaluation only". Use Blender cloth instead.
- **ChatGarment / design2garmentcode-impl**: heavy ML stacks that write GarmentCode JSON, which we can write directly.
- **HakanErunsal/MetahumanToManny**: rebinds to the Manny skeleton and collapses correctives, the opposite of P3. Borrow snippets at most.
- **Mutable for three fixed outfits** (including toxrus/MutableSidekicksPlugin): Beta, no Python, and its MetaHuman docs are from the Bridge era. Baking per-outfit meshes is simpler.
- **burakcatan/metahuman-body-masks**: UE 4.27, no licence, and opacity-masked skin is the wrong approach on the mobile forward renderer.
- **brainexcerpts/Unreal-DeformerGraph-ExtraNodes**: abandoned UE 5.1 source plugin; compute deformers are unproven within a mobile VR budget.
- **AgileLens/UnofficialMetaHumanVR_Studio**: PC-tethered Quest Pro, UE 5.2, no licence.
- **oculus-samples/Unreal-PerformanceSettings**: needs the Meta XR plugin and C++; it won't run on PICO OpenXR. Use it as a checklist of settings at most.
- **Italink/UnrealClientProtocol**: needs a compile, and everything we need is already reachable from the `unreal` Python module.
- **Ziyuan-Cao/Skeleton-Aware-Skin-Weight-Transfer**: no licence, Maya 2020.
- **Non-rigid ICP repos** (golkir, Tonsty): Blender's Surface Deform and Shrinkwrap already cover this for bodies with shared topology.
- **dairin0d/quadwild-wrapper**: its sponsor dropped it over remeshing quality.

---

## 4. Gaps, and what to do instead

The commercial tools named below are identified only. I did not check any of them in this research, and none is a buying recommendation.

- **P1, procedural low-poly set-in or raglan garments:** nothing open source produces a real-time, skinnable cardigan with a continuous shoulder.
  - **Do instead:** build the shared-armhole-seam construction ourselves (pick 4). Then judge it against posed Character DNA bodies.
  - **Commercial tools:** Marvelous Designer and CLO 3D (pattern, simulation and quad retopology, export to UE), Style3D Studio, SideFX Houdini (Vellum cloth, KineFX), and Faceform (formerly R3DS) Wrap for wrapping a template garment onto a body.
- **P2, skin-under-clothes coverage across poses for MetaHumans:** no tool exists.
  - **Do instead:** run a CharMorph-style ray test per frame in Blender on the Level Sequence exported with `SequencerTools.export_level_sequence_fbx`. Add the in-engine screen-space test from pick 8.
- **P3, MetaHuman-aware garment weighting with correctives and twist joints:** only generic inpainting exists.
  - **Do instead:** inpaint from a full-torso body, then apply our own rules, for example no head or face bones on collars except the neck ring. Before spending effort on corrective weights, check on the device which correctives are driven at the LOD we ship.
- **P4, collar layering:** no tool.
  - **Do instead:** derive the blouse collar and the cardigan neckline from one offset curve, give both layers matching weights at the collar ring, and use `LayeredMeshSupport`.
- **P5, refitting garments across MetaHumans:** no MetaHuman-specific tool. Regenerating per body with our parametric generator is the right approach. MetaHuman bodies of one body type probably share topology (inferred), so vertex-index correspondence works if a refit is ever needed.
- **P6, measured MetaHuman performance on standalone Quest or PICO:** no public benchmarks exist.
  - **Do instead:** profile on the device (stat GPU, Unreal Insights, RenderDoc, Snapdragon Profiler), record a PSO cache, and keep to Epic's LOD3 budget.
  - **Commercial tool:** Simplygon, for LOD and material reduction.
- **P8, real cloth on mobile VR:** I found no evidence that Chaos Cloth is affordable on a standalone headset.
  - **Do instead:** simulate offline and bake with Dem Bones (pick 6), or use KawaiiPhysics (pick 7). If a test is wanted, profile one low-resolution Chaos Cloth skirt on the PICO.