#!/bin/bash
# MayaToon control: status|start|stop|restart|logs|open|make|story|cultures
set -uo pipefail
DIR="$(cd "$(dirname "$(readlink "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")")" && pwd)"
LABEL="com.manish.mayatoon"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:5' "$PLIST" 2>/dev/null || echo "${MAYATOON_PORT:-47219}")"
URL="http://localhost:$PORT"
enc(){ python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }
usage(){ cat <<U
usage: ctl.sh status | start | stop | restart | logs | open | cultures
       ctl.sh make  "story idea" [--culture nepal] [--lang ne] [--length short|medium|long]
                    [--format 16:9|9:16|1:1] [--cast humans|animals|mixed] [--engine auto|claude|openai|ollama|offline]
                    [--subs both|native|en|off] [--render] [--no-voice]
       ctl.sh story "story idea" [--culture ...]      prints the story JSON only
U
}
cmd="${1:-status}"; shift || true
case "$cmd" in
  start)   launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "started on port $PORT" ;;
  stop)    launchctl bootout "gui/$(id -u)/$LABEL" && echo "stopped" ;;
  restart) launchctl kickstart -k "gui/$(id -u)/$LABEL" && echo "restarted on port $PORT" ;;
  logs)    tail -n 60 -f "$DIR/logs/server.log" ;;
  open)    open "$URL" ;;
  status)  if curl -fsS "$URL/api/health"; then echo; echo "running: $URL"; else echo "not answering on port $PORT"; exit 1; fi ;;
  cultures) curl -fsS "$URL/api/story/meta" | python3 -c 'import sys,json; d=json.load(sys.stdin); [print("%-16s %s" % (k, v["label"])) for k, v in d["cultures"].items()]; print("engines:", {k: v for k, v in d["engines"].items() if k != "ollama_models"})' ;;
  make|story)
    [ $# -ge 1 ] || { usage; exit 2; }
    PROMPT="$1"; shift
    CULTURE=nepal; LANGC=""; LEN=short; FMT="16:9"; CAST=""; ENG=auto; SUBS=both; RENDER=0; VOICE=1
    while [ $# -gt 0 ]; do case "$1" in
      --culture) CULTURE="$2"; shift 2 ;; --lang) LANGC="$2"; shift 2 ;; --length) LEN="$2"; shift 2 ;;
      --format) FMT="$2"; shift 2 ;; --cast) CAST="$2"; shift 2 ;; --engine) ENG="$2"; shift 2 ;; --subs) SUBS="$2"; shift 2 ;;
      --render) RENDER=1; shift ;; --no-voice) VOICE=0; shift ;; *) echo "unknown option $1"; usage; exit 2 ;; esac; done
    if [ "$cmd" = story ]; then
      python3 - "$URL" "$PROMPT" "$CULTURE" "$LANGC" "$LEN" "$CAST" "$ENG" <<'PY'
import json, sys, urllib.request
u, prompt, culture, lang, length, cast, eng = sys.argv[1:]
body = {"prompt": prompt, "culture": culture, "length": length, "engine": eng, "cast_type": cast or "auto"}
if lang: body["language"] = lang
r = urllib.request.urlopen(urllib.request.Request(u + "/api/story", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600)
print(json.dumps(json.load(r)["story"], ensure_ascii=False, indent=1))
PY
    else
      H="make=1&prompt=$(enc "$PROMPT")&culture=$CULTURE&length=$LEN&format=$(enc "$FMT")&engine=$ENG&subs=$SUBS&render=$RENDER&voice=$VOICE"
      [ -n "$LANGC" ] && H="$H&lang=$LANGC"; [ -n "$CAST" ] && H="$H&cast=$CAST"
      open "$URL/#$H" 2>/dev/null || xdg-open "$URL/#$H"
      echo "Opened the Story director: it writes, builds, voices and cuts${RENDER:+ the movie}. Movies land in $DIR/data/renders"
    fi ;;
  *) usage; exit 2 ;;
esac
