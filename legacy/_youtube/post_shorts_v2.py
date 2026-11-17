#!/usr/bin/env python3
"""Bulk-schedule YouTube Shorts from a CSV.  usage:  python3 post_shorts.py "<path to schedule csv>" [--dry]
CSV columns: file,title,description,tags,publish_local   (publish_local = "YYYY-MM-DD HH:MM", America/New_York)
- File paths are relative to the CSV's folder.
- Uploads as private + scheduled (YouTube flips it public at publish time).
- Already-uploaded rows are logged in <csv>.done and skipped on re-runs, so it's safe to run again after a failure.
First run opens a browser window to log in to the NLJBS YouTube channel; the login is saved to token.json next to this script.
To switch accounts/channels: delete token.json and run again."""
import csv, os, sys, json, datetime, time, socket, ssl
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

def login(tok):
    cs = os.path.join(HERE, 'client_secret.json')
    if not os.path.exists(cs): sys.exit(f'!! client_secret.json not found in {HERE} — download it from Google Cloud (Clients > Desktop app) and put it here.')
    creds = InstalledAppFlow.from_client_secrets_file(cs, SCOPES).run_local_server(port=0)
    open(tok, 'w').write(creds.to_json()); return creds

def auth():
    tok = os.path.join(HERE, 'token.json'); creds = None
    if os.path.exists(tok): creds = Credentials.from_authorized_user_file(tok, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(Request()); open(tok, 'w').write(creds.to_json())
            except RefreshError: print('Login expired (normal every ~7 days while the app is in Testing) — logging in again.'); creds = login(tok)
        else: creds = login(tok)
    return build('youtube', 'v3', credentials=creds)

def main():
    path = sys.argv[1]; dry = '--dry' in sys.argv; base = os.path.dirname(os.path.abspath(path))
    done_path = path + '.done'
    done = set(l.split(',')[0] for l in open(done_path)) if os.path.exists(done_path) else set()
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8')))
    yt = None if dry else auth()
    if yt:
        ch = yt.channels().list(part='snippet', mine=True).execute()['items'][0]['snippet']['title']
        if input(f'Upload {len(rows) - len(done & set(r["file"] for r in rows))} Shorts to the channel "{ch}"? [y/N] ').strip().lower() != 'y':
            sys.exit('Stopped — nothing uploaded. Wrong channel? Delete token.json and run again to pick the NLJBS channel.')
    now = datetime.datetime.now(TZ)
    for r in rows:
        f = os.path.join(base, r['file'])
        if r['file'] in done: print('skip (already uploaded):', r['file']); continue
        when = datetime.datetime.strptime(r['publish_local'], '%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        if when <= now + datetime.timedelta(minutes=15): print('!! publish time is in the past / too soon, fix the CSV:', r['file']); continue
        if not os.path.exists(f): print('!! missing file:', f); continue
        utc = when.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        print(f"{r['file']}  ->  {when:%a %b %d %I:%M %p}  ({utc})  {r['title']}")
        if dry: continue
        body = dict(snippet=dict(title=r['title'][:100], description=r['description'].replace('\\n', '\n'),
                                 tags=[t.strip() for t in r['tags'].split('|') if t.strip()], categoryId='24'),
                    status=dict(privacyStatus='private', publishAt=utc, selfDeclaredMadeForKids=False))
        req = yt.videos().insert(part='snippet,status', body=body, media_body=MediaFileUpload(f, chunksize=4 * 1024 * 1024, resumable=True))
        resp = None; fails = 0
        while resp is None:
            try:
                st, resp = req.next_chunk(num_retries=5)
                fails = 0
                if st: print(f'   {int(st.progress() * 100)}%', end='\r', flush=True)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.timeout, ssl.SSLError, OSError) as e:
                fails += 1
                if fails > 8: sys.exit(f'!! upload kept dropping ({e}). Nothing is logged for this file, so just run the same command again.')
                wait = min(60, 2 ** fails); print(f'   connection dropped ({e.__class__.__name__}), retrying in {wait}s...'); time.sleep(wait)
        vid = resp['id']; print(f'   done  https://youtube.com/shorts/{vid}')
        open(done_path, 'a').write(f"{r['file']},{vid},{utc}\n")
    print('all done' if not dry else 'dry run only — nothing uploaded')

if __name__ == '__main__': main()
