# Changelog

## 0.13.0
- Cast library (Story tab, Cast; or Attribute Editor, From cast…): generate textured, auto-rigged characters from a name, culture, age, gender and a description. MayaToon writes the Meshy prompt (T-pose, separated limbs, animated-film style, culture-aware outfits), runs preview, texturing (PBR) and rigging, then downloads the rigged GLB and a thumbnail
- Generated characters work with every action, IK pose, foot locking, physics, the Story director, auto-cut cameras and renders
- Generate the cast for this story: one click starts a job per character in the current scene; each replaces its built-in look when ready
- Story director option: use Cast models for characters with matching names
- Jobs run in the background on the studio server; Meshy task ids are saved after every step, so a restart resumes instead of paying again, and Retry continues a failed job from its last finished step; downloads retry automatically
- Meshy key, face budget and a Test Meshy button (shows remaining credits) in AI and voice settings; MESHY_API_KEY is picked up by the installer
- Wider skeleton-name matching (Mixamo, Unreal, Blender and generic rigs)

## 0.12.0
- IK pose tool (I, or the new tool button): drag a character's hands, feet or purple look target in the viewport; a two-bone IK solver bends the limb to reach and keys an additive pose layer on top of its actions. Poses blend smoothly between keys; a weight slider and Clear key / Clear all live in the Attribute Editor. Works with VRM and Mixamo models too
- Foot locking with leg IK (Display menu, on by default): feet that touch the ground stay planted while the body moves; grounded foot drift on a test walk fell from about 61 cm to under 1 cm
- Walk stride now matches the leg swing geometry, so walking looks planted even without locking
- Curve editor tangents per key: Auto (smooth, never overshoots a key), Linear, Flat (ease in and out) and Step, with tangent handles drawn on the selected key; interpolation is Hermite throughout
- Follow-through now includes the pose layer, so IK placements land exactly

## 0.11.0
- Hair and cloth physics (Display, Hair and cloth physics, on by default): spring chains with head and body colliders for braids (4 segments), ponytails, long hair, animal tails and the sari pallu; braids drape over the back of the head instead of passing through it
- Dupatta for kurta outfits on women and girls (or any character with dupatta set): two physics tails behind the shoulders and a drape across the front
- VRM characters load through three-vrm: their authored spring bones (hair, skirts, accessories, with colliders), expression manager, node constraints and VRoid's MToon toon shading
- Physics steps forward continuously during playback and renders (motion blur samples included), and settles to a natural drape instantly when you jump or scrub
- The old procedural hair and tail sway is replaced by the simulation

## 0.10.0
- Engine upgraded from three.js r128 (2021) to r186 (current), loaded as ES modules through an import map; three-vrm 3.5 is vendored for upcoming spring physics and toon shading
- New ambient occlusion (GTAO, denoised) replaces SSAO; post chain is Render, GTAO, depth of field, bloom, Output (tone map and sRGB), grade, FXAA, the same for viewport, film view and MP4
- Neutral tone mapping (Khronos PBR Neutral) instead of ACES: colours stay as authored, skies stay blue, better for cartoons; exposure and grade rebalanced
- Lights rescaled for physically based light units; shadows use PCF with a soft radius
- The font stylesheet no longer blocks start-up on a slow network
- Fixed: post-processing copy no longer writes into three.js's shared CopyShader uniforms
- Removed the old r128 vendor files

## 0.9.0
- Characters can wear a real 3D model: Attribute Editor, Character, "Use a model…" takes a VRM (VRoid Studio, VRM 0.x or 1.0) or any Mixamo-rigged GLB. MayaToon drives its skeleton, so every action, walk, run, gesture, look-at, Story director scene and render works with it
- Retargeting in character space: spine, neck and head copy rotation; arms and legs match direction, so T-pose and A-pose models map onto MayaToon motion
- Faces: VRM expressions (blink, happy, sad, angry, surprised and the aa/ih/ou/ee/oh mouth shapes) follow lip-sync and emotion; ARKit-style or VRoid morph names work on plain GLBs; VRM eye bones follow eye darts and eye contact
- VRM 1.0 node constraints (aim, roll, rotation) are solved, so twist and helper bones follow the arms and legs
- Unlit VRM materials are converted to lit ones (keeping skinning and morph targets) so models sit in the scene's light, shadows and ambient occlusion
- Models are sized from their skeleton and stand on the ground automatically; "Built-in" switches back

## 0.8.0
- Hands with four fingers and a thumb that curl per gesture: relaxed at rest, fists when angry, an extended index finger for Point, flat palms for Namaste and Clap, open for Wave and Cheer, loose while talking, tighter while running
- New walk and run cycle: heel strike and toe-off, knee absorb on contact, hip twist and drop, chest counter-twist, arm swing with elbow follow-through, steadied head, hair and tail swing
- Lip-sync reads vowel shape: rounded lips on "oo/oh" sounds, wider mouth on bright sounds, brows lift and the head dips on stressed syllables
- Saris, kurtas, daura, dhotis and skirts are skinned to the legs: hems lift and swing with each step instead of the knees poking through; the sari border follows the hem

## 0.7.0
- Characters rebuilt on skinned bodies: torso, arms, legs and neck are one continuous skin with weighted joints, so shoulders, elbows, hips and knees bend smoothly instead of showing ball joints; fur follows the skinned limbs
- Hands with a thumb (paws for animals), shoes with soles and toe caps, trouser cuffs, sleeve cuffs, collars, belts, shirt buttons, a kurta placket with gold buttons
- Eyes: textured irises with fibres and limbal ring, round or slit pupils, glossy sclera, two catch-lights, real upper and lower eyelids that blink, widen when surprised, droop when sad, narrow when angry and lift into a smile; lashes for women and girls
- Arched brows, a shaped nose with nostrils, a mouth with teeth and tongue that open with the voice
- Hair sculpted with strands, a side-swept fringe, glossy clearcoat; ponytail band, braid with ribbon, bun with pin, fuller bob; hair fluff is now optional (Hair fluff slider)
- Skin and fabric use physically based materials (soft sheen on skin and cloth)
- Namaste lands with palms together at the chest; sari drape and bindi placement fixed

## 0.6.0
- New studio skin: floating rounded panels on a graphite canvas, marigold accent, Manrope type, focus rings, blurred menus and dialogs; dark by default (Display, Switch light / dark)
- Production viewport (Display menu, on by default): screen-space ambient occlusion, subtle bloom, colour grade with vignette and fine grain, FXAA; Film view adds depth of field focused on the character in shot
- MP4 renders run the same pipeline at full resolution (Render, Look: Production or Plain; Depth of field on or off), combined with supersampling and motion blur
- Lighting: sun disc and glow in the sky, horizon haze, aerial perspective on distant scenery, rim light, sun colour that warms toward golden hour and cools at night, 4K soft shadows, textured ground

## 0.5.0 (MayaToon)
- Renamed Mini Maya Studio to MayaToon; installs to ~/Sites/mayatoon on port 47219 next to the old app, and copies its scenes once
- Story director: prompt, culture and language in, finished movie out (write, build, cast, voice, cut, render). Claude, OpenAI or Ollama, with offline templates in Nepali, Hindi, Telugu, Tamil and English
- Nine culture packs with names in native script, festivals, wardrobe, skin tones, sets and light
- New set pieces: mountains, stupa, prayer flags, temple, gopuram, banyan, coconut palm, kolam, well, bullock cart, market stall, clay pots, oil lamps, cottage
- Wardrobe: sari, kurta, dhoti/veshti, daura suruwal, Dhaka topi, pagdi, cap, braid, bindi
- Gestures: namaste, clap, nod, shake head, bow
- Natural motion: acceleration lean, turn banking, follow-through, breathing, eye darts, eye contact with the speaker, squash and stretch, longer smoother blends; in-between-frame playback
- Auto-cut cameras: establishing wide, medium singles, two-shots, tracking shots, push-ins and drifts, avoiding props and characters
- Narrator track; English line beside every line; subtitles in dialogue language, English or both; title card
- Voices: Azure, ElevenLabs, Google, OpenAI alongside Piper, Mac and espeak; automatic casting by language, gender and age; Voice lab to preview and assign
- Record a line in the browser or upload one, with denoise, trim and loudness; consent-based voice cloning through ElevenLabs
- Render: motion blur, filmic tone mapping, title card
- ctl.sh make / story / cultures for the terminal

## 0.4.0
- Voices: type a Line on a Talk clip and the studio speaks it. Offline Piper neural voices (English, Hindi, Nepali by default, edit voices.txt for more), Mac system voices, and espeak-ng when present
- Lip sync from the actual audio: mouth opening follows loudness, shape widens on hissing sounds, head nods with emphasis
- Per-character voice, pitch (animals default higher or lower) and speed; Speak line, Re-voice and Voice all lines on the Story panel; a voiced line pushes later clips back so nothing is cut off
- MP4 mixes every voiced line with the music track
- Characters: sculpted species heads (snouts, cheeks, chins), fur rendered as layered strands with darker roots, markings painted into the fur (fox muzzle, tiger stripes, panda patches, raccoon mask, tabby, dog eye patch), iris colors and slit pupils, lighter inner ears, black ear tips, bushy and ringed tails, lion mane
- New species: tiger, lion, raccoon. New hair style: curly. Hair has soft fluff
- Fur slider per character (0 gives the old toy look); Display menu sets viewport fur to full, light or hidden, renders always use full fur
- Installer creates a Python venv with piper-tts and downloads voices into data/voices (MINIMAYA_NO_TTS=1 skips)

## 0.3.0
- Characters: little humans and animals (cat, dog, bear, bunny, fox, pig, panda) with rigs, blinking eyes, brows, talking mouths, ears, tails, hair styles, skin-tone presets and clothes
- Acting: 15 actions (Walk to and Run to with a ground pick, Wave, Talk, Jump, Dance, Cheer, Point, Think, Look around, Sit, Sad, Surprised, Angry, Play animation) with blending, expressions, dialogue lines and facing direction
- Story panel (T): per-character clip tracks, camera shots, audio track with waveform; drag, resize, delete
- Cameras: camera from view, lens, aim at a character, shot cuts; Film view (V) with format gate and subtitles
- Sets: ten props, gradient sky, ground, sun and fill light with Day, Golden hour and Night presets, image-based lighting
- Media: import rigged GLB models with animations; audio track synced to playback
- Render: Landscape, Vertical 9:16, Square and 720p presets, supersampling, burned-in subtitles; MP4 movie with sound encoded by ffmpeg on the studio Mac
- Server: asset storage, frame upload and ffmpeg encoding, media with byte ranges; installer adds ffmpeg through Homebrew and gives launchd a Homebrew PATH
- Shelf is now tabbed: Create, Characters, Acting, Set, Camera, Media
- First run of 0.3 opens a demo movie; Undo returns to your previous scene

## 0.2.0
- Studio server (Python, stdlib only) with a scene library: Save to studio (Ctrl S), Save as, Open, Delete
- Graph Editor: per-channel curves, drag keys in value or time, zoom and pan, spline / linear / stepped curves, exact key fields
- Multi-select (Shift-click in viewport and Outliner), moving several objects at once
- Hierarchy: Parent (P), Unparent (Shift P), Group (Ctrl G), drag-and-drop parenting in the Outliner, duplicate and delete whole branches
- Render: clean still at any size (PNG) and playblast of the frame range (WebM or MP4)
- Export: animated GLB (baked per frame) and OBJ; scene JSON download
- Seed scene shows a spinning group with children
- Offline: three.js vendored; install script with launchd agent, backups, git commit and GitHub push

## 0.1.0
- Viewport, shelf, toolbox, Outliner, Attribute Editor, time slider, keys, undo, autosave
