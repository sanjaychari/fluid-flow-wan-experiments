#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def command_output(argv: list[str]) -> str:
    try:
        return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return ""


def git_head(path: Path) -> str:
    return command_output(["git", "-C", str(path), "rev-parse", "HEAD"])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()



def public_text(value: str, *, codes_root: Path, ross_root: Path) -> str:
    replacements = [
        (str(REPO_ROOT.resolve()), "/workspace/fluid-flow-wan-experiments"),
        (str(codes_root.resolve()), "/workspace/codes"),
        (str(ross_root.resolve()), "/workspace/ross"),
    ]
    out = value
    for source, target in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
        out = out.replace(source, target)
    return out

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--codes-root", type=Path, required=True)
    p.add_argument("--ross-root", type=Path, required=True)
    p.add_argument("--command", required=True)
    p.add_argument("--sync", type=int, required=True)
    p.add_argument("--ranks", type=int, required=True)
    p.add_argument("--mode", required=True)
    p.add_argument("--wall-clock-sec", type=float, required=True)
    p.add_argument("--return-code", type=int, required=True)
    p.add_argument("--input", action="append", default=[])
    p.add_argument("--seed", default="")
    p.add_argument("--interval-seconds", default="")
    p.add_argument("--note", action="append", default=[])
    args = p.parse_args()

    public_command = public_text(
        args.command, codes_root=args.codes_root, ross_root=args.ross_root
    )

    inputs = {}
    for value in args.input:
        path = Path(value)
        public_path = public_text(
            str(path), codes_root=args.codes_root, ross_root=args.ross_root
        )
        inputs[public_path] = sha256(path) if path.is_file() else None

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "codes_commit": git_head(args.codes_root),
        "ross_commit": git_head(args.ross_root),
        "host": "anonymous-host",
        "platform": platform.platform(),
        "compiler": command_output(["c++", "--version"]).splitlines()[:1],
        "mpi": command_output(["mpirun", "--version"]).splitlines()[:2],
        "command": public_command,
        "command_argv": shlex.split(public_command),
        "sync_mode": args.sync,
        "rank_count": args.ranks,
        "mode": args.mode,
        "seed": args.seed,
        "interval_seconds": args.interval_seconds,
        "wall_clock_sec": args.wall_clock_sec,
        "return_code": args.return_code,
        "input_sha256": inputs,
        "notes": [
            public_text(note, codes_root=args.codes_root, ross_root=args.ross_root)
            for note in args.note
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
