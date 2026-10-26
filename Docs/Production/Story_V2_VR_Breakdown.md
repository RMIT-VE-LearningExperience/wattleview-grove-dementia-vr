# Wattleview Story V2 — VR production breakdown

Source: `Wattleview Story_V2` (received 2026-10-26, second draft; final stories pending after the
22 October 2026 meeting). This document turns the script into the things the Unreal build needs:
viewpoints, characters, set, props, a beat table, the perception effects, and open questions.

**Version note.** The narrative sections of Story V2 (Context, VR Experience 1, VR Experience 2)
still describe a *medication round* with tablets. The Story & Purpose Guide and the CAUSEd section
in the same document replace that with *helping Maria get ready for breakfast* and a *hairbrush*,
following the 22 October decision that a support worker cannot give medication. This breakdown
follows the **hairbrush version**. The narrative prose should be brought in line before voice
recording, because several of David's lines change (see Open questions).

## Viewpoints

Three viewpoints of the same five minutes, all driven by one master Level Sequence:

| # | Viewpoint | Camera | Perception layer |
|---|---|---|---|
| 1 | David, support worker (VR Experience 1) | First person. Moves: door → beside Maria → table → seated → door. | Off |
| 2 | Maria, resident (VR Experience 2) | First person. Standing by her chair, then seated at the table. | On |
| 3 | Corner of the room | Fixed position in a corner, sees the whole room. Watched in VR as a third-person option, and exported as a flat video for students who can't wear a headset, viewed on a tablet. | Off |

Rules that apply to every viewpoint:

- Head rotation always comes from the headset. The sequence never animates camera rotation.
- Camera position changes are cuts with a short fade, not continuous travel. David's walk from the
  door to Maria is the main case; continuous first-person walking is a nausea risk for VR-naive and
  older viewers. Test continuous motion only if the client asks for it.
- No camera shake. Pain and fear are shown with audio and edge effects.
- Target 72 Hz on PICO 4 Ultra at all times. Frame rate is a safety constraint, not polish.
- Seated viewing is the default assumption for students.

## Characters

| Character | Role in the scene | Build need |
|---|---|---|
| **Maria Russo** | 82, resident, Alzheimer's disease, moderate stage (confirmed by Lawrence 2026-10-26). Italian background; slips into Italian when settled. Injured right arm, visible on a second look, never mentioned. Standing by her chair, then seated. | MetaHuman, re-authored: the existing Maria asset does not match the brief (decision 2026-10-26). Injury as a skin decal (see note below). Full-body and facial performance. |

**Injury note.** Lawrence has proposed a cast or a bruise on the right arm. The Story & Purpose
Guide requires the injury to be "only visible on a second look, painful but unspoken, and
reportable", and explicitly rules out "an obvious injury". A cast is visible the moment David walks
in and would remove the "easy to miss" learning beat. A bruise above the wrist, a skin tear under a
sleeve, or swollen fingers all satisfy the guide. This breakdown assumes a **bruise above the right
wrist** until told otherwise.
| **David** | Support worker, early 30s, clipboard with the night handover. Does every action in the scene. | New MetaHuman in support-worker uniform. Full-body performance with usable first-person hands for viewpoint 1. |
| **Enzo** | Maria's husband. In the wall photograph (younger, green backyard) and as the figure David gradually becomes in Maria's view: work shirt, grey hair, then his full face. | New MetaHuman sharing David's body rig and animation so the two can cross-fade in place. Younger Enzo only needs a 2D photo render. |
| **Gardener** | Works the garden beds outside the window. Haloed in light in Maria's view. | Low-detail character with a short work loop, seen through glass at distance. |
| **Antonio** | Named only, in the handover note. | Text only. |

## Set

Wattleview Grove, Maria's room. Morning, early light through the window.

- Door to the corridor. The corridor is never seen; it is an audio source.
- Large window onto garden beds with the gardener at work.
- Table with chairs. Maria's chair has arms she grips. David pulls a second chair in at 4:00.
- Bed, bedside table, curtains, a shelf for the memory box.
- Ceiling fan, turning. It is the last sound to fade in Maria's view, so it must stay in both views.
- TV in the corner playing the morning news. At 0:45 it must be showing a man.

### Props with a story job

Every item below is used by a later beat. If one changes, the beat changes with it.

| Prop | Where | Job |
|---|---|---|
| Framed photograph: Maria and Enzo in a backyard thick with green | On the wall near her chair | Her focus at 0:00. The only sharp, warm-lit thing in Maria's view. |
| Memory box | On the shelf | Life-history tool David never uses. |
| Calendar crowded with bright sticky notes | Wall | Person-centred room dressing. |
| Day-date clock | Wall or bedside | Room dressing, orientation aid. |
| Hairbrush | Table | The care task. Looms "too large, too close" in Maria's view at 1:40. Left on the table at the end. |
| Water jug and glass | Table | David's reflex at 2:30. Glass pushed away. |
| Call bell / buzzer | Near the chair or bed | David's parting line. |
| Clipboard with handover note | In David's hand | Must be legible in viewpoint 1: "Antonio visited last evening. Upset after he left. Up since 05:00, looking for her mother." |
| Garden beds and gardener | Outside the window | Trigger for Enzo at 0:45. |

### Memory overlay set (Maria's view only, 2:30 to 3:15)

A backyard that replaces the room for a moment: tomatoes and basil climbing their stakes, a fig
tree, and a garden hose lying across the table in front of her. Italian kitchen garden, not a
generic lawn.

## Room reference

From "Aged Care Room environment examples" (received 2026-10-26). The PDF should be copied into
`Docs/References/` so it travels with the repo.

- **Page 1, real rooms.** A traditional room: mauve walls with a floral border, wall clock, photo
  collage boards, a wall calendar and planner, floral curtains, a red recliner, bedside cabinet with
  radio and flowers, floral bedspread, carpet. A modern facility room: neutral walls, grey curtains,
  a large window onto a courtyard garden, light-timber built-in wardrobe and shelving, a lounge chair
  by the window, adjustable bed with a quilt, timber bedside drawers with a phone, downlights, fan.
- **Page 2, AI concepts.** Full-height glass onto a garden, a resident in a recliner with a carer
  kneeling beside, mirror, timber wardrobe, light pelmet above the bed, warm neutral palette.
- **Page 3, AI concept, closest to the brief.** An Italian-Australian personalised room: a large
  window with floral curtains onto a flowering garden with a bench; a pink floral recliner by the
  window with a crochet throw; a side table with a framed photo and flowers; pot plants on the sill;
  a timber wardrobe covered in family photos with an Italian flag, a Madonna figurine, a cross and a
  "Famiglia Amore Sempre" sign; a gallery wall of family photos and a coastal painting; an adjustable
  bed with floral linen and a granny-square blanket; an overbed table; a teddy bear; timber bedside
  drawers with lamp, alarm clock, water glass, rosary and saint figurine; a basket with a gardening
  magazine; slippers; a floral rug on carpet.

Direction: take the architecture from the modern facility room (built-ins, big window, adjustable
bed, downlights, fan) and the dressing and warmth from page 3. Palette: warm cream walls, light
timber, pink and floral textiles, green garden light. The script needs a small table with armchairs
in addition to the recliner, since David guides Maria to the table and she grips a chair arm.

## Beat table

Both views run the same clock. Quotes are verbatim from Story V2.

| Time | David's view (VR 1) | Maria's view (VR 2), perception on top of the same action | Audio | Build notes |
|---|---|---|---|---|
| 0:00–0:45 | Enters with the clipboard. Handover note visible at the top of the page; he glances and says nothing. "Maria? Morning — how are you doing today?" She turns, searches his face, doesn't answer. "Let's get you sat down, yeah? Come on." Guides her to the table; she keeps looking back at the photo: "...he'll want to know..." As she sits she winces and cradles her right wrist; a bruise darkens above the joint. David, reaching for the hairbrush, doesn't notice. | The photograph is the only thing in sharp focus, warm-lit. Everything else is soft. Someone has come in: a shape, a voice, no one in particular. "...he'll want to know..." She is guided to the table; as she sits, pain flares through the wrist. | Fan hum. TV news, low. Garden ambience through the window. Footsteps, door. VO: David's greeting, Maria's murmur. | David camera: door → beside Maria → table, as cuts with fades. Maria camera: standing → seated, one cut. Photo rendered sharp on a stereo quad layer over a softened scene. Bruise decal on the right wrist. |
| 0:45–1:40 | From her chair Maria stares at the gardener. The TV shows a man at the same moment. "...that's him... that's him..." David follows the rough direction of her gaze to the TV: "Sorry, is the TV bothering you? Let me turn that down." Turns it down, then off. Her eyes never left the gardener. | The gardener shines, haloed in light. The TV is a grey blur of muffled speech. "Enzo does the garden" is a clear thought; only "...that's him... that's him..." comes out. The man beside her starts to take on Enzo's colours: a work shirt, grey hair. He turns the TV off; it doesn't help and she doesn't notice. | TV audio clear in view 1, low-passed in view 2. VO. | Halo glow on the gardener. Blurred variant of the TV screen material. Enzo stage 1: shirt material cross-fade, hair colour parameter. |
| 1:40–2:30 | David brings the hairbrush towards her. She pulls back in fear, not anger, blocks it with her sore hand and winces. David reads it as resistance. "No — not now, not now, not now..." Then, quieter, eyes drifting to the window: "...he'll want to know..." | The brush looms, too large and too close, reaching for her head. She throws up her hand and pain jolts through her wrist. She hears her own heartbeat and pulls back. | Heartbeat, view 2 only. VO. | Brush scaled up close to the camera in view 2. Pain shown as an edge pulse, never camera shake. Enzo stage 2. |
| 2:30–3:15 | "...time for water... it needs doing before it gets hot..." David pours a drink from the jug ("good idea, it's going to be a warm one") and slides the glass across. She pushes it away: "No — no, not that. Not for me." | The room falls away: the backyard, tomatoes, basil, a fig tree, a hose across the table. The glass is pushed at her and the backyard vanishes. A flicker of frustration: Enzo would understand, and this man doesn't quite. | VO. Backyard ambience under the overlay in view 2. | Memory overlay: dithered cross-fade between the room set and the backyard set, hose prop on the table. |
| 3:15–4:00 | Voices drift in from the corridor, ordinary to David. Maria glances at the door, frightened: "...why is it so loud... he won't hear me..." "It's alright, it's just the hallway." He goes back to brushing her hair. She holds her wrist, rocks slightly: "...he'll want to know... he'll want to know..." Agitation climbs. | The corridor erupts: voices amplified, overlapping, impossible to make out. The light in the room cools and the edges of her vision darken. Fear peaks because she still can't be heard. | Corridor chatter: quiet in view 1, loud and layered in view 2. VO. | Light colour animated directly on the lights in the sequence, not through post-processing. Edge-darkening vignette mesh on the camera. |
| 4:00–4:30 | Something makes him pause. He sets the brush aside, pulls a chair in, sits close. "Hey. Maria. What's going on?" She doesn't answer, but the edge comes off slightly. | He sits close and asks what's wrong. The noise falls away one layer at a time: the corridor first, then the fan. The light warms. | Layered fade-outs in view 2. VO. | David camera: standing → seated cut. Enzo stage 3. |
| 4:30–5:00 | Without a word David takes her hand. Her shoulders drop, her grip loosens, then her face follows. She looks at him properly. "Enzo... l'hai trovato. You found it. Good." "There we go. All settled?" "Come on then." He stands, leaves the brush on the table, her hair unbrushed, tells her to ring the buzzer if she needs him, and goes. The refusal, the wrist and the handover go unreported. | He takes her hand and that completes it. Her body lets go, then her face. His face resolves fully into Enzo. The room is quiet and the warmth at its fullest. He leaves; she stays settled. The brush means nothing to her. | VO. Near silence apart from room tone. | Face swap: David and Enzo MetaHumans cross-fade in place on the same animation. David camera: seated → door → fade out. |

## Perception effects, Maria's view only

Mobile-safe approaches. Everything here must run under forward shading with MSAA and no HDR
post-processing, so none of it relies on depth of field, bloom, or colour grading.

| Effect | Beats | Approach |
|---|---|---|
| Soft room, sharp photograph | 0:00 onwards, easing off as she settles | Lower the projection layer render scale so the whole scene softens, and draw the photograph as a stereo quad layer, which the compositor renders crisp. Warm glow as an additive sprite behind the frame. |
| Haloed gardener | 0:45–1:40 | Additive glow sprite or emissive shell around the gardener, visible through the window. |
| TV as a grey blur | 0:45–1:40 | Swap the screen material for a blurred, desaturated variant; low-pass the TV audio. |
| Enzo over David | 0:45 → 4:30 in three stages | Stage 1 shirt and hair colour. Stage 2 stronger material blend. Stage 3 full MetaHuman cross-fade with dithered opacity, both characters on the same animation. |
| Brush looms | 1:40–2:30 | Scale the brush prop up on its approach in this view only. |
| Pain jolt | 0:00 and 1:40 | Short edge pulse on a camera-attached vignette mesh plus a sharp sound. |
| Heartbeat | 1:40–2:30 | Audio only. |
| Memory overlay | 2:30–3:15 | Cross-fade the room set and the backyard set with dithered opacity; the hose lies across the real table. |
| Corridor overload | 3:15–4:00 | Amplified, layered voices; edge darkening; lights cool. |
| Settling | 4:00–5:00 | Sounds fade in order: corridor, then fan. Lights warm. Softness clears so Enzo's face can resolve. |

## Audio

- Voice: David in English. Maria in English with one Italian line, "Enzo... l'hai trovato." Final
  lines will be generated with ElevenLabs once the script is locked; the Windows TTS placeholders
  stand in until then. No subtitles in VR for now.
- Beds: fan loop, morning-news TV bed with a visible presenter, garden ambience, corridor chatter
  in two mixes, room tone, heartbeat, backyard ambience, hose or water, footsteps, door.
- Two mixes per bed where the views differ. The fan is the last sound to fade in view 2.
- TV content must be rights-clear or produced in-house.

## Asset list, first pass

- Characters: Maria, David, Enzo, gardener. Clothing: support-worker uniform, Maria's day clothes,
  Enzo's work shirt.
- Animation: full-body performances for Maria and David, with David's hands usable from his own
  eyes. Facial animation from the recorded voice lines. Gardener loop.
- Environment: resident room, garden exterior seen through glass, corridor door, backyard memory set.
- Props: as listed, plus the clipboard with a legible handover note.
- Systems: viewpoint selection at launch, master sequence with per-view camera and effect tracks,
  per-view audio submixes, fade-based transitions.

## Decisions so far (2026-10-26)

- Maria Russo is 82, Italian, Alzheimer's disease at moderate stage.
- The existing Maria MetaHuman will be re-authored.
- The corner view is both a VR option and a flat video export for tablet viewing.
- No subtitles in VR for now.
- Voices via ElevenLabs once the script is final.
- Engine: UE 5.8.4, fresh project from the VR template, native PICO support.

## Open questions

1. Confirm the hairbrush version supersedes the medication prose, and supply David's final lines for
   the changed beats, including his parting line.
2. Cast versus bruise for the right arm. See the Injury note; bruise recommended.
3. David's movement between positions: cuts with fades, or continuous walking.
4. Which corner and what height for the corner camera.
5. Both experiences run exactly five minutes; confirm no intro or outro inside the VR itself.
6. David's and Enzo's looks beyond "early 30s, uniform" and "grey hair, work shirt".
