#!/usr/bin/env python3
"""Remove machine- and user-specific paths from generated experiment results."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".out",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def text_files(directory: Path):
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Anonymize generated results across all experiments."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Root of the fluid-flow-wan-experiments repository.",
    )
    parser.add_argument(
        "--codes-root",
        type=Path,
        default=Path(os.environ.get("CODES_ROOT", Path.home() / "codes")),
        help="Root of the local CODES checkout.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    codes_root = args.codes_root.expanduser().resolve()
    home = Path.home().resolve()

    results_directories = sorted(
        path
        for path in repo_root.glob("experiment*/results")
        if path.is_dir()
    )

    if not results_directories:
        raise SystemExit(f"No experiment result directories found under {repo_root}")

    # Apply specific replacements before the general home-directory replacement.
    replacements = [
        (str(codes_root), "/workspace/codes"),
        (str(repo_root), "/workspace/fluid-flow-wan-experiments"),
        (str(home), "/home/anonymous"),
    ]

    scanned = 0
    changed = 0

    for results in results_directories:
        for path in text_files(results):
            scanned += 1
            original = path.read_text(errors="replace")
            updated = original

            for source, replacement in replacements:
                updated = updated.replace(source, replacement)

            if updated != original:
                path.write_text(updated)
                changed += 1
                print(f"sanitized {path.relative_to(repo_root)}")

    # Verify that personally identifying paths and names do not remain.
    forbidden = {
        str(home),
        "/home/local/KHQ",
        "sanjay.chari",
        "sanjaychari",
        "tagvor",
        "etheria",
    }

    leaks: list[tuple[Path, str]] = []

    for results in results_directories:
        for path in text_files(results):
            text = path.read_text(errors="replace")
            lowered = text.lower()

            for value in forbidden:
                if value.lower() in lowered:
                    leaks.append((path.relative_to(repo_root), value))

    if leaks:
        print("\nAnonymization failed. Remaining identifying strings:")
        for path, value in leaks:
            print(f"  {path}: {value}")
        raise SystemExit(1)

    print(
        "\nAnonymization complete: "
        f"result_directories={len(results_directories)} "
        f"files_scanned={scanned} files_changed={changed}"
    )


if __name__ == "__main__":
    main()
