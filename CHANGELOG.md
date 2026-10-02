# Changelog

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
