#!/bin/bash
# MayaToon installer: copies the studio to ~/Sites/mayatoon, sets up voices, starts it as a login service,
# commits the build and pushes to your public GitHub repo "mayatoon". Safe to re-run for every update.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${MAYATOON_DEST:-$HOME/Sites/mayatoon}"
PORT="${MAYATOON_PORT:-47219}"
HOST="${MAYATOON_HOST:-127.0.0.1}"
LABEL="com.manish.mayatoon"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
OLD="${MAYATOON_MIGRATE_FROM:-$HOME/Sites/minimaya}"
VERSION="$(cat "$SRC/VERSION")"; BUILD="$(cat "$SRC/BUILD")"

say(){ printf '\033[1;33m>\033[0m %s\n' "$*"; }
ok(){ printf '\033[1;32m✓\033[0m %s\n' "$*"; }
fail(){ printf '\033[1;31mx %s\033[0m\n' "$*" >&2; exit 1; }

PY="$(command -v python3 || true)"
[ -n "$PY" ] || fail "python3 not found. Run: xcode-select --install   (or: brew install python)"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || fail "Python 3.8 or newer is required"
PY="$("$PY" -c 'import sys; print(sys.executable)')"
ok "Python: $PY"

BREW="$(command -v brew || true)"
for c in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -z "$BREW" ] && [ -x "$c" ] && BREW="$c"; done
FF="$(command -v ffmpeg || true)"
for c in /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do [ -z "$FF" ] && [ -x "$c" ] && FF="$c"; done
if [ -z "$FF" ] && [ "${MAYATOON_NO_FFMPEG:-0}" != "1" ]; then
  if [ -n "$BREW" ]; then
    say "Installing ffmpeg with Homebrew (MP4 movies, recordings, voices; one time)"
    "$BREW" install ffmpeg >/dev/null && FF="$(dirname "$BREW")/ffmpeg" || say "Homebrew could not install ffmpeg; MP4 export and recording cleanup stay off"
  else
    say "No Homebrew, so no ffmpeg: install Homebrew, then brew install ffmpeg"
  fi
fi
[ -n "$FF" ] && ok "ffmpeg: $FF"

say "Installing MayaToon $VERSION (build $BUILD) into $DEST"
mkdir -p "$DEST/data/scenes" "$DEST/data/assets" "$DEST/data/renders" "$DEST/data/voices" "$DEST/data/stories" "$DEST/logs" "$DEST/releases"
if [ -f "$DEST/VERSION" ] && [ -f "$DEST/index.html" ]; then
  PREV="$(cat "$DEST/VERSION")-$(cat "$DEST/BUILD" 2>/dev/null || echo old)"
  tar -czf "$DEST/releases/backup-$PREV.tgz" -C "$DEST" --exclude ./data --exclude ./logs --exclude ./releases --exclude ./.git --exclude ./.venv . 2>/dev/null || true
  ls -1t "$DEST"/releases/backup-*.tgz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
  ok "Backed up previous build $PREV to releases/"
fi
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude=/data --exclude=/logs --exclude=/releases --exclude=/.git --exclude=/.venv --exclude=__pycache__ "$SRC/" "$DEST/"
else
  (cd "$SRC" && tar -cf - --exclude ./data --exclude ./__pycache__ .) | (cd "$DEST" && tar -xf -)
fi
chmod +x "$DEST"/*.sh "$DEST/server.py"
ok "Files copied (your scenes, voices, keys and movies in data/ were left alone)"

# one-time copy of Mini Maya scenes, media and voices (the old folder is not changed)
if [ "${MAYATOON_NO_MIGRATE:-0}" != "1" ] && [ -d "$OLD/data" ] && [ ! -f "$DEST/data/.migrated" ]; then
  for d in scenes assets voices; do [ -d "$OLD/data/$d" ] && (cd "$OLD/data/$d" && for f in *; do [ -e "$f" ] && [ ! -e "$DEST/data/$d/$f" ] && cp -R "$f" "$DEST/data/$d/"; done; true); done
  touch "$DEST/data/.migrated"
  ok "Copied Mini Maya scenes, media and voices from $OLD/data (Mini Maya itself is untouched)"
fi

# keys from this shell go into data/config.json (only if not already set there)
"$PY" - "$DEST/data/config.json" <<'PYK' || true
import json, os, sys
p = sys.argv[1]
env = {"anthropic_key": "ANTHROPIC_API_KEY", "openai_key": "OPENAI_API_KEY", "eleven_key": "ELEVENLABS_API_KEY",
       "azure_key": "AZURE_SPEECH_KEY", "azure_region": "AZURE_SPEECH_REGION", "google_key": "GOOGLE_TTS_API_KEY", "meshy_key": "MESHY_API_KEY"}
try: d = json.load(open(p))
except Exception: d = {}
got = [k for k, e in env.items() if os.environ.get(e) and not d.get(k)]
for k in got: d[k] = os.environ[env[k]]
if got:
    open(p, "w").write(json.dumps(d, indent=2)); os.chmod(p, 0o600)
    print("\033[1;32m✓\033[0m Saved from your shell: " + ", ".join(env[k] for k in got))
PYK

if [ "${MAYATOON_NO_TTS:-0}" != "1" ]; then
  say "Setting up offline voices (Piper; MAYATOON_NO_TTS=1 skips)"
  VPY="$DEST/.venv/bin/python"
  [ -x "$VPY" ] || "$PY" -m venv "$DEST/.venv" >/dev/null 2>&1 || true
  if [ -x "$VPY" ]; then
    if ! "$VPY" -c 'import piper' >/dev/null 2>&1; then
      "$VPY" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
      "$VPY" -m pip install -q piper-tts >/dev/null 2>&1 && ok "Installed piper-tts" || say "pip could not install piper-tts; Mac and cloud voices still work"
    fi
    "$PY" "$DEST/get_voices.py" "$DEST/data/voices" || true
  fi
  if [ -n "$BREW" ] && ! command -v espeak-ng >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/espeak-ng ] && [ "${MAYATOON_NO_ESPEAK:-0}" != "1" ]; then
    say "Installing espeak-ng as a last-resort voice for Telugu and Tamil (MAYATOON_NO_ESPEAK=1 skips)"
    "$BREW" install espeak-ng >/dev/null 2>&1 && ok "espeak-ng installed" || true
  fi
fi

if [ "$(uname)" = "Darwin" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  sleep 1
  PIDS="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then ps -o pid=,command= -p $PIDS >&2 || true; fail "Port $PORT is in use by the process above. Re-run with MAYATOON_PORT=<another 5-digit port>."; fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DEST/server.py</string>
    <string>--host</string><string>$HOST</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$DEST</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DEST/logs/server.log</string>
  <key>StandardErrorPath</key><string>$DEST/logs/server.log</string>
</dict>
</plist>
PL
  for i in 1 2 3 4 5; do launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null && break; sleep 1; [ "$i" = 5 ] && fail "launchctl could not load $PLIST"; done
  ok "Background service $LABEL loaded (starts at login, restarts if it stops)"
  if [ "${MAYATOON_RETIRE_MINIMAYA:-0}" = "1" ]; then
    launchctl bootout "gui/$(id -u)/com.manish.minimaya" >/dev/null 2>&1 && rm -f "$HOME/Library/LaunchAgents/com.manish.minimaya.plist" && ok "Stopped the old Mini Maya service"
  fi
else
  say "Not macOS: starting in the background with nohup"
  pkill -f "[s]erver.py --host $HOST --port $PORT" 2>/dev/null || true
  nohup "$PY" "$DEST/server.py" --host "$HOST" --port "$PORT" >> "$DEST/logs/server.log" 2>&1 &
fi

URL="http://localhost:$PORT"
for i in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.3
  [ "$i" = 40 ] && { tail -n 20 "$DEST/logs/server.log" >&2 || true; fail "Server did not answer on port $PORT"; }
done
ok "Server is up: $URL"

if command -v git >/dev/null 2>&1; then
  cd "$DEST"
  [ -d .git ] || git init -q -b main
  git add -A
  if git commit -qm "MayaToon $VERSION (build $BUILD)" >/dev/null 2>&1; then git tag -f "build-$BUILD" >/dev/null 2>&1 || true; ok "Committed build $BUILD"; else say "Nothing new to commit (or git user.name/email not set)"; fi
  if [ "${MAYATOON_NO_PUSH:-0}" != "1" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if ! git remote get-url origin >/dev/null 2>&1; then
      if gh repo view mayatoon >/dev/null 2>&1; then git remote add origin "$(gh repo view mayatoon --json url -q .url).git"
      else gh repo create mayatoon --public --source . --remote origin --description "MayaToon: culture-based 3D cartoon stories from a prompt, in the browser" >/dev/null && ok "Created public GitHub repo mayatoon"; fi
    fi
    git push -q -u origin main --tags 2>/dev/null && ok "Pushed to $(git remote get-url origin)" || say "GitHub push failed; run 'git push -u origin main --tags' in $DEST to see why"
  else
    say "Skipped GitHub push (needs gh logged in; MAYATOON_NO_PUSH=1 silences)"
  fi
fi

ln -sf "$DEST/ctl.sh" "$DEST/mayatoon" 2>/dev/null || true
echo
ok "MayaToon $VERSION is running at $URL"
echo "   Folder:   $DEST"
echo "   Movies:   $DEST/data/renders"
echo "   Control:  $DEST/ctl.sh status|restart|stop|start|logs|open|make|story"
echo "   Try:      $DEST/ctl.sh make \"Hajurama teaches her grandson to make sel roti\" --culture nepal --render"
[ "$(uname)" = "Darwin" ] && [ "${MAYATOON_NO_OPEN:-0}" != "1" ] && open "$URL" || true
