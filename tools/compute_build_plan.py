#!/usr/bin/env python
"""Compute per-package build fingerprints for the wheel cache system.

For each package, computes a content-addressable fingerprint based on:
  - Global toolchain hash (pyodide-build commit, emscripten version, etc.)
  - Per-package recipe hash (meta.yaml, patches, extras, source URL/sha256)
  - Recursive host dependency fingerprints

Outputs a build-plan.json file used by restore_build_cache.py and save_build_cache.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from graphlib import TopologicalSorter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGES_DIR = BASE_DIR / "packages"
PYODIDE_BUILD_DIR = BASE_DIR / "pyodide-build"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute build fingerprints for all packages"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="build-plan.json",
        help="Output path for build-plan.json",
    )
    parser.add_argument(
        "--packages-dir",
        type=str,
        default=str(PACKAGES_DIR),
        help="Path to the packages directory",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    """Load a YAML file. Uses ruamel.yaml if available, falls back to PyYAML."""
    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        return yaml.load(path)
    except ImportError:
        import yaml

        with open(path) as f:
            return yaml.safe_load(f)


def compute_toolchain_hash() -> str:
    """Compute a hash of all global toolchain inputs.

    Inputs:
      - pyodide-build submodule commit SHA
      - emscripten version (from pyodide config or pyodide-build)
      - xbuildenv URL (from pyproject.toml)
      - python version (from environment.yml)
      - constraints.txt content
      - environment.yml content
      - rust_toolchain (from pyproject.toml)
    """
    hasher = hashlib.sha256()

    # 1. pyodide-build submodule commit
    try:
        result = subprocess.run(
            ["git", "-C", str(PYODIDE_BUILD_DIR), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        hasher.update(f"pyodide-build-commit:{result.stdout.strip()}".encode())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: hash the pyodide-build directory content marker
        hasher.update(b"pyodide-build-commit:unknown")

    # 2. Emscripten version - try `pyodide config get emscripten_version` first
    emscripten_version = _get_emscripten_version()
    hasher.update(f"emscripten:{emscripten_version}".encode())

    # 3. xbuildenv URL and rust_toolchain from pyproject.toml
    pyproject_path = BASE_DIR / "pyproject.toml"
    if pyproject_path.exists():
        pyproject_content = pyproject_path.read_text()
        # Extract relevant fields instead of hashing the whole file
        # (pyproject.toml also has linter config that doesn't affect builds)
        for line in pyproject_content.splitlines():
            line = line.strip()
            if line.startswith("default_cross_build_env_url"):
                hasher.update(f"xbuildenv:{line}".encode())
            elif line.startswith("rust_toolchain"):
                hasher.update(f"rust:{line}".encode())

    # 4. Python version from environment.yml
    env_yml_path = BASE_DIR / "environment.yml"
    if env_yml_path.exists():
        hasher.update(f"environment.yml:{env_yml_path.read_text()}".encode())

    # 5. constraints.txt
    constraints_path = BASE_DIR / "tools" / "constraints.txt"
    if constraints_path.exists():
        hasher.update(f"constraints:{constraints_path.read_text()}".encode())

    return hasher.hexdigest()


def _get_emscripten_version() -> str:
    """Get emscripten version from pyodide config or fallback to parsing."""
    try:
        result = subprocess.run(
            ["pyodide", "config", "get", "emscripten_version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: try to extract from pyodide-build config files
        config_path = PYODIDE_BUILD_DIR / "pyodide_build" / "config.py"
        if config_path.exists():
            content = config_path.read_text()
            # Simple extraction — not robust but good enough as fallback
            for line in content.splitlines():
                if "PYODIDE_EMSCRIPTEN_VERSION" in line and "=" in line:
                    return line.split("=")[-1].strip().strip('"').strip("'")
        return "unknown"


def compute_recipe_hash(pkg_dir: Path, meta: dict) -> str:
    """Compute the hash of a single package's recipe inputs.

    Inputs:
      - meta.yaml file content
      - patch file contents (sorted by name)
      - extra file contents (sorted by name)
      - source URL string
      - source sha256 string
    """
    hasher = hashlib.sha256()

    # 1. meta.yaml content (the full file, not the parsed dict)
    meta_yaml_path = pkg_dir / "meta.yaml"
    if meta_yaml_path.exists():
        hasher.update(meta_yaml_path.read_bytes())

    source = meta.get("source", {})

    # 2. Patch file contents (sorted)
    patches = source.get("patches", [])
    for patch_name in sorted(patches):
        patch_path = pkg_dir / patch_name
        if patch_path.exists():
            hasher.update(patch_path.read_bytes())
        else:
            # Hash the name even if file is missing (indicates a problem)
            hasher.update(f"missing-patch:{patch_name}".encode())

    # 3. Extra file contents (sorted)
    extras = source.get("extras", [])
    for extra in sorted(
        extras, key=lambda x: x[0] if isinstance(x, (list, tuple)) else str(x)
    ):
        if isinstance(extra, (list, tuple)):
            extra_src = extra[0]
        else:
            extra_src = str(extra)
        extra_path = pkg_dir / extra_src
        if extra_path.exists():
            hasher.update(extra_path.read_bytes())
        else:
            hasher.update(f"missing-extra:{extra_src}".encode())

    # 4. Source URL
    url = source.get("url")
    if url:
        hasher.update(f"url:{url}".encode())

    # 5. Source sha256
    sha256 = source.get("sha256")
    if sha256:
        hasher.update(f"sha256:{sha256}".encode())

    # 6. Source path (for in-tree sources)
    path = source.get("path")
    if path:
        src_path = (pkg_dir / path).resolve()
        if src_path.exists() and src_path.is_dir():
            # Hash all files in the source tree
            for f in sorted(src_path.rglob("*")):
                if f.is_file():
                    hasher.update(f.read_bytes())
        elif src_path.exists():
            hasher.update(src_path.read_bytes())

    return hasher.hexdigest()


def _load_single_package(
    meta_path: Path,
) -> tuple[str, dict | None, str | None]:
    """Load meta.yaml and compute recipe hash for a single package.

    Returns (pkg_name, meta_dict, recipe_hash) or (pkg_name, None, None) on failure.
    """
    pkg_name = meta_path.parent.name
    pkg_dir = meta_path.parent
    try:
        meta = load_yaml(meta_path)
        if meta is None:
            print(f"Warning: empty meta.yaml for {pkg_name}", file=sys.stderr)
            return pkg_name, None, None
        recipe_hash = compute_recipe_hash(pkg_dir, meta)
        return pkg_name, meta, recipe_hash
    except Exception as e:
        print(f"Warning: failed to parse {meta_path}: {e}", file=sys.stderr)
        return pkg_name, None, None


def load_all_package_metadata(
    packages_dir: Path,
) -> tuple[dict[str, dict], dict[str, str]]:
    """Load meta.yaml and compute recipe hashes for all packages concurrently.

    Returns (all_meta, recipe_hashes) dicts.
    """
    meta_paths = sorted(packages_dir.glob("*/meta.yaml"))
    packages: dict[str, dict] = {}
    recipe_hashes: dict[str, str] = {}

    max_workers = min(32, (os.cpu_count() or 4) + 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = pool.map(_load_single_package, meta_paths)
        for pkg_name, meta, recipe_hash in results:
            if meta is not None and recipe_hash is not None:
                packages[pkg_name] = meta
                recipe_hashes[pkg_name] = recipe_hash

    return packages, recipe_hashes


def get_host_dependencies(meta: dict) -> list[str]:
    """Extract host dependencies from a package's metadata."""
    requirements = meta.get("requirements", {})
    return requirements.get("host", [])


def is_cross_build_env(meta: dict) -> bool:
    """Check if a package has cross-build-env: true."""
    build = meta.get("build", {})
    return build.get("cross-build-env", False)


def get_package_type(meta: dict) -> str:
    """Get the package type (package, static_library, shared_library, cpython_module)."""
    build = meta.get("build", {})
    return build.get("type", "package")


def compute_all_fingerprints(
    all_meta: dict[str, dict],
    recipe_hashes: dict[str, str],
    toolchain_hash: str,
) -> dict[str, str]:
    """Compute fingerprints for all packages in topological order.

    Fingerprints are computed leaves-first so that each package's fingerprint
    includes the fingerprints of its host dependencies (recursive).
    """
    graph: dict[str, set[str]] = {}
    for name, meta in all_meta.items():
        host_deps = get_host_dependencies(meta)
        graph[name] = {dep for dep in host_deps if dep in all_meta}

    fingerprints: dict[str, str] = {}

    try:
        topo_order = list(TopologicalSorter(graph).static_order())
    except Exception as e:
        print(f"Error: dependency cycle detected: {e}", file=sys.stderr)
        sys.exit(1)

    for name in topo_order:
        if name not in all_meta:
            continue

        hasher = hashlib.sha256()

        # 1. Toolchain hash (global)
        hasher.update(f"toolchain:{toolchain_hash}".encode())

        # 2. Recipe hash (per-package)
        hasher.update(f"recipe:{recipe_hashes[name]}".encode())

        # 3. Host dependency fingerprints (recursive, sorted for determinism)
        host_deps = sorted(graph.get(name, set()))
        for dep in host_deps:
            if dep in fingerprints:
                hasher.update(f"dep:{dep}:{fingerprints[dep]}".encode())

        fingerprints[name] = hasher.hexdigest()

    return fingerprints


def main() -> None:
    args = parse_args()
    packages_dir = Path(args.packages_dir)

    print(f"Loading package metadata from {packages_dir}...")
    all_meta, recipe_hashes = load_all_package_metadata(packages_dir)
    print(f"Found {len(all_meta)} packages")

    print("Computing toolchain hash...")
    toolchain_hash = compute_toolchain_hash()
    print(f"Toolchain hash: {toolchain_hash[:16]}...")

    print("Computing per-package fingerprints...")
    fingerprints = compute_all_fingerprints(all_meta, recipe_hashes, toolchain_hash)

    # Identify cross-build-env packages
    cross_build_packages = sorted(
        name for name, meta in all_meta.items() if is_cross_build_env(meta)
    )

    # Identify library packages (static_library, shared_library)
    # These don't produce wheels — needs_rebuild() checks build/.packaged token instead
    library_packages = sorted(
        name
        for name, meta in all_meta.items()
        if get_package_type(meta) in ("static_library", "shared_library")
    )

    build_plan = {
        "toolchain_hash": toolchain_hash,
        "fingerprints": {k: v for k, v in sorted(fingerprints.items())},
        "cross_build_packages": cross_build_packages,
        "library_packages": library_packages,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(build_plan, indent=2) + "\n")
    print(f"Build plan written to {output_path}")
    print(f"  Total packages: {len(fingerprints)}")
    print(f"  Cross-build-env (always rebuild): {cross_build_packages}")
    print(f"  Library packages: {len(library_packages)}")

    num_unique_fps = len(set(fingerprints.values()))
    print(f"  Unique fingerprints: {num_unique_fps}")


if __name__ == "__main__":
    main()
