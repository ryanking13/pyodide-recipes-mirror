#!/usr/bin/env python
"""Bundle all built wheels into .wheel-cache/ for GitHub Actions cache.

After the build completes, this script collects all wheels from
packages/*/dist/ and copies them into .wheel-cache/{name}/ along
with a manifest.json that maps package names to their fingerprints.

The .wheel-cache/ directory is then saved by `actions/cache/save`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGES_DIR = BASE_DIR / "packages"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle built wheels into cache directory"
    )
    parser.add_argument(
        "--build-plan",
        type=str,
        required=True,
        help="Path to build-plan.json",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        required=True,
        help="Path to the .wheel-cache directory to create/update",
    )
    parser.add_argument(
        "--packages-dir",
        type=str,
        default=str(PACKAGES_DIR),
        help="Path to the packages directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_plan_path = Path(args.build_plan)
    cache_dir = Path(args.cache_dir)
    packages_dir = Path(args.packages_dir)

    if not build_plan_path.exists():
        print(f"Error: build plan not found at {build_plan_path}", file=sys.stderr)
        sys.exit(1)

    build_plan = json.loads(build_plan_path.read_text())
    fingerprints: dict[str, str] = build_plan["fingerprints"]
    library_packages: set[str] = set(build_plan.get("library_packages", []))

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True)

    cached_count = 0
    skipped_no_dist = 0
    skipped_library = 0
    total_size = 0

    for pkg_name in sorted(fingerprints):
        if pkg_name in library_packages:
            skipped_library += 1
            continue

        dist_dir = packages_dir / pkg_name / "dist"
        if not dist_dir.exists():
            skipped_no_dist += 1
            continue

        artifacts = [f for f in dist_dir.iterdir() if f.is_file()]
        if not artifacts:
            skipped_no_dist += 1
            continue

        pkg_cache_dir = cache_dir / pkg_name
        pkg_cache_dir.mkdir(parents=True, exist_ok=True)

        for artifact in artifacts:
            dest = pkg_cache_dir / artifact.name
            shutil.copy2(artifact, dest)
            total_size += artifact.stat().st_size

        cached_count += 1

    manifest = {
        "fingerprints": fingerprints,
        "toolchain_hash": build_plan.get("toolchain_hash", ""),
        "cross_build_packages": build_plan.get("cross_build_packages", []),
        "library_packages": sorted(library_packages),
    }
    manifest_path = cache_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    total_size_mb = total_size / (1024 * 1024)
    print(f"Cache save summary:")
    print(f"  Wheel packages cached: {cached_count}")
    print(f"  Skipped (library packages): {skipped_library}")
    print(f"  Skipped (no dist/): {skipped_no_dist}")
    print(f"  Total cache size: {total_size_mb:.1f} MB")
    print(f"  Cache directory: {cache_dir}")


if __name__ == "__main__":
    main()
