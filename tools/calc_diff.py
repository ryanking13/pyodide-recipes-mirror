#!/usr/bin/env python

import argparse
import shutil
import subprocess as sp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate the difference between two commits"
    )
    parser.add_argument(
        "-b", "--base", help="The base commit", type=str, default="HEAD~1"
    )
    parser.add_argument(
        "-t", "--target", help="The target commit", type=str, default="HEAD"
    )
    return parser.parse_args()


def check_requirements():
    if not shutil.which("git"):
        print("git not found in PATH")
        exit(1)


def main():
    check_requirements()

    args = parse_args()

    base = args.base
    target = args.target

    print(f"Calculating diff between {base} and {target}")

    diff = sp.run(
        ["git", "diff", "--name-only", base, target], capture_output=True, text=True
    ).stdout.split("\n")
    diff = [x for x in diff if x != ""]

    print(f"Found {len(diff)} files changed")

    for file in diff:
        print(f"Diff for {file}:")
        print(
            sp.run(
                ["git", "diff", base, target, file], capture_output=True, text=True
            ).stdout
        )

    print("Done")


if __name__ == "__main__":
    main()
