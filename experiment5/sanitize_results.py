#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


TEXT_SUFFIXES = {
    ".out", ".log", ".txt", ".csv", ".yaml", ".yml", ".xml", ".json"
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace machine-specific absolute paths in generated Experiment 5 results."
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument(
        "--codes-root",
        type=Path,
        default=Path(os.environ.get("CODES_ROOT", Path.home() / "codes")),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    args = parser.parse_args()

    results = args.results.resolve()
    codes_root = args.codes_root.resolve()
    repo_root = args.repo_root.resolve()

    replacements = [
        (str(codes_root), "/workspace/codes"),
        (str(repo_root), "/workspace/fluid-flow-wan-experiments"),
    ]

    changed = 0
    scanned = 0

    for path in sorted(results.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue

        scanned += 1
        text = path.read_text(errors="replace")
        updated = text

        # Replace the more specific roots before checking for a remaining home path.
        for source, target in replacements:
            updated = updated.replace(source, target)

        if updated != text:
            path.write_text(updated)
            changed += 1

    # Fail loudly if this user's home directory still occurs in a generated text
    # artifact. This catches a newly introduced path that is not covered above.
    home = str(Path.home().resolve())
    leaks = []
    for path in sorted(results.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(errors="replace")
        if home in text:
            leaks.append(str(path.relative_to(results)))

    if leaks:
        raise SystemExit(
            "machine-specific home path remains in: " + ", ".join(leaks)
        )

    print(
        f"sanitized Experiment 5 results: scanned={scanned} changed={changed}"
    )


if __name__ == "__main__":
    main()
