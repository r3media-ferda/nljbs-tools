#!/usr/bin/env python3
"""Upload a full Shop Talk episode to YouTube (title, description, tags, thumbnail, publish time).
usage: python3 upload_episode.py "<video.mp4>" --title "..." --desc "<description.txt>" [--thumb "<thumbnail.png>"]
                                 [--tags "a|b|c"] [--when now | "YYYY-MM-DD HH:MM"] [--dry]
--when now (default) = public as soon as YouTube finishes processing. A date = uploads private, goes public then (America/New_York).
Uses the same login as post_shorts (token.json next to this script)."""
import os, sys, time, socket, ssl, argparse, datetime
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
TZ = ZoneInfo('America/New_York')

def auth():
    tok = os.path.join(HERE, 'token.json'); creds = None
    if os.path.exists(tok): creds = Credentials.from_authorized_user_file(tok, SCOPES)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
            else: raise RefreshError('login')
        except RefreshError:
            creds = InstalledAppFlow.from_client_secrets_file(os.path.join(HERE, 'client_secret.json'), SCOPES).run_local_server(port=0)
        open(tok, 'w').write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def chunks(req, label):
    resp, fails = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk(num_retries=5); fails = 0
            if st: print(f'   {label} {st.progress() * 100:5.1f}%', end='\r', flush=True)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.timeout, ssl.SSLError, OSError) as e:
            fails += 1
            if fails > 12: sys.exit(f'!! upload kept dropping ({e}). Run the same command again to start over.')
            w = min(60, 2 ** fails); print(f'\n   connection dropped ({e.__class__.__name__}), retrying in {w}s...'); time.sleep(w)
    print(); return resp

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--title', required=True); ap.add_argument('--desc', required=True)
    ap.add_argument('--thumb'); ap.add_argument('--tags', default=''); ap.add_argument('--when', default='now'); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    for p in [a.video, a.desc] + ([a.thumb] if a.thumb else []):
        if not os.path.exists(p): sys.exit(f'!! not found: {p}')
    desc = open(a.desc, encoding='utf-8').read().strip()
    if len(a.title) > 100: sys.exit(f'!! title is {len(a.title)} chars, YouTube max is 100')
    status = dict(selfDeclaredMadeForKids=False)
    if a.when == 'now': status['privacyStatus'] = 'public'; when_txt = 'PUBLIC as soon as it finishes processing'
    else:
        t = datetime.datetime.strptime(a.when, '%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        if t <= datetime.datetime.now(TZ) + datetime.timedelta(minutes=15): sys.exit('!! --when must be at least 15 minutes from now')
        status.update(privacyStatus='private', publishAt=t.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')); when_txt = f'private, goes public {t:%a %b %d %I:%M %p}'
    gb = os.path.getsize(a.video) / 1e9
    print(f'Video:  {a.video}  ({gb:.2f} GB)\nTitle:  {a.title}\nWhen:   {when_txt}\nThumb:  {a.thumb or "(none)"}\n--- description ---\n{desc}\n-------------------')
    if a.dry: print('dry run only — nothing uploaded'); return
    yt = auth()
    ch = yt.channels().list(part='snippet', mine=True).execute()['items'][0]['snippet']['title']
    if input(f'Upload to the channel "{ch}"? [y/N] ').strip().lower() != 'y': sys.exit('Stopped — nothing uploaded.')
    body = dict(snippet=dict(title=a.title, description=desc, tags=[t.strip() for t in a.tags.split('|') if t.strip()], categoryId='24',
                             defaultLanguage='en', defaultAudioLanguage='en'), status=status)
    req = yt.videos().insert(part='snippet,status', body=body,
                             media_body=MediaFileUpload(a.video, mimetype='video/mp4', chunksize=16 * 1024 * 1024, resumable=True))
    print(f'Uploading {gb:.2f} GB — leave Terminal open (roughly 5–20 min depending on your upload speed)')
    vid = chunks(req, 'video')['id']; print(f'   uploaded  https://youtu.be/{vid}')
    if a.thumb:
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(a.thumb, mimetype='image/png' if a.thumb.lower().endswith('png') else 'image/jpeg')).execute()
            print('   thumbnail set')
        except Exception as e:
            print(f'!! thumbnail failed ({e}). Set it in YouTube Studio → Content → the video → Thumbnail.')
    print(f'done. Studio: https://studio.youtube.com/video/{vid}/edit')

if __name__ == '__main__': main()
