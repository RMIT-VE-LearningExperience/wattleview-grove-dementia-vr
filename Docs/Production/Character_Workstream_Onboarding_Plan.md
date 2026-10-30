# Character workstream onboarding plan

Updated: 30 October 2026

## Purpose

Onboard Homie to own the Wattleview Grove character work while Lawrence concentrates on the VR
experience, environment, interaction, story and platform builds. Neda's Miro board is the creative
source material for the cast. The Unreal project remains the technical source of truth for what has
actually been built and validated.

The character workstream must produce production MetaHumans that preserve the approved identities,
look natural at conversational VR distance, animate without clothing deformation, and run within the
PICO performance budget. Character experiments must not destabilise the main VR project.

## Roles and decision ownership

| Person | Owns | Does not own |
|---|---|---|
| Neda | Miro context, narrative intent, visual references, character relationships, character-sheet creation and revision, and the rationale behind approved directions | Unreal implementation, rigging, packaging or technical acceptance |
| Homie | MetaHuman identity, age, anatomy, hair, garments, accessories, deformation fixes, character optimisation and character evidence | Room, lighting, VR interaction, story systems or final platform integration |
| Lawrence | Product and creative approval, VR experience, environment, story, interaction, build priorities and final acceptance in the headset | Day-to-day character construction once the brief is agreed |
| Technical support | Reproducible scripts, Unreal import/integration help, build diagnostics, captures and validation tooling | Changing the approved identity or visual direction without review |

When creative and technical needs conflict, Homie documents the trade-off and Lawrence decides. A
technically successful asset is not automatically an approved character.

Neda remains the owner of the visual character sheets throughout production. Homie does not replace
or reinterpret those sheets independently; Homie flags ambiguities and technical constraints, then
Neda revises the sheet or Lawrence approves a documented exception.

## Working locations

- Main UE 5.8 project: `D:\Unreal-Projects\WattleviewGrove-ue58`
- Character validation project: `D:\Unreal-Projects\WattleviewCharacterLab-ue58`
- Character direction: `Docs/Production/Character_Recreation_Reference.md`
- Character Lab rules and gates: `D:\Unreal-Projects\WattleviewCharacterLab-ue58\Docs\README.md`
- Reproducible identity specifications:
  `SourceArt/Characters/References/character_reference_v1.json`
- Approved concept images: `SourceArt/Characters/References/Concepts/`

Homie develops and validates in **WattleviewCharacterLab-ue58**. A character moves into
**WattleviewGrove-ue58** only after the applicable validation gates pass. The main project must not
be used as a garment-fitting sandbox.

## Phase 1 — Neda-to-Homie creative handoff

### Before the meeting

1. Give Homie view access to Neda's Miro board.
2. Export the relevant Miro character frames as a PDF and full-resolution PNGs. Store a dated,
   read-only snapshot outside Unreal's `Content` directory and copy final image references into
   `SourceArt/Characters/References/`.
3. Mark every board item as one of:
   - approved direction;
   - useful reference;
   - historical exploration;
   - rejected direction.
4. Neda prepares an approved character sheet for each character. Each sheet should include front,
   three-quarter, profile and rear views where possible, plus head/face, hair, full-body proportions,
   clothing layers, footwear, colours, materials and key identifying details.
5. Prepare a one-page cast list with age, background, role in the story, required costume, required
   actions and whether the character appears close to the viewer.

### Handoff meeting — 60 to 90 minutes

Neda walks Homie through:

- who each character is and why they are in the experience;
- which references define identity versus only clothing, mood or period;
- Italian identity and family resemblance for Maria and Enzo;
- Maria at about 40 as the master identity;
- how elderly Maria should age forward from young Maria rather than become a different person;
- the carer's lighter complexion and approachable professional appearance;
- the gardener's outdoor role and practical working appearance;
- the 1980s visual cues that apply to the younger versions;
- non-negotiable details and areas where Homie may propose alternatives.

Homie ends the meeting by presenting back the brief in their own words. Any disagreement is resolved
before modelling starts.

### Handoff output

Neda supplies the approved, dated character sheet for each character. Homie then creates a technical
implementation brief linked to that sheet, containing:

- approved front and three-quarter identity references;
- age, heritage, body type and posture;
- hair silhouette, colour and grooming;
- costume layers, materials, colours and footwear;
- required animations and difficult poses;
- intended closest viewing distance;
- mobile/PICO constraints;
- open questions and approval owner.

Neda's character sheets define the intended appearance. Homie's implementation briefs define how
that appearance will be produced and tested in Unreal. Together, rather than live Miro comments,
they become the daily production checklist. The dated Miro export remains the traceable source
reference.

## Phase 2 — Technical onboarding

Homie receives a project walkthrough covering:

1. UE 5.8 MetaHuman sources and generated assemblies.
2. The Character Lab validation map and side-by-side PICO package
   `com.rmit.wattleviewcharacterlab`.
3. The current approved neutral inspection lighting and grey background.
4. The difference between a MetaHuman source, generated Blueprint, body mesh, garment mesh,
   materials and animation assets.
5. Why the full body must remain available during fitting and coverage inspection.
6. Previous failures: hollow shoulders, body-coloured repair wedges, open armholes, split or hanging
   skirt backs, rigid shells, stretched hems and thighs, body breakthrough, glossy materials and
   misleading static-only validation.
7. The rule that desktop appearance is evidence, not final approval; the physical PICO build is the
   final visual and deformation check.
8. Source control and file naming. Homie works on a dedicated branch and does not overwrite an
   approved source asset without preserving a recoverable version.

Homie's first technical task is deliberately small: duplicate one approved MetaHuman in the
Character Lab, make a reversible material or groom adjustment, package it, and confirm the change on
PICO. This proves the complete workflow before substantial character work begins.

## Phase 3 — Production order

### 1. Maria at about 40 — master identity

Lock face, complexion, age, body proportions and the approved 1980s dark hairstyle first. This is the
identity anchor for elderly Maria. Do not use elderly Maria as the likeness target for this version.

### 2. Elderly Maria — age-forward pass

Derive her recognisably from the approved age-40 Maria. Preserve the eyes, nose, mouth, cheekbone and
jaw relationships while adding believable ageing, silver hair, posture and age-appropriate body
changes. Build her practical outfit only after the underlying body and shoulder anatomy are approved.

Current costume direction is a plain cream blouse, dusty-rose cardigan, dark straight trousers and
subtle comfortable footwear. Avoid strong stripes, dense patterns and shiny synthetic materials.

### 3. Enzo at about 40

Match the age and Italian/Mediterranean family context of the photograph. Maintain a healthy average
build, dark swept-back hair and a clean-shaven face. Validate him independently; shared heritage does
not mean copying Maria's facial features.

### 4. David, the carer

Use the approved younger care-worker direction with a lighter complexion, neat hair and friendly,
professional presentation. Add glasses, badge and final uniform only after body and clothing motion
pass.

### 5. Gardener

Older, stockier and practical, with receding grey hair and a full grey beard. His hat, apron, gloves
and outdoor clothing must be designed for the exterior role and tested for silhouette and mobile
cost.

Finish one character as a complete vertical slice before expanding the same garment method to the
whole cast.

## Phase 4 — Per-character workflow

Each character moves through the following states. Record the state in the character brief.

1. **Identity draft** — neutral head and full-body inspection; no final clothing.
2. **Identity approval** — face, age, heritage, proportions, posture and hair approved.
3. **Garment prototype** — clean separate layers fitted to the full body.
4. **Static construction review** — front, rear, profile, both three-quarter views and close-ups.
5. **Deformation review** — idle, walk, reach, sit and transition frames; inspect shoulders, neck,
   elbows, waist, crotch, hips, thighs, knees and hems.
6. **Coverage debug review** — contrasting body and garment materials expose clipping, holes and
   accidental skin visibility.
7. **Material review** — neutral light, protected highlights, matte believable skin and cloth,
   stable hair and no distracting aliasing.
8. **PICO candidate** — packaged exact asset tested at normal and close conversational distances.
9. **Performance review** — record frame time and identify the cost of hair, materials, cloth and
   character count.
10. **Production handoff** — freeze source version, export evidence and migrate only the accepted
    assets and settings into Wattleview Grove.

MetaTailor may be evaluated first for fitting and auto-skin weighting. Its free tier is sufficient
for a controlled proof of concept, but licensing must be confirmed before production use. If it
cannot pass the deformation test, test Marvelous Designer or a clean manual weight-transfer workflow
instead of repeatedly patching a failed mesh. AI-generated garments may provide a starting shape,
but they are not accepted until topology, layering, weights and Pico deformation pass.

## Required review evidence

For every candidate, Homie supplies:

- front, rear, left, right and both three-quarter stills;
- face, hair, neck/shoulder, hand and footwear close-ups;
- full-body images at representative animation times;
- short desktop animation capture;
- contrasting body-coverage debug captures;
- exact Unreal asset paths and source-file paths;
- known limitations;
- Character Lab build identifier and source revision;
- Pico screenshots or video from the exact candidate build;
- pass/fail result against the checklist below.

Screenshots are taken with the shared grey background and neutral inspection light. Bright glamour
lighting, clipped highlights or a single favourable angle cannot be used for approval.

## Acceptance checklist

A character passes only when all applicable items are true:

- recognisable approved identity, age, heritage and role;
- plausible anatomy and posture without clothing hiding defects;
- hair silhouette and colour match the character brief;
- shoulders and armholes are continuous and naturally constructed;
- neckline and garment layering are intentional from all angles;
- no gaps, floating pieces, split backs, rigid shells or stretched lower garments;
- no body breakthrough during idle, walk, reach or sit;
- garment materials read as cloth and skin is not excessively shiny;
- animation remains smooth and anatomically plausible;
- the exact asset passes physical PICO review;
- performance remains within the agreed scene budget;
- source, licence and build provenance are recorded.

Any unexplained visual defect is a fail. "Fixed" means it passed the required Pico gate, not merely
that the asset imported or looked correct in one editor frame.

## Integration contract with the VR workstream

To keep Lawrence's VR work unblocked:

- the main experience continues to use the last known stable character set until a replacement is
  accepted;
- Homie never asks the VR branch to absorb an unfinished garment experiment;
- character migrations are scheduled, versioned packages rather than ad-hoc asset copies;
- each migration includes an asset list, setup instructions, dependencies, material settings,
  animation assumptions and rollback point;
- Lawrence checks story blocking, gaze, interaction, lighting and performance after migration;
- character-specific defects return to Homie's Character Lab branch instead of being patched in the
  room map;
- environment or story changes that affect a character are communicated through a short interface
  request: required action, duration, contact points, nearest viewer distance and performance limit.

## Suggested first two weeks

### Week 1 — alignment and one proven pipeline

- Miro access, export and Neda handoff.
- Unreal/MetaHuman/Character Lab walkthrough.
- Neda delivers the five dated character sheets and Homie writes the linked technical implementation
  briefs.
- Review and lock Maria age 40's identity and hair target.
- Run one MetaTailor or equivalent garment-fitting spike on a duplicate test asset.
- Package and inspect the result on PICO.
- Decide the garment pipeline from evidence, not from an editor preview.

### Week 2 — Maria vertical slice

- Finalise Maria age 40 identity evidence.
- Produce the elderly age-forward identity draft.
- Approve elderly Maria's body, shoulders, neck and hair before final clothing.
- Build the simple blouse/cardigan/trouser outfit.
- Complete static, animated, coverage-debug and Pico reviews.
- Document the repeatable process for Enzo, David and the gardener.

At the end of week 2, the desired outcome is not five partially completed people. It is one accepted
character pipeline and one complete Maria vertical slice that can be repeated safely.

## Communication rhythm

- **Start of week:** Homie posts the character, target gate and intended evidence.
- **Mid-week:** 20-minute visual review with only unresolved creative decisions.
- **End of week:** pass/fail review using the evidence pack; no live-editor improvisation as the sole
  proof.
- **Decision log:** Neda records visual-direction changes in the character sheet; Homie records
  implementation changes in the technical brief. Both include the date and decision owner.
- **Blockers:** flag missing reference, licensing, topology/rigging failure or Pico regression as soon
  as discovered. Do not hide a known failure behind clothing, camera angle or lighting.

## Immediate setup checklist

- [ ] Homie has Miro access.
- [ ] Neda's relevant frames are labelled and exported.
- [ ] Neda's five dated character sheets are delivered and approved as the visual source of truth.
- [ ] Homie has access to both Unreal projects and the required UE 5.8 installation.
- [ ] Homie can open the Character Lab and locate the current MetaHuman assets.
- [ ] A dedicated character branch and shared handoff folder exist.
- [ ] The PICO test/install process is demonstrated.
- [ ] Homie's five technical implementation briefs are linked to Neda's sheets and reviewed by
      Lawrence.
- [ ] Maria age 40 is confirmed as the first identity task.
- [ ] The first garment-tool spike and its pass/fail criteria are scheduled.
