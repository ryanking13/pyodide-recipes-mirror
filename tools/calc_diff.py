#!/usr/bin/env python

import argparse
import shutil
import subprocess as sp
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
RECIPE_DIR = Path(__file__).parent.parent / "packages"


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
    parser.add_argument(
        "-f",
        "--diff-filter",
        help="The diff filter to use",
        type=str,
        default="AMR",  # Added, Modified, Renamed
    )
    parser.add_argument(
        "-d",
        "--recipe-dir",
        help="The directory containing the recipes",
        type=str,
        default=RECIPE_DIR,
    )
    parser.add_argument(
        "-s",
        "--separator",
        help="The separator to use",
        type=str,
        default=",",
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
    recipe_dir = Path(args.recipe_dir).resolve()

    try:
        recipe_dir_relative = str(recipe_dir.relative_to(BASE_DIR))
    except ValueError:
        print(f"Recipe directory {recipe_dir} is not under {BASE_DIR}")
        exit(1)

    # 1. Get the list of all files that have been modified
    diff = sp.run(
        [
            "git",
            "diff",
            "--name-only",
            f"--diff-filter={args.diff_filter}",
            base,
            target,
        ],
        capture_output=True,
        text=True,
    ).stdout.split("\n")

    # 2. Only keep the changes happened in the recipe directory
    diff = [Path(f).resolve() for f in diff if f.startswith(recipe_dir_relative)]

    # 3. find package names from the recipe directory
    #    say the recipe directory is `packages`,
    #    and if there is a file `packages/abc/...`,
    #    then `abc` is a package name
    packages = set()
    for f in diff:
        while f.parent != recipe_dir:
            f = f.parent

        if not f.is_dir():  # ignore files in the recipe directory
            continue

        packages.add(f.name)

    # 4. print the list of packages
    if packages:
        print(args.separator.join(packages))


if __name__ == "__main__":
    main()
