#!/usr/bin/env python3

import argparse
import re
import statistics
from pathlib import Path


SCALES = (32, 64, 128)
REPEATS = (1, 2, 3)
FLOW_GBIT = 500.0
TERMINALS_PER_SWITCH = 2


def parse_codes_runtime(path: Path) -> float:
    text = path.read_text(errors="replace")
    match = re.search(
        r"Running Time\s*[:=]\s*([0-9.eE+-]+)",
        text,
    )
    if not match:
        raise RuntimeError(f"could not find CODES runtime in {path}")
    return float(match.group(1))


def parse_simgrid_runtime(path: Path) -> float:
    text = path.read_text(errors="replace")
    match = re.search(
        r"SIMGRID_WALL_RUNTIME_SEC=([0-9.eE+-]+)",
        text,
    )
    if not match:
        raise RuntimeError(f"could not find SimGrid runtime in {path}")
    return float(match.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    print(
        "switches,terminals,"
        "codes_runtime_mean_sec,codes_runtime_std_sec,"
        "simgrid_runtime_mean_sec,simgrid_runtime_std_sec,"
        "codes_gbit_per_wall_sec,simgrid_gbit_per_wall_sec,"
        "codes_over_simgrid_runtime"
    )

    for switches in SCALES:
        case = args.root / str(switches)

        codes = [
            parse_codes_runtime(
                case / f"codes-performance-{r}.out"
            )
            for r in REPEATS
        ]

        simgrid = [
            parse_simgrid_runtime(
                case / f"simgrid-performance-{r}.out"
            )
            for r in REPEATS
        ]

        terminals = switches * TERMINALS_PER_SWITCH
        total_gbit = terminals * FLOW_GBIT

        cmean = statistics.mean(codes)
        cstd = statistics.stdev(codes)

        smean = statistics.mean(simgrid)
        sstd = statistics.stdev(simgrid)

        print(
            f"{switches},{terminals},"
            f"{cmean:.9f},{cstd:.9f},"
            f"{smean:.9f},{sstd:.9f},"
            f"{total_gbit / cmean:.9f},"
            f"{total_gbit / smean:.9f},"
            f"{cmean / smean:.9f}"
        )


if __name__ == "__main__":
    main()
