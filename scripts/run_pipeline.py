#!/usr/bin/env python3
import subprocess, shlex, os
from pathlib import Path

def run(cmd):
    print(f"$ {cmd}")
    subprocess.check_call(shlex.split(cmd))

root = Path(__file__).resolve().parent.parent
os.chdir(root)

run("python -m lyripop.pipeline --fetch_charts --start 1980 --end 2024")
run("python -m lyripop.pipeline --fetch_lyrics --start 1980 --end 2024")
run("python -m lyripop.pipeline --compute      --start 1980 --end 2024")
