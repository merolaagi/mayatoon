# MayaToon

A small Maya-style 3D animation studio in the browser that turns a one-line idea into a short, voiced cartoon rooted in a culture: Nepal, Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, UK or US English. It runs from your Mac with a tiny Python server (standard library only).

## Make a movie from a prompt

Story tab, **New story** (or File, New story from a prompt). Type an idea, pick a culture and the dialogue language, then **Make movie**. The director:

1. writes the story (Claude, OpenAI or a local Ollama model; offline templates when none is set up), with lines in the language's own script and English alongside,
2. builds the set (stupa, prayer flags, mountains, temple, gopuram, banyan, coconut palms, kolam, well, bullock cart, stall, clay pots, oil lamps, cottage…) and dresses the cast (sari, kurta, dhoti/veshti, daura suruwal, Dhaka topi, pagdi, braid, bindi),
3. casts a voice per character by language, gender and age, and voices every line,
4. places cameras and cuts: establishing wide, medium singles on whoever speaks, two-shots for group moments, tracking shots for walks, with gentle push-ins and drifts; cameras steer around props and other characters,
5. optionally renders the MP4 with a title card, subtitles (dialogue language, English, or both) and motion blur.

Read the script before building, edit it as JSON if you like, and change anything afterwards on the Story panel (T).

From the terminal:

```
~/Sites/mayatoon/ctl.sh make "Two friends fly kites during Dashain" --culture nepal --render
~/Sites/mayatoon/ctl.sh make "A family cooks pongal" --culture india-tamil --format 9:16 --render
~/Sites/mayatoon/ctl.sh story "A fox helps a farmer" --culture india-telugu > story.json
~/Sites/mayatoon/ctl.sh cultures
```

`make` opens the studio and runs the whole pipeline in the browser (rendering needs the page's WebGL). Movies land in `data/renders`.

## Your own characters (VRM and Mixamo)

For a production look, give characters real models: select a character, then Attribute Editor, Character, **Use a model…**.

- **VRoid Studio** (free, Mac): design a character (hair, face, outfits, including saris and kurtas made with its texture editor), then File, Export as VRM. VRM faces bring blinks, smiles, sad, angry and surprised looks and mouth shapes that follow the voice.
- **Mixamo** (free with an Adobe account): upload any humanoid model, auto-rig it, download FBX, then convert to GLB (for example in Blender: File, Import FBX, Export glTF binary).
- Any GLB with a humanoid skeleton named in the usual ways (Hips, Spine, LeftUpLeg, LeftArm…) works.

MayaToon drives the model with its own animation, so all actions, the Story director, auto-cut cameras and renders work unchanged. Respect each model's licence (VRM files carry their terms in their metadata).

## Voices

- **Offline:** Piper neural voices (edit `voices.txt`), Mac system voices, espeak-ng as a last resort.
- **Commercial:** Azure Speech (good Nepali, Hindi, Telugu, Tamil neural voices), ElevenLabs, Google Cloud TTS, OpenAI. Add keys in Windows, AI and voice settings. Keys stay in `data/config.json` (mode 600) and never reach the browser. Keys in your shell (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, `GOOGLE_TTS_API_KEY`) are copied in when you run the installer.
- **Record:** on any line clip, Record line. The take is denoised, trimmed and normalised; the mouth follows your recording. You can also upload an audio or video file.
- **Clone:** Voice lab, Clone a voice. Record or upload one to three minutes of speech, confirm it is your voice or that you have the speaker's permission, and ElevenLabs creates the voice. For audio from your own YouTube, Instagram or TikTok channel, download it from YouTube Studio or the platform's data export and upload the file.

## Motion and look

The production viewport (Display menu) runs ambient occlusion, bloom, a colour grade and anti-aliasing live; Film view adds depth of field on whoever is in shot. Turn it off for a fast viewport on a busy scene. Renders use the same look at full resolution.


Natural motion (Display menu) adds weight shift into acceleration, banking on turns, follow-through on head, arms, tail and hair, breathing, eye darts and eye contact with whoever is speaking. Jumps squash and stretch. Playback evaluates in-between frames so it stays smooth on a 60 Hz screen. The filmic tone curve is on by default (Environment). Renders can add motion blur.

## Install or update

From the folder with the zip:

```
Z=$(ls -t ~/Downloads/mayatoon-v*.zip | head -1) && rm -rf /tmp/mt && unzip -q "$Z" -d /tmp/mt && bash /tmp/mt/mayatoon/install.sh
```

The installer copies the app to `~/Sites/mayatoon`, backs up the previous build (last five), sets up Piper in `.venv`, adds ffmpeg and espeak-ng with Homebrew if missing, copies scenes, media and voices from `~/Sites/minimaya` once (that folder is left as is), starts a launchd service `com.manish.mayatoon` on port **47219**, commits the build and pushes to your public GitHub repo `mayatoon` when `gh` is logged in, and opens the studio.

| Setting | Default | Change with |
|---|---|---|
| Port | 47219 | `MAYATOON_PORT=5xxxx` |
| Bind address | 127.0.0.1 | `MAYATOON_HOST=0.0.0.0` |
| Folder | ~/Sites/mayatoon | `MAYATOON_DEST=…` |
| Copy Mini Maya data | once | `MAYATOON_NO_MIGRATE=1` |
| Stop old Mini Maya service | no | `MAYATOON_RETIRE_MINIMAYA=1` |
| GitHub push | when gh is logged in | `MAYATOON_NO_PUSH=1` |
| Offline voices | on | `MAYATOON_NO_TTS=1` |

Control: `ctl.sh status | restart | stop | start | logs | open`. `run.sh` runs in the foreground. `uninstall.sh` removes the service and keeps your data.

**On the internet:** the server has no login and holds your API keys. If you put it behind a Cloudflare tunnel, put Cloudflare Access in front of it, otherwise anyone with the URL can spend your voice and AI credits.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | app, version, ffmpeg |
| GET | /api/story/meta | cultures, languages, which writers are available |
| POST | /api/story | write a story: {prompt, culture, language, length, cast, cast_type, engine} |
| GET/PUT | /api/config | settings (keys masked); PUT merges, null removes |
| POST | /api/config/test | {provider}: check a voice service or Ollama |
| GET | /api/tts/voices | every voice with language, engine, gender |
| POST | /api/tts | speak {text, voice, pitch, rate, style, lang} into a cached WAV |
| POST | /api/audio/clean | denoise, trim and normalise an uploaded recording |
| POST | /api/voices/clone | {name, samples, consent, consent_text}: ElevenLabs instant clone |
| GET / DELETE | /api/voices/profiles[/id] | your cloned voices |
| GET/PUT/DELETE | /api/scenes/<n> | scenes |
| PUT | /api/assets/<file> | upload glb, image, audio or video (300 MB) |
| PUT / POST / DELETE | /api/render/<job>/… | movie frames, encode, cancel |
