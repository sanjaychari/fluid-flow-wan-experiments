#!/usr/bin/env python3
from pathlib import Path
import argparse

p = argparse.ArgumentParser()
p.add_argument("input", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
lines = a.input.read_text(errors="replace").replace("\r", "").splitlines()
if not lines:
    raise SystemExit(f"empty CSV: {a.input}")
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(lines[0] + "\n" + "\n".join(sorted(x for x in lines[1:] if x)) + ("\n" if len(lines) > 1 else ""))
