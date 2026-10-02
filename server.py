#!/usr/bin/env python3
"""MayaToon server: serves the studio, stores scenes and media, voices lines (offline and cloud),
clones voices with consent, writes culture-based mini stories, and encodes movies with ffmpeg.
Standard library only."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "dev"
DATA = Path(os.environ.get("MAYATOON_DATA", ROOT / "data"))
SCENES = DATA / "scenes"
ASSETS = DATA / "assets"
RENDERS = DATA / "renders"
VOICES = DATA / "voices"
STORIES = DATA / "stories"
TMP = DATA / "tmp"
CONFIG = DATA / "config.json"
PROFILES = DATA / "voice_profiles.json"
VENV_PY = Path(os.environ.get("MAYATOON_PIPER_PY", ROOT / ".venv" / "bin" / "python"))
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ASSET_RE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
JOB_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm", ".opus", ".flac", ".mp4", ".mov"}
ASSET_EXT = AUDIO_EXT | {".glb", ".vrm", ".png", ".jpg", ".jpeg"}
MAX_BODY = 20 * 1024 * 1024
MAX_ASSET = 300 * 1024 * 1024
MAX_FRAME = 60 * 1024 * 1024
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf-binary", ".vrm")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/webm", ".webm")

CULTURES = json.loads((ROOT / "cultures.json").read_text(encoding="utf-8"))
TEMPLATES = json.loads((ROOT / "story_templates.json").read_text(encoding="utf-8"))
SPECIES = ["human", "cat", "dog", "bear", "bunny", "fox", "pig", "panda", "tiger", "lion", "raccoon"]
ACTIONS = ["idle", "walk", "run", "wave", "talk", "jump", "dance", "cheer", "point", "think", "look", "sit",
           "sad", "surprised", "angry", "namaste", "clap", "nod", "shake", "bow"]
PROPS = ["tree", "pine", "bush", "rock", "house", "bench", "lamp", "fence", "flowers", "ball", "mountains", "stupa",
         "prayer_flags", "temple", "gopuram", "banyan", "palm", "kolam", "well", "cart", "stall", "pots", "diyas", "cottage"]
EXPRS = ["neutral", "happy", "sad", "angry", "surprised"]
LANG_NAMES = {"en": "English", "ne": "Nepali", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam",
              "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "ur": "Urdu", "si": "Sinhala"}
SCRIPTS = {"en": "Latin", "ne": "Devanagari", "hi": "Devanagari", "mr": "Devanagari", "te": "Telugu", "ta": "Tamil", "kn": "Kannada",
           "ml": "Malayalam", "bn": "Bengali", "gu": "Gujarati", "pa": "Gurmukhi", "ur": "Urdu (Perso-Arabic)", "si": "Sinhala"}

# ---------------------------------------------------------------- config
SECRETS = {"anthropic_key": "ANTHROPIC_API_KEY", "openai_key": "OPENAI_API_KEY", "eleven_key": "ELEVENLABS_API_KEY",
           "azure_key": "AZURE_SPEECH_KEY", "google_key": "GOOGLE_TTS_API_KEY"}
DEFAULTS = {"anthropic_model": "claude-sonnet-5-5", "openai_model": "gpt-4o-mini", "openai_tts_model": "gpt-4o-mini-tts",
            "ollama_url": "http://127.0.0.1:11434", "ollama_model": "llama3.1", "eleven_model": "eleven_multilingual_v2",
            "azure_region": os.environ.get("AZURE_SPEECH_REGION", ""), "story_engine": "auto", "tts_prefer": "auto",
            "cloud_langs": "en,hi,ne,te,ta,kn,ml,bn,mr,gu,pa,ur,si"}
_cfg_lock = threading.Lock()


def load_cfg():
    try:
        d = json.loads(CONFIG.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def cfg(k):
    d = load_cfg()
    v = d.get(k)
    if v:
        return v
    if k in SECRETS:
        return os.environ.get(SECRETS[k], "")
    return DEFAULTS.get(k, "")


def save_cfg(update):
    with _cfg_lock:
        d = load_cfg()
        for k, v in update.items():
            if k not in SECRETS and k not in DEFAULTS:
                continue
            if v is None:
                d.pop(k, None)
            elif isinstance(v, str) and (v.strip() or k not in SECRETS):
                d[k] = v.strip()
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2))
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG)
    _voice_cache["t"] = 0
    _cloud_cache.clear()
    _cloud_errors.clear()
    _ollama["t"] = 0


def public_cfg():
    d = load_cfg()
    secrets = {}
    for k, env in SECRETS.items():
        v = d.get(k) or os.environ.get(env, "")
        secrets[k] = {"set": bool(v), "hint": ("…" + v[-4:]) if len(v) > 8 else ("set" if v else ""), "from": "config" if d.get(k) else ("env" if v else "")}
    return {"values": {k: cfg(k) for k in DEFAULTS}, "secrets": secrets, "errors": dict(_cloud_errors)}


# ---------------------------------------------------------------- http helper
def http(method, url, headers=None, body=None, timeout=60):
    data = body
    headers = dict(headers or {})
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=dict({"User-Agent": "MayaToon/" + VERSION}, **headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw = e.read()[:600].decode("utf-8", "replace")
        msg = raw
        try:
            j = json.loads(raw)
            msg = (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else j.get("detail") or j.get("error") or raw
            if isinstance(msg, dict):
                msg = msg.get("message") or json.dumps(msg)
        except Exception:
            pass
        raise RuntimeError("%s answered %d: %s" % (urllib.parse.urlparse(url).netloc, e.code, str(msg)[:300]))
    except urllib.error.URLError as e:
        raise RuntimeError("Could not reach %s (%s)" % (urllib.parse.urlparse(url).netloc, e.reason))
    except TimeoutError:
        raise RuntimeError("%s did not answer in time" % urllib.parse.urlparse(url).netloc)


def jget(url, headers=None, timeout=20):
    return json.loads(http("GET", url, headers, timeout=timeout)[1])


def find_ffmpeg():
    for c in (os.environ.get("MAYATOON_FFMPEG"), shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---------------------------------------------------------------- voices
PIPER_GENDER = {"amy": "f", "ryan": "m", "alba": "f", "lessac": "f", "pratham": "m", "priyamvada": "f", "rohan": "m", "alan": "m",
                "jenny_dioco": "f", "northern_english_male": "m", "southern_english_female": "f", "cori": "f", "hfc_female": "f",
                "hfc_male": "m", "joe": "m", "john": "m", "kristin": "f", "kusal": "m", "danny": "m", "kathleen": "f", "bryce": "m",
                "norman": "m", "ljspeech": "f", "maya": "f", "padmavathi": "f", "venkatesh": "m", "arjun": "m", "meera": "f", "sam": "m"}
MAC_GENDER = {"samantha": "f", "alex": "m", "daniel": "m", "karen": "f", "moira": "f", "tessa": "f", "rishi": "m", "veena": "f",
              "lekha": "f", "fred": "m", "victoria": "f", "fiona": "f", "tom": "m", "allison": "f", "ava": "f", "susan": "f", "kate": "f",
              "serena": "f", "oliver": "m", "aman": "m", "tara": "f", "vani": "f", "geeta": "f", "soumya": "f", "zoe": "f", "evan": "m"}
OPENAI_VOICES = [("alloy", ""), ("ash", "m"), ("ballad", "m"), ("coral", "f"), ("echo", "m"), ("fable", "m"), ("onyx", "m"),
                 ("nova", "f"), ("sage", "f"), ("shimmer", "f"), ("verse", "m")]
_voice_cache = {"t": 0, "list": []}
_cloud_cache = {}
_cloud_errors = {}
_ollama = {"t": 0, "ok": False, "models": []}


def piper_voices():
    if not VENV_PY.exists():
        return []
    out = []
    for onnx in sorted(VOICES.glob("*.onnx")):
        meta = {}
        try:
            meta = json.loads(Path(str(onnx) + ".json").read_text())
        except Exception:
            pass
        lang = (meta.get("language") or {}).get("code") or onnx.stem.split("-")[0]
        parts = onnx.stem.split("-")
        key = parts[1] if len(parts) > 2 else onnx.stem
        base = key.replace("_", " ").title()
        speakers = meta.get("speaker_id_map") or {}
        if meta.get("num_speakers", 1) > 1 and speakers:
            for name, sid in list(speakers.items())[:8]:
                out.append({"id": "piper:%s#%d" % (onnx.stem, sid), "name": "%s %s" % (base, name), "lang": lang, "engine": "piper", "gender": ""})
        else:
            out.append({"id": "piper:" + onnx.stem, "name": base, "lang": lang, "engine": "piper", "gender": PIPER_GENDER.get(key, "")})
    return out


def say_voices():
    if sys.platform != "darwin" or not shutil.which("say"):
        return []
    try:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=20)
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        m = re.match(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]+)\s+#", line)
        if m:
            n = m.group(1).strip()
            out.append({"id": "say:" + n, "name": n, "lang": m.group(2), "engine": "mac", "gender": MAC_GENDER.get(n.split(" ")[0].lower(), "")})
    return out


def espeak_exe():
    return shutil.which("espeak-ng") or shutil.which("espeak") or next((p for p in ("/opt/homebrew/bin/espeak-ng", "/usr/local/bin/espeak-ng") if os.path.exists(p)), None)


def espeak_voices():
    exe = espeak_exe()
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "--voices"], capture_output=True, text=True, timeout=20)
    except Exception:
        return []
    out = []
    keep = set(cfg("cloud_langs").split(","))
    for line in r.stdout.splitlines()[1:]:
        f = line.split()
        if len(f) >= 4 and f[1].split("-")[0] in keep:
            out.append({"id": "espeak:" + f[1], "name": f[3].replace("_", " "), "lang": f[1], "engine": "espeak", "gender": ""})
    return out


def cloud(name, fn, ttl=900):
    c = _cloud_cache.get(name)
    if c and time.time() < c[0]:
        return c[1]
    try:
        v = fn()
        _cloud_errors.pop(name, None)
    except Exception as e:
        v = []
        _cloud_errors[name] = str(e)[:300]
        ttl = 60
    _cloud_cache[name] = (time.time() + ttl, v)
    return v


def wanted_lang(code):
    return (code or "").replace("_", "-").split("-")[0].lower() in set(cfg("cloud_langs").split(","))


def eleven_voices():
    key = cfg("eleven_key")
    if not key:
        return []
    j = jget("https://api.elevenlabs.io/v1/voices", {"xi-api-key": key})
    out = []
    for v in j.get("voices", []):
        lab = v.get("labels") or {}
        g = (lab.get("gender") or "")[:1].lower()
        mine = v.get("category") in ("cloned", "generated", "professional")
        out.append({"id": "eleven:" + v["voice_id"], "name": v.get("name", "voice") + (" (your voice)" if mine else ""), "lang": "*",
                    "engine": "elevenlabs", "gender": g if g in ("f", "m") else "", "mine": mine})
    return out


def azure_voices():
    key, region = cfg("azure_key"), cfg("azure_region")
    if not key or not region:
        return []
    j = jget("https://%s.tts.speech.microsoft.com/cognitiveservices/voices/list" % region, {"Ocp-Apim-Subscription-Key": key})
    out = []
    for v in j:
        if not wanted_lang(v.get("Locale")):
            continue
        g = (v.get("Gender") or "")[:1].lower()
        out.append({"id": "azure:%s|%s" % (v["ShortName"], v["Locale"]), "name": "%s (%s)" % (v.get("DisplayName") or v["ShortName"], v["Locale"]),
                    "lang": v["Locale"], "engine": "azure", "gender": g if g in ("f", "m") else ""})
    return out


def google_voices():
    key = cfg("google_key")
    if not key:
        return []
    j = jget("https://texttospeech.googleapis.com/v1/voices?key=" + urllib.parse.quote(key))
    out = []
    for v in j.get("voices", []):
        lc = (v.get("languageCodes") or ["en-US"])[0]
        if not wanted_lang(lc) or not re.search(r"(Neural2|Wavenet|Chirp|Studio)", v["name"]):
            continue
        g = {"FEMALE": "f", "MALE": "m"}.get(v.get("ssmlGender"), "")
        out.append({"id": "google:%s|%s" % (v["name"], lc), "name": v["name"], "lang": lc, "engine": "google", "gender": g})
    return out


def openai_voices():
    if not cfg("openai_key"):
        return []
    return [{"id": "openai:" + n, "name": n.title(), "lang": "*", "engine": "openai", "gender": g} for n, g in OPENAI_VOICES]


def all_voices():
    if time.time() - _voice_cache["t"] > 30:
        local = piper_voices() + say_voices() + espeak_voices()
        remote = cloud("azure", azure_voices) + cloud("elevenlabs", eleven_voices) + cloud("google", google_voices) + cloud("openai", openai_voices)
        _voice_cache["list"] = remote + local
        _voice_cache["t"] = time.time()
    return _voice_cache["list"]


STYLE_HINT = {"happy": "cheerful and warm", "sad": "soft and a little sad", "angry": "cross but still kid-friendly",
              "surprised": "surprised and excited", "neutral": "natural and friendly"}


def synth(voice, text, pitch, rate, dest, style="", lang=""):
    ff = find_ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    stem = TMP / hashlib.sha1((voice + text + str(time.time())).encode()).hexdigest()[:16]
    txt = stem.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    native_rate = True
    try:
        engine, _, name = voice.partition(":")
        r = None
        if engine == "piper":
            model, _, sid = name.partition("#")
            onnx = VOICES / (model + ".onnx")
            if not onnx.exists() or not VENV_PY.exists():
                raise RuntimeError("That Piper voice is not installed")
            raw = stem.with_suffix(".wav")
            r = subprocess.run([str(VENV_PY), str(ROOT / "tts_piper.py"), str(onnx), str(raw), "%.3f" % (1.0 / rate), sid or ""],
                               input=text, capture_output=True, text=True, timeout=180)
        elif engine == "say":
            raw = stem.with_suffix(".aiff")
            r = subprocess.run(["say", "-v", name, "-r", str(int(180 * rate)), "-o", str(raw), "-f", str(txt)], capture_output=True, text=True, timeout=180)
        elif engine == "espeak":
            exe = espeak_exe()
            if not exe:
                raise RuntimeError("espeak-ng is not installed")
            raw = stem.with_suffix(".wav")
            r = subprocess.run([exe, "-v", name, "-s", str(int(160 * rate)), "-w", str(raw), "-f", str(txt)], capture_output=True, text=True, timeout=180)
        elif engine == "eleven":
            key = cfg("eleven_key")
            if not key:
                raise RuntimeError("Add an ElevenLabs key in AI & voice settings")
            raw = stem.with_suffix(".mp3")
            body = {"text": text, "model_id": cfg("eleven_model"), "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}
            raw.write_bytes(http("POST", "https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128" % name, {"xi-api-key": key}, body, timeout=120)[1])
            native_rate = False
        elif engine == "azure":
            key, region = cfg("azure_key"), cfg("azure_region")
            if not key or not region:
                raise RuntimeError("Add an Azure Speech key and region in AI & voice settings")
            short, _, locale = name.partition("|")
            esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            ssml = "<speak version='1.0' xml:lang='%s'><voice name='%s'>%s</voice></speak>" % (locale or "en-US", short, esc)
            raw = stem.with_suffix(".wav")
            raw.write_bytes(http("POST", "https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region,
                                 {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm"},
                                 ssml.encode("utf-8"), timeout=120)[1])
            native_rate = False
        elif engine == "openai":
            key = cfg("openai_key")
            if not key:
                raise RuntimeError("Add an OpenAI key in AI & voice settings")
            raw = stem.with_suffix(".wav")
            body = {"model": cfg("openai_tts_model"), "voice": name, "input": text, "response_format": "wav"}
            if "gpt-4o" in body["model"]:
                body["instructions"] = "Voice a character in a children's animated film. Sound %s.%s" % (
                    STYLE_HINT.get(style, STYLE_HINT["neutral"]), (" Speak in %s with a natural local accent." % LANG_NAMES[lang]) if lang in LANG_NAMES and lang != "en" else "")
            raw.write_bytes(http("POST", "https://api.openai.com/v1/audio/speech", {"Authorization": "Bearer " + key}, body, timeout=120)[1])
            native_rate = False
        elif engine == "google":
            key = cfg("google_key")
            if not key:
                raise RuntimeError("Add a Google Cloud TTS key in AI & voice settings")
            vname, _, lc = name.partition("|")
            j = json.loads(http("POST", "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + urllib.parse.quote(key), None,
                                {"input": {"text": text}, "voice": {"languageCode": lc, "name": vname}, "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}, timeout=120)[1])
            raw = stem.with_suffix(".wav")
            raw.write_bytes(base64.b64decode(j["audioContent"]))
            native_rate = False
        else:
            raise RuntimeError("Unknown voice")
        if r is not None and (r.returncode != 0 or not raw.exists()):
            raise RuntimeError("Speech engine failed: " + (r.stderr or "").strip()[-300:])
        if ff:
            af = ["aresample=44100"]
            if pitch:
                k = 2 ** (pitch / 12.0)
                af += ["asetrate=%d" % round(44100 * k), "aresample=44100", "atempo=%.5f" % (1 / k)]
            if not native_rate and abs(rate - 1) > 0.01:
                af.append("atempo=%.4f" % rate)
            af += ["silenceremove=start_periods=1:start_threshold=-50dB", "loudnorm=I=-16:TP=-1.5:LRA=11", "aresample=44100", "apad=pad_dur=0.12"]
            r2 = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-af", ",".join(af), "-ac", "1", "-c:a", "pcm_s16le", str(dest)],
                                capture_output=True, text=True, timeout=120)
            if r2.returncode != 0:
                raise RuntimeError("ffmpeg could not process the voice: " + r2.stderr.strip()[-300:])
        elif raw.suffix == ".wav":
            shutil.copy(raw, dest)
        else:
            raise RuntimeError("ffmpeg is needed to convert this voice")
    finally:
        for f in TMP.glob(stem.name + ".*"):
            f.unlink(missing_ok=True)


def wav_duration(p):
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def clean_audio(src, dest, denoise=True, trim=True):
    ff = find_ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg is needed to process recordings (brew install ffmpeg)")
    af = ["highpass=f=70"]
    if denoise:
        af.append("afftdn=nf=-28")
    if trim:
        t = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08"
        af += [t, "areverse", t, "areverse"]
    af += ["loudnorm=I=-16:TP=-1.5:LRA=11", "aresample=44100", "apad=pad_dur=0.1"]
    r = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-af", ",".join(af), "-ac", "1", "-c:a", "pcm_s16le", str(dest)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not dest.exists():
        raise RuntimeError("ffmpeg could not read that recording: " + r.stderr.strip()[-300:])


# ---------------------------------------------------------------- voice cloning (ElevenLabs, consent required)
def load_profiles():
    try:
        return json.loads(PROFILES.read_text())
    except Exception:
        return []


def save_profiles(p):
    PROFILES.write_text(json.dumps(p, indent=2, ensure_ascii=False))


def multipart(fields, files):
    b = "----mayatoon" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields:
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (b, k, v)).encode()
    for k, fn, ctype, data in files:
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n" % (b, k, fn, ctype)).encode()
        out += data + b"\r\n"
    out += ("--%s--\r\n" % b).encode()
    return bytes(out), "multipart/form-data; boundary=" + b


def clone_voice(name, samples, consent_text, description=""):
    key = cfg("eleven_key")
    if not key:
        raise RuntimeError("Voice cloning uses ElevenLabs. Add your ElevenLabs key in AI & voice settings first.")
    if not samples:
        raise RuntimeError("Record or upload at least one sample")
    files, total = [], 0.0
    TMP.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(samples[:25]):
        p = ASSETS / s
        if not ASSET_RE.match(s) or not p.exists():
            raise RuntimeError("Sample %s is missing" % s)
        cleaned = TMP / ("clone_%d_%s.wav" % (i, uuid.uuid4().hex[:6]))
        clean_audio(p, cleaned, denoise=True, trim=True)
        total += wav_duration(cleaned)
        files.append(("files", "sample%d.wav" % (i + 1), "audio/wav", cleaned.read_bytes()))
        cleaned.unlink(missing_ok=True)
    if total < 20:
        raise RuntimeError("Only %.0f seconds of speech. Record or upload at least 30 seconds (one to three minutes clones best)." % total)
    body, ctype = multipart([("name", name), ("description", (description or "MayaToon voice")[:400]), ("remove_background_noise", "true"),
                             ("labels", json.dumps({"source": "mayatoon"}))], files)
    j = json.loads(http("POST", "https://api.elevenlabs.io/v1/voices/add", {"xi-api-key": key, "Content-Type": ctype}, body, timeout=300)[1])
    prof = {"id": uuid.uuid4().hex[:10], "name": name, "provider": "elevenlabs", "voice": "eleven:" + j["voice_id"], "seconds": round(total, 1),
            "samples": samples, "consent": {"text": consent_text, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, "created": time.time()}
    profs = load_profiles()
    profs.append(prof)
    save_profiles(profs)
    _cloud_cache.pop("elevenlabs", None)
    _voice_cache["t"] = 0
    return prof


def delete_clone(pid):
    profs = load_profiles()
    p = next((x for x in profs if x["id"] == pid), None)
    if not p:
        raise RuntimeError("No such voice profile")
    key = cfg("eleven_key")
    if key and p["voice"].startswith("eleven:"):
        try:
            http("DELETE", "https://api.elevenlabs.io/v1/voices/" + p["voice"].split(":", 1)[1], {"xi-api-key": key}, timeout=30)
        except RuntimeError as e:
            if "404" not in str(e):
                raise
    save_profiles([x for x in profs if x["id"] != pid])
    _cloud_cache.pop("elevenlabs", None)
    _voice_cache["t"] = 0


# ---------------------------------------------------------------- story writer
def ollama_status():
    if time.time() - _ollama["t"] > 60:
        try:
            j = jget(cfg("ollama_url").rstrip("/") + "/api/tags", timeout=1.2)
            _ollama.update(ok=True, models=[m.get("name") for m in j.get("models", [])])
        except Exception:
            _ollama.update(ok=False, models=[])
        _ollama["t"] = time.time()
    return _ollama


def engines():
    o = ollama_status()
    return {"claude": bool(cfg("anthropic_key")), "openai": bool(cfg("openai_key")), "ollama": o["ok"], "ollama_models": o["models"], "offline": True}


LENGTHS = {"short": (7, 10, "about 30 seconds"), "medium": (11, 15, "about a minute"), "long": (16, 22, "about 90 seconds")}


def story_prompt(o):
    c = CULTURES.get(o["culture"]) or CULTURES["english-uk"]
    lang = o.get("language") or c["lang"]
    lname, script = LANG_NAMES.get(lang, lang), SCRIPTS.get(lang, "its usual")
    lo, hi, secs = LENGTHS.get(o.get("length"), LENGTHS["short"])
    cast = o.get("cast") or "auto"
    kinds = {"humans": "all human characters", "animals": "all animal characters (talking animals)", "mixed": "a mix of humans and talking animals"}.get(
        o.get("cast_type"), "humans, animals or a mix, whatever suits the story")
    system = """You are the head writer at MayaToon, a small studio that makes short, warm 3D cartoon films for families.
You write ONE complete mini story as JSON. An automatic director turns your JSON into a 3D scene, so follow the schema exactly.

Culture and setting: %(label)s. Typical setting: %(setting)s. Festivals: %(fests)s. Foods: %(foods)s.
Use authentic names, customs, food, greetings and festival details from this culture. Be respectful and specific; no stereotypes, no mocking accents, no religion-as-a-joke. Family-friendly, gentle humour.

Language: every spoken line goes in "say", written in %(lname)s using the %(script)s script only (never transliterated into Latin letters unless the language is English). Put a natural English translation in "en". Keep each line short enough to say in one breath (at most about 14 words). Elders may be addressed by the respectful titles used in this culture.

Shape: a clear little arc: setup, a small problem or wish, a turning point, a warm resolution, and an ending beat everyone can enjoy (dance, cheer, clap, namaste). %(lo)d to %(hi)d beats, %(secs)s of film. Narrator lines are optional (0 to 3).

Return JSON only, no markdown, matching:
{
 "title": "title in %(lname)s", "title_en": "English title", "logline": "one English sentence",
 "setting": {"time": "day|golden|night", "props": [3 to 8 of: %(props)s]},
 "narrator": {"gender": "f|m"} or null,
 "characters": [{"name": "...", "species": one of %(species)s, "gender": "f|m", "age": "child|adult|elder", "personality": "two words"}],
 "beats": [{"who": "character name or Narrator", "action": one of %(actions)s, "say": "line or empty", "en": "English or empty", "expr": one of %(exprs)s, "at": "name of who is being spoken to, or empty", "to": "for walk/run only: a character name or prop:<kind> from setting.props", "parallel": false}]
}
Rules: Narrator beats have only who, say and en. Every character appears in at least two beats. Use "parallel": true only when a beat should start at the same moment as the previous beat (for example two characters dancing together). Use walk/run with "to" to bring characters together; use talk for plain dialogue and gesture actions (wave, point, think, namaste, clap, nod, shake, bow, cheer, jump, sad, surprised, angry) when the line carries that feeling.""" % {
        "label": c["label"], "setting": c["setting"], "fests": ", ".join(c.get("festivals", [])), "foods": ", ".join(c.get("foods", [])),
        "lname": lname, "script": script, "lo": lo, "hi": hi, "secs": secs, "props": ", ".join(PROPS), "species": "/".join(SPECIES),
        "actions": "/".join(ACTIONS), "exprs": "/".join(EXPRS)}
    user = "Story idea: %s\nCast: %s, %s.\nWrite the JSON now." % (
        o.get("prompt") or "surprise me with a festival story", ("%s characters" % cast) if cast != "auto" else "2 to 4 characters", kinds)
    return system, user


def extract_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise RuntimeError("The AI did not return a story (no JSON found)")
    return json.loads(t[a:b + 1])


def write_claude(o):
    system, user = story_prompt(o)
    j = json.loads(http("POST", "https://api.anthropic.com/v1/messages", {"x-api-key": cfg("anthropic_key"), "anthropic-version": "2023-06-01"},
                        {"model": cfg("anthropic_model"), "max_tokens": 6000, "system": system, "messages": [{"role": "user", "content": user}]}, timeout=180)[1])
    return extract_json("".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text"))


def write_openai(o):
    system, user = story_prompt(o)
    j = json.loads(http("POST", "https://api.openai.com/v1/chat/completions", {"Authorization": "Bearer " + cfg("openai_key")},
                        {"model": cfg("openai_model"), "response_format": {"type": "json_object"}, "temperature": 0.9,
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout=180)[1])
    return extract_json(j["choices"][0]["message"]["content"])


def write_ollama(o):
    system, user = story_prompt(o)
    st = ollama_status()
    model = cfg("ollama_model")
    if st["models"] and model not in st["models"] and not any(m.split(":")[0] == model for m in st["models"]):
        model = st["models"][0]
    j = json.loads(http("POST", cfg("ollama_url").rstrip("/") + "/api/chat", None,
                        {"model": model, "stream": False, "format": "json", "options": {"temperature": 0.9},
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout=600)[1])
    return extract_json(j["message"]["content"])


def write_offline(o):
    c = CULTURES.get(o["culture"]) or CULTURES["english-uk"]
    lang = o.get("language") or c["lang"]
    prompt = (o.get("prompt") or "").lower()
    rnd = random.Random(hashlib.sha1((prompt + o["culture"]).encode()).hexdigest())
    arcs = TEMPLATES["arcs"]
    arc_id = max(arcs, key=lambda k: (sum(w in prompt for w in arcs[k]["keywords"]), k == "lost_kite"))
    arc = arcs[arc_id]
    tl = lang if lang in arc["title"] else "en"
    animals = [s for s in SPECIES if s != "human"]
    named = [s for s in animals if s in prompt]
    ctype = o.get("cast_type") or "auto"
    chars, roles = [], {}
    for role in arc["cast"]:
        g = rnd.choice("fm")
        species = "human"
        if ctype == "animals" or (ctype == "mixed" and role == "B") or (named and role == "B"):
            species = named.pop(0) if named else rnd.choice(animals)
        if role == "E":
            g = "f"
            name = c["names"]["elder_f"]
        else:
            pool = [n for n in c["names"][g] if n not in [x["name"] for x in chars]]
            name = rnd.choice(pool)
        roles[role] = name
        chars.append({"name": name, "species": species, "gender": g, "age": "elder" if role == "E" else "child", "personality": ""})
    fest = c.get("festival", "the festival")
    nat = c.get("native", {}) if lang == c["lang"] else {}

    def fill(s, native=False):
        for r, n in roles.items():
            s = s.replace("{%s}" % r, nat.get(n, n) if native else n)
        return s.replace("{F}", fest)
    beats = []
    for b in arc["beats"]:
        nb = {"who": "Narrator" if b["who"] == "N" else roles[b["who"]]}
        for k in ("action", "expr", "parallel"):
            if k in b:
                nb[k] = b[k]
        if b.get("at"):
            nb["at"] = roles.get(b["at"], "")
        if b.get("to"):
            nb["to"] = b["to"] if b["to"].startswith("prop:") else roles.get(b["to"], "")
        if b.get("say"):
            s = b["say"].get(lang) or b["say"]["en"]
            if isinstance(s, dict):
                spk = next((x for x in chars if x["name"] == nb["who"]), {"gender": "f"})
                s = s.get(spk["gender"]) or next(iter(s.values()))
            nb["say"] = fill(s, native=True)
            nb["en"] = fill(b.get("en", ""))
        beats.append(nb)
    props = list(dict.fromkeys(c["props"]))
    if "tree" not in props and arc_id == "lost_kite":
        props.append("tree")
    return {"title": arc["title"][tl], "title_en": arc["title"]["en"], "logline": "", "setting": {"time": c["env"]["time"], "props": props},
            "narrator": {"gender": "f"}, "characters": chars, "beats": beats,
            "note": None if lang in ("en", "ne", "hi", "te", "ta") else "Offline templates have English dialogue for this culture. Set up an AI engine for %s lines." % LANG_NAMES.get(lang, lang)}


def normalize(s, o):
    c = CULTURES.get(o["culture"]) or CULTURES["english-uk"]
    lang = o.get("language") or c["lang"]
    if not isinstance(s, dict):
        raise RuntimeError("The story was not a JSON object")
    chars, seen = [], set()
    for ch in (s.get("characters") or [])[:6]:
        if not isinstance(ch, dict) or not ch.get("name"):
            continue
        n = str(ch["name"]).strip()[:24]
        if n in seen or n.lower() == "narrator":
            continue
        seen.add(n)
        sp = str(ch.get("species", "human")).lower()
        chars.append({"name": n, "species": sp if sp in SPECIES else "human", "gender": "m" if str(ch.get("gender", "")).lower().startswith("m") else "f",
                      "age": ch.get("age") if ch.get("age") in ("child", "adult", "elder") else "child", "personality": str(ch.get("personality", ""))[:40]})
    if not chars:
        raise RuntimeError("The story had no characters")
    names = {x["name"] for x in chars}
    st = s.get("setting") if isinstance(s.get("setting"), dict) else {}
    props = [p for p in (st.get("props") or []) if p in PROPS][:10] or list(dict.fromkeys(c["props"]))
    beats = []
    for b in (s.get("beats") or [])[:40]:
        if not isinstance(b, dict):
            continue
        who = str(b.get("who", "")).strip()
        say = str(b.get("say") or "").strip()[:300]
        en = str(b.get("en") or "").strip()[:300]
        if who.lower() == "narrator":
            if say:
                beats.append({"who": "Narrator", "say": say, "en": en})
            continue
        if who not in names:
            continue
        a = str(b.get("action") or ("talk" if say else "idle")).lower()
        nb = {"who": who, "action": a if a in ACTIONS else ("talk" if say else "idle")}
        if say:
            nb["say"], nb["en"] = say, en
        e = str(b.get("expr") or "").lower()
        if e in EXPRS:
            nb["expr"] = e
        if b.get("at") in names and b.get("at") != who:
            nb["at"] = b["at"]
        to = str(b.get("to") or "")
        if nb["action"] in ("walk", "run"):
            if to in names and to != who:
                nb["to"] = to
            elif to.startswith("prop:") and to[5:] in PROPS:
                nb["to"] = to
                if to[5:] not in props:
                    props.append(to[5:])
        if b.get("parallel") is True and beats:
            nb["parallel"] = True
        beats.append(nb)
    if not beats:
        raise RuntimeError("The story had no usable beats")
    nar = s.get("narrator")
    return {"title": str(s.get("title") or s.get("title_en") or "Untitled")[:80], "title_en": str(s.get("title_en") or "")[:80],
            "logline": str(s.get("logline") or "")[:240], "culture": o["culture"], "language": lang, "prompt": o.get("prompt", ""),
            "setting": {"time": st.get("time") if st.get("time") in ("day", "golden", "night") else c["env"]["time"], "props": props},
            "narrator": {"gender": "m" if str((nar or {}).get("gender", "")).startswith("m") else "f"} if nar or any(b["who"] == "Narrator" for b in beats) else None,
            "characters": chars, "beats": beats, "engine": s.get("_engine", ""), "note": s.get("note")}


def write_story(o):
    o["culture"] = o.get("culture") if o.get("culture") in CULTURES else "english-uk"
    if o.get("language") not in LANG_NAMES:
        o["language"] = CULTURES[o["culture"]]["lang"]
    want = o.get("engine") or cfg("story_engine") or "auto"
    av = engines()
    order = [want] if want != "auto" else [e for e in ("claude", "openai", "ollama") if av.get(e)] + ["offline"]
    errors = []
    for e in order:
        if e != "offline" and not av.get(e):
            errors.append("%s is not set up" % e)
            continue
        try:
            raw = {"claude": write_claude, "openai": write_openai, "ollama": write_ollama, "offline": write_offline}[e](o)
            raw["_engine"] = e
            story = normalize(raw, o)
            if errors:
                story["note"] = ((story.get("note") or "") + " Fell back to %s: %s." % (e, "; ".join(errors))).strip()
            STORIES.mkdir(parents=True, exist_ok=True)
            (STORIES / ("%s_%s.json" % (time.strftime("%Y%m%d-%H%M%S"), e))).write_text(json.dumps(story, ensure_ascii=False, indent=1), encoding="utf-8")
            return story
        except Exception as ex:
            errors.append("%s: %s" % (e, str(ex)[:200]))
    raise RuntimeError("; ".join(errors))


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    server_version = "MayaToon/" + VERSION

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        if "/api/render/" in (self.path or "") and " 200 " in (fmt % args):
            return
        sys.stdout.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args))
        sys.stdout.flush()

    def end_headers(self):
        path = urlparse(self.path).path
        if path.startswith("/api/") or path in ("/", "/index.html") or path.endswith(".json"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body_json(self, limit=262144):
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= limit:
            return {}
        try:
            d = json.loads(self.rfile.read(length))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def scene_path(self, name):
        return SCENES / (name + ".json") if NAME_RE.match(name) else None

    def asset_path(self, name):
        if not isinstance(name, str) or not ASSET_RE.match(name) or name.startswith(".") or Path(name).suffix.lower() not in ASSET_EXT:
            return None
        return ASSETS / name

    def route(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return None, path
        return [unquote(p) for p in path[len("/api/"):].split("/") if p], path

    def read_to_file(self, dest, limit):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > limit:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        left = length
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            tmp.unlink(missing_ok=True)
            return False
        os.replace(tmp, dest)
        return True

    def send_media(self, base, name):
        p = (base / name).resolve()
        if base.resolve() not in p.parents or not p.is_file():
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        size = p.stat().st_size
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_HEAD(self):
        _, path = self.route()
        if path.startswith("/media/"):
            return self.do_GET()
        return super().do_HEAD()

    def do_GET(self):
        parts, path = self.route()
        if parts is None:
            if path.startswith("/media/assets/"):
                return self.send_media(ASSETS, unquote(path[len("/media/assets/"):]))
            if path.startswith("/media/renders/"):
                return self.send_media(RENDERS, unquote(path[len("/media/renders/"):]))
            blocked = ("/data", "/logs", "/.git", "/.venv", "/releases", "/server.py", "/install.sh", "/run.sh", "/uninstall.sh", "/ctl.sh", "/mayatoon")
            if any(path.startswith(b) for b in blocked):
                return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return super().do_GET()
        if parts == ["health"]:
            return self.send_json(HTTPStatus.OK, {"ok": True, "app": "mayatoon", "version": VERSION, "ffmpeg": bool(find_ffmpeg()), "tts": True})
        if parts == ["tts", "voices"]:
            return self.send_json(HTTPStatus.OK, {"voices": all_voices(), "errors": dict(_cloud_errors)})
        if parts == ["config"]:
            return self.send_json(HTTPStatus.OK, public_cfg())
        if parts == ["story", "meta"]:
            return self.send_json(HTTPStatus.OK, {"cultures": CULTURES, "engines": engines(), "languages": LANG_NAMES, "default_engine": cfg("story_engine")})
        if parts == ["voices", "profiles"]:
            return self.send_json(HTTPStatus.OK, {"profiles": load_profiles()})
        if parts == ["scenes"]:
            items = []
            for f in SCENES.glob("*.json"):
                st = f.stat()
                items.append({"name": f.stem, "modified": st.st_mtime, "size": st.st_size})
            items.sort(key=lambda x: x["modified"], reverse=True)
            return self.send_json(HTTPStatus.OK, {"scenes": items})
        if len(parts) == 2 and parts[0] == "scenes":
            p = self.scene_path(parts[1])
            if not p or not p.exists():
                return self.send_json(HTTPStatus.NOT_FOUND, {"error": "No scene with that name"})
            body = p.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts == ["assets"]:
            items = [{"name": f.name, "size": f.stat().st_size} for f in sorted(ASSETS.glob("*")) if f.is_file() and not f.name.endswith(".part")]
            return self.send_json(HTTPStatus.OK, {"assets": items})
        if parts == ["renders"]:
            items = [{"name": f.name, "size": f.stat().st_size, "url": "media/renders/" + f.name, "modified": f.stat().st_mtime} for f in RENDERS.glob("*.mp4")]
            items.sort(key=lambda x: x["modified"], reverse=True)
            return self.send_json(HTTPStatus.OK, {"renders": items})
        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})

    def do_PUT(self):
        parts, _ = self.route()
        if parts == ["config"]:
            save_cfg(self.body_json())
            return self.send_json(HTTPStatus.OK, public_cfg())
        if parts and len(parts) == 2 and parts[0] == "assets":
            p = self.asset_path(parts[1])
            if not p:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Allowed files: glb, vrm, png, jpg and audio or video (mp3, wav, m4a, aac, ogg, webm, flac, mp4, mov)"})
            if not self.read_to_file(p, MAX_ASSET):
                return self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "File is empty or larger than 300 MB"})
            return self.send_json(HTTPStatus.OK, {"ok": True, "name": p.name, "url": "media/assets/" + p.name})
        if parts and len(parts) == 3 and parts[0] == "render" and JOB_RE.match(parts[1]) and parts[2].isdigit():
            dest = RENDERS / parts[1] / "frames" / ("%05d.png" % int(parts[2]))
            if not self.read_to_file(dest, MAX_FRAME):
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Frame is empty or too large"})
            return self.send_json(HTTPStatus.OK, {"ok": True})
        if not parts or len(parts) != 2 or parts[0] != "scenes":
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        p = self.scene_path(parts[1])
        if not p:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Use letters, numbers, dashes and underscores, up to 64"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Scene is empty or larger than 20 MB"})
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
            assert isinstance(data, dict) and isinstance(data.get("objects"), list)
        except Exception:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Body is not a MayaToon scene"})
        SCENES.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, p)
        return self.send_json(HTTPStatus.OK, {"ok": True, "name": parts[1], "path": str(p)})

    def guard(self, fn):
        try:
            return self.send_json(HTTPStatus.OK, fn())
        except RuntimeError as e:
            return self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(e)})
        except Exception as e:
            return self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_POST(self):
        parts, _ = self.route()
        if parts == ["tts"]:
            return self.tts()
        if parts == ["story"]:
            d = self.body_json()
            return self.guard(lambda: {"story": write_story(d)})
        if parts == ["audio", "clean"]:
            d = self.body_json()

            def go():
                src = self.asset_path(d.get("asset"))
                if not src or not src.exists() or src.suffix.lower() not in AUDIO_EXT:
                    raise RuntimeError("Upload the recording first")
                dest = ASSETS / ("rec_%s.wav" % hashlib.sha1((src.name + str(src.stat().st_mtime)).encode()).hexdigest()[:12])
                clean_audio(src, dest, denoise=d.get("denoise", True) is not False, trim=d.get("trim", True) is not False)
                return {"ok": True, "asset": dest.name, "duration": round(wav_duration(dest), 3), "url": "media/assets/" + dest.name}
            return self.guard(go)
        if parts == ["voices", "clone"]:
            d = self.body_json()

            def go():
                if d.get("consent") is not True or not str(d.get("consent_text", "")).strip():
                    raise RuntimeError("Confirm that this is your own voice or that the speaker gave you permission")
                name = re.sub(r"[^\w .'-]+", "", str(d.get("name", "")))[:40].strip()
                if not name:
                    raise RuntimeError("Give the voice a name")
                return {"profile": clone_voice(name, [str(x) for x in d.get("samples") or []], str(d["consent_text"])[:400], str(d.get("description", "")))}
            return self.guard(go)
        if parts == ["config", "test"]:
            d = self.body_json()

            def go():
                which = d.get("provider")
                if which == "ollama":
                    _ollama["t"] = 0
                    st = ollama_status()
                    if not st["ok"]:
                        raise RuntimeError("Ollama is not answering at " + cfg("ollama_url"))
                    return {"ok": True, "count": len(st["models"])}
                fn = {"azure": azure_voices, "elevenlabs": eleven_voices, "google": google_voices, "openai": openai_voices}.get(which)
                if not fn:
                    raise RuntimeError("Unknown provider")
                need = {"azure": ("azure_key", "azure_region"), "elevenlabs": ("eleven_key",), "google": ("google_key",), "openai": ("openai_key",)}[which]
                if not all(cfg(k) for k in need):
                    raise RuntimeError("Add the %s first, then test" % " and ".join(k.replace("_", " ") for k in need))
                _cloud_cache.pop(which, None)
                n = len(cloud(which, fn))
                if which in _cloud_errors:
                    raise RuntimeError(_cloud_errors[which])
                _voice_cache["t"] = 0
                return {"ok": True, "count": n}
            return self.guard(go)
        if not parts or len(parts) != 3 or parts[0] != "render" or parts[2] != "finish" or not JOB_RE.match(parts[1]):
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        return self.finish_render(parts[1])

    def finish_render(self, job):
        ff = find_ffmpeg()
        if not ff:
            return self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "ffmpeg is not installed on the studio Mac (brew install ffmpeg)"})
        opts = self.body_json(65536)
        jobdir = RENDERS / job
        frames = jobdir / "frames"
        n = len(list(frames.glob("*.png"))) if frames.exists() else 0
        if n == 0:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "No frames were uploaded for this render"})
        fps = max(1, min(120, int(opts.get("fps") or 24)))
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(opts.get("name") or job))[:90] or job
        out = RENDERS / (name + ".mp4")
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.png")]
        dur = n / fps
        tracks = opts.get("tracks") if isinstance(opts.get("tracks"), list) else []
        chains, k = [], 0
        for tr in tracks[:96]:
            ap = self.asset_path(tr.get("asset")) if isinstance(tr, dict) else None
            if not ap or not ap.exists():
                continue
            st = float(tr.get("start") or 0)
            if st >= dur:
                continue
            vol = max(0.0, min(2.0, float(tr.get("vol") if tr.get("vol") is not None else 1)))
            cmd += ["-i", str(ap)]
            k += 1
            f = ["aformat=sample_rates=48000:channel_layouts=stereo"]
            if st < 0:
                f.append("atrim=start=%.3f,asetpts=PTS-STARTPTS" % (-st))
            elif st > 0:
                f.append("adelay=delays=%d:all=1" % int(round(st * 1000)))
            f.append("volume=%.3f" % vol)
            chains.append("[%d:a]%s[a%d]" % (k, ",".join(f), k))
        if chains:
            mix = "".join("[a%d]" % i for i in range(1, k + 1))
            fc = ";".join(chains) + ";" + mix + ("amix=inputs=%d:duration=longest:dropout_transition=0:normalize=0," % k if k > 1 else "anull,") + "alimiter=limit=0.95,apad[aout]"
            cmd += ["-filter_complex", fc, "-map", "0:v:0", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
        cmd += ["-t", "%.3f" % dur, "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            return self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "ffmpeg took longer than an hour"})
        if r.returncode != 0 or not out.exists():
            return self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "ffmpeg failed: " + (r.stderr or "").strip()[-400:]})
        shutil.rmtree(jobdir, ignore_errors=True)
        print("%s rendered %s (%d frames, %.1fs encode)" % (time.strftime("%Y-%m-%d %H:%M:%S"), out.name, n, time.time() - t0), flush=True)
        return self.send_json(HTTPStatus.OK, {"ok": True, "name": name, "url": "media/renders/" + out.name, "size": out.stat().st_size, "path": str(out), "frames": n})

    def tts(self):
        opts = self.body_json(65536)
        text = str(opts.get("text") or "").strip()[:800]
        voice = str(opts.get("voice") or "")
        if not text or not voice:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Need a line of text and a voice"})
        if voice not in {v["id"] for v in all_voices()}:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "That voice is not available on this studio"})
        try:
            pitch = max(-12.0, min(12.0, float(opts.get("pitch") or 0)))
            rate = max(0.5, min(2.0, float(opts.get("rate") or 1)))
        except (TypeError, ValueError):
            pitch, rate = 0.0, 1.0
        style = str(opts.get("style") or "")[:20]
        lang = str(opts.get("lang") or "")[:5]
        key = hashlib.sha1(json.dumps([voice, text, pitch, rate, style if voice.startswith("openai:") else ""]).encode("utf-8")).hexdigest()[:14]
        dest = ASSETS / ("tts_%s.wav" % key)
        if not dest.exists():
            ASSETS.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part.wav")
            try:
                synth(voice, text, pitch, rate, tmp, style, lang)
                os.replace(tmp, dest)
            except Exception as e:
                tmp.unlink(missing_ok=True)
                return self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
        return self.send_json(HTTPStatus.OK, {"ok": True, "asset": dest.name, "duration": round(wav_duration(dest), 3), "url": "media/assets/" + dest.name})

    def do_DELETE(self):
        parts, _ = self.route()
        if parts and len(parts) == 2 and parts[0] == "render" and JOB_RE.match(parts[1]):
            shutil.rmtree(RENDERS / parts[1], ignore_errors=True)
            return self.send_json(HTTPStatus.OK, {"ok": True})
        if parts and len(parts) == 3 and parts[:2] == ["voices", "profiles"]:
            return self.guard(lambda: (delete_clone(parts[2]), {"ok": True})[1])
        if not parts or len(parts) != 2 or parts[0] != "scenes":
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        p = self.scene_path(parts[1])
        if not p or not p.exists():
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "No scene with that name"})
        p.unlink()
        return self.send_json(HTTPStatus.OK, {"ok": True})


def main():
    ap = argparse.ArgumentParser(description="MayaToon studio server")
    ap.add_argument("--host", default=os.environ.get("MAYATOON_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MAYATOON_PORT", "47219")))
    a = ap.parse_args()
    for d in (SCENES, ASSETS, RENDERS, VOICES, TMP, STORIES):
        d.mkdir(parents=True, exist_ok=True)
    for stale in RENDERS.glob("job_*"):
        if stale.is_dir() and time.time() - stale.stat().st_mtime > 86400:
            shutil.rmtree(stale, ignore_errors=True)
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    print("MayaToon %s on http://%s:%d  (data: %s, ffmpeg: %s)" % (VERSION, a.host, a.port, DATA, find_ffmpeg() or "not found"), flush=True)
    threading.Thread(target=all_voices, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
