"""`palefire beats <shoot folder>`: beats, downbeats and a loudness map for every track in <shoot>/music.

Writes <work>/music/<track>.beats.json, which `palefire cut` uses to land cuts on the beat and the payoff on a break.
Beat This and PyTorch live in the system Python (python.org 3.15 or 3.14), not the repo venv, so this runs
beats_worker.py under the first of python3.15 / python3.14 on PATH. Override it with PALEFIRE_BEAT_PYTHON.
Existing beat files are kept unless --force.
"""
import os
import shutil
import subprocess
from pathlib import Path

from nljbs import media

from .transcribe import work_dir

BEAT_PY = os.environ.get("PALEFIRE_BEAT_PYTHON") or next(
    (py for py in ("python3.15", "python3.14") if shutil.which(py)), "python3.15")


def run(folder, work=None, force=False):
    music = Path(folder) / "music"
    if not music.is_dir():
        raise SystemExit(f"{music}: no music folder (put the Epidemic tracks there)")
    out = work_dir(folder, work) / "music"
    ffmpeg = shutil.which(media.FFMPEG) or media.FFMPEG
    cmd = [BEAT_PY, str(Path(__file__).with_name("beats_worker.py")), ffmpeg, str(music), str(out)]
    r = subprocess.run(cmd + (["--force"] if force else []))
    if r.returncode:
        raise SystemExit(f"Beat This failed under {BEAT_PY}. Install it there: "
                         f'{BEAT_PY} -m pip install torch "git+https://github.com/CPJKU/beat_this.git"')
