#!/usr/bin/env python3
"""Copy a week's reels into the shared Google Drive folder for Nick.
usage:  python3 send_to_drive.py "<local reels folder>" --sub "<subfolder name>" [--into "shop talk"] [--dry]
- Finds the Drive folder named --into (yours or shared with you), shows what's in it, and puts the files in a
  subfolder --sub (created if missing). Uploads .mp4 + .txt. Files already there (same name) are skipped.
- First run opens a browser to sign in: pick the Google account that has the "shop talk" folder.
  Login is saved to token_drive.json next to this script (separate from the YouTube login)."""
import os, sys, time, socket, ssl, argparse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER = 'application/vnd.google-apps.folder'

def auth():
    tok = os.path.join(HERE, 'token_drive.json'); creds = None
    if os.path.exists(tok): creds = Credentials.from_authorized_user_file(tok, SCOPES)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
            else: raise RefreshError('login')
        except RefreshError:
            creds = InstalledAppFlow.from_client_secrets_file(os.path.join(HERE, 'client_secret.json'), SCOPES).run_local_server(port=0)
        open(tok, 'w').write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def q(s): return s.replace("\\", "\\\\").replace("'", "\\'")
def ls(d, query):
    out, pt = [], None
    while True:
        r = d.files().list(q=query, fields='nextPageToken, files(id,name,mimeType,modifiedTime,owners(emailAddress))', pageSize=200,
                           pageToken=pt, supportsAllDrives=True, includeItemsFromAllDrives=True, corpora='allDrives').execute()
        out += r.get('files', []); pt = r.get('nextPageToken')
        if not pt: return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('local'); ap.add_argument('--sub', required=True)
    ap.add_argument('--into', default='shop talk'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    files = sorted(f for f in os.listdir(a.local) if f.lower().endswith(('.mp4', '.txt')) and not f.startswith('._'))
    if not files: sys.exit(f'!! no .mp4/.txt files in {a.local}')
    d = auth()
    me = d.about().get(fields='user(emailAddress)').execute()['user']['emailAddress']; print('Signed in as', me)
    hits = ls(d, f"name = '{q(a.into)}' and mimeType = '{FOLDER}' and trashed = false")
    if not hits: sys.exit(f'!! no folder named "{a.into}" visible to {me}. Wrong account? Delete token_drive.json and run again.')
    if len(hits) > 1:
        for i, h in enumerate(hits): print(f'  [{i}] {h["name"]}  owner {h.get("owners", [{}])[0].get("emailAddress", "?")}  modified {h["modifiedTime"][:10]}')
        top = hits[int(input('Which one? '))]
    else: top = hits[0]
    subs = sorted(ls(d, f"'{top['id']}' in parents and mimeType = '{FOLDER}' and trashed = false"), key=lambda x: x['name'])
    print(f'"{top["name"]}" has {len(subs)} folders, last few:', ', '.join(s['name'] for s in subs[-5:]) or '(none)')
    sub = next((s for s in subs if s['name'] == a.sub), None)
    print(f'-> files go into "{top["name"]}/{a.sub}"' + ('' if sub else ' (new folder)'))
    for f in files: print('   ', f)
    if a.dry: print('dry run only — nothing uploaded'); return
    if input('Go? [y/N] ').strip().lower() != 'y': sys.exit('Stopped — nothing uploaded.')
    if not sub: sub = d.files().create(body=dict(name=a.sub, mimeType=FOLDER, parents=[top['id']]), fields='id', supportsAllDrives=True).execute()
    have = {x['name'] for x in ls(d, f"'{sub['id']}' in parents and trashed = false")}
    for f in files:
        if f in have: print('skip (already there):', f); continue
        mt = 'video/mp4' if f.lower().endswith('.mp4') else 'text/plain'
        req = d.files().create(body=dict(name=f, parents=[sub['id']]), supportsAllDrives=True, fields='id',
                               media_body=MediaFileUpload(os.path.join(a.local, f), mimetype=mt, chunksize=4 * 1024 * 1024, resumable=True))
        resp, fails = None, 0
        while resp is None:
            try:
                st, resp = req.next_chunk(num_retries=5); fails = 0
                if st: print(f'   {f}  {int(st.progress() * 100)}%', end='\r', flush=True)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.timeout, ssl.SSLError, OSError) as e:
                fails += 1
                if fails > 8: sys.exit(f'!! upload kept dropping ({e}). Run the same command again; finished files are skipped.')
                w = min(60, 2 ** fails); print(f'   connection dropped, retrying in {w}s...'); time.sleep(w)
        print(f'   done  {f}' + ' ' * 10)
    print(f'all done -> https://drive.google.com/drive/folders/{sub["id"]}')

if __name__ == '__main__': main()
