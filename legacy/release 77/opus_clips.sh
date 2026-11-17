#!/bin/bash
# opus_clips.sh — send a Shop Talk episode to OpusClip and pull the finished clips
# into a folder (point it at a Google Drive for Desktop folder and Nick gets them).
#
# One-time setup (Terminal): store your key + org ID in the macOS Keychain.
#   security add-generic-password -a "$USER" -s opus_api -w     # paste API key at the prompt
#   security add-generic-password -a "$USER" -s opus_org -w     # paste org ID at the prompt
#
# Usage:
#   bash opus_clips.sh "<episode MP4 on your Mac  OR  a YouTube/Vimeo link>" "<output folder>" "<title>"
# Example (local file — easiest: drag the MP4 into Terminal to paste its path):
#   bash opus_clips.sh "/Volumes/NLJBS Drive/EXPORTS/RELEASE 77.mp4" "$HOME/Desktop/OPUS CLIPS/R77" "Shop Talk R77"
#
# NOTE: Opus's API rejects Google Drive links. Use the local file or a YouTube link.
set -euo pipefail

KEY=$(security find-generic-password -s opus_api -w)
ORG=$(security find-generic-password -s opus_org -w 2>/dev/null || echo "")
URL="${1:?Pass the public video link as the first argument}"
OUT="${2:-$HOME/Desktop/OPUS CLIPS/$(date +%Y-%m-%d)}"
TITLE="${3:-Shop Talk}"
API="https://api.opus.pro/api"
mkdir -p "$OUT"

# tiny JSON helper (JavaScript for Automation ships with every Mac — no installs needed)
jget() { osascript -l JavaScript -e 'function run(a){var d=JSON.parse(a[0]);var ks=a[1].split(",");
  function f(o){if(o&&typeof o==="object"){for(var k of ks){if(o[k]!==undefined&&typeof o[k]!=="object")return String(o[k]);}
  for(var k in o){var r=f(o[k]);if(r)return r;}}return "";} return f(d);}' "$1" "$2"; }

SRC="$URL"
if [ -f "$URL" ]; then
  # ---- local file: Opus direct upload (Drive links are NOT accepted by the API) ----
  echo "→ Getting an upload slot from Opus…"
  UL=$(curl -sS -X POST "$API/upload-links" -H "Accept: application/json" -H "Content-Type: application/json" \
       -H "Authorization: Bearer $KEY" -d '{"video":{"usecase":"LocalUpload"}}')
  echo "$UL" > "$OUT/opus_upload_link.json"
  GCS=$(jget "$UL" "url"); UPID=$(jget "$UL" "uploadId")
  if [ -z "$GCS" ] || [ -z "$UPID" ]; then echo "✗ No upload link back. See $OUT/opus_upload_link.json"; exit 1; fi
  LOC=$(curl -sS -X POST "$GCS" -H "x-goog-resumable: start" -H "Content-Length: 0" -D - -o /dev/null \
        | grep -i '^location:' | sed 's/^[Ll]ocation: *//' | tr -d '\r')
  if [ -z "$LOC" ]; then echo "✗ Upload session didn't start."; exit 1; fi
  echo "→ Uploading $(basename "$URL") ($(du -h "$URL" | cut -f1)) — progress bar below…"
  curl -X PUT -H "Content-Type: application/octet-stream" --upload-file "$URL" "$LOC" --progress-bar -o "$OUT/opus_upload_result.txt"
  echo "✓ Upload done."
  SRC="$UPID"
fi

echo "→ Creating Opus project for: $TITLE"
# Clip brief (Opus "ClipAnything" mode). Edit the prompt here if the show format changes.
PROMPT="Shop Talk is a tattoo podcast. 1) The opening banter before they start looking at tattoos is always the funniest part: clip the best stories and roasts from the first several minutes. 2) Every time they pull up a tattoo on screen and react to it or break it down, make 1-2 clips for that tattoo and keep the tattoo visible on screen as much as possible."
BODY=$(osascript -l JavaScript -e 'function run(a){return JSON.stringify({videoUrl:a[0],uploadedVideoAttr:{title:a[1]},importPref:{sourceLang:"en"},curationPref:{model:"ClipAnything",customPrompt:a[2],clipDurations:[[15,60]]}});}' "$SRC" "$TITLE" "$PROMPT")
RESP=$(curl -sS -X POST "$API/clip-projects" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$BODY")
echo "$RESP" > "$OUT/opus_project.json"
PID=$(jget "$RESP" "projectId,id")
if [ -z "$PID" ]; then echo "✗ No project ID back from Opus. Response saved to $OUT/opus_project.json"; exit 1; fi
echo "✓ Project $PID created. Waiting for clips (checks every 2 min, up to 4 h)…"

HDRS=(-H "Authorization: Bearer $KEY")
[ -n "$ORG" ] && HDRS+=(-H "x-opus-org-id: $ORG")
for i in $(seq 1 120); do
  sleep 120
  CLIPS=$(curl -sS "${HDRS[@]}" "$API/exportable-clips?q=findByProjectId&projectId=$PID" || true)
  # one line per clip: rank|start-sec|title|best url (full render if Opus made one, else preview)
  LIST=$(osascript -l JavaScript -e 'function run(a){var d;try{d=JSON.parse(a[0])}catch(e){return ""}
    var c=(d.data||[]);return c.map(function(x){var t=(x.timeRanges&&x.timeRanges[0])?Math.round(x.timeRanges[0][0]/1000):0;
    var u=x.uriForExport||x.uriForPreview||"";var tl=(x.title||"clip").replace(/[^A-Za-z0-9 ]/g,"").trim().replace(/ +/g,"-").slice(0,50);
    return [x.rank||0,t,tl,u,x.uriForExport?"FULL":"PREVIEW"].join("|")}).join("\n")}' "$CLIPS" 2>/dev/null || true)
  if [ -n "$LIST" ]; then
    echo "$CLIPS" > "$OUT/opus_clips.json"
    n=0
    while IFS='|' read -r rank st tl u q; do
      [ -z "$u" ] && continue
      n=$((n+1)); f=$(printf '%s/rank%02d_%02dm%02ds_%s%s.mp4' "$OUT" "$rank" $((st/60)) $((st%60)) "$tl" "$([ "$q" = PREVIEW ] && echo _PREVIEW-export-in-opus)")
      curl -sSL "$u" -o "$f" && echo "  ↓ $(basename "$f")"
    done <<< "$LIST"
    echo "✓ $n clips saved to: $OUT (titles/descriptions/transcripts in opus_clips.json)"
    exit 0
  fi
  echo "  …still processing ($((i*2)) min)"
done
echo "✗ Timed out. Check the project in the Opus dashboard: $PID"; exit 1
