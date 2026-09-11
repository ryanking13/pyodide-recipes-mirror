# Wheel Build Cache

The wheel build cache avoids rebuilding packages on `main` branch CI when their inputs haven't changed. It sits in front of the existing `build-recipes "*"` command and requires no changes to `pyodide-build`.

## How It Works

```
compute_build_plan.py → actions/cache/restore → build-recipes "*" → save_build_cache.py → actions/cache/save
```

1. `tools/compute_build_plan.py` computes a content fingerprint for every package and writes `build-plan.json`.
2. `actions/cache/restore` fetches `.wheel-cache/` from a previous run using `build-plan.json`'s hash as the cache key.
3. `tools/restore_build_cache.py` copies cached wheels whose fingerprints still match into `packages/{name}/dist/` and sets their mtime to year 2099.
4. `build-recipes "*" --install` runs unchanged. `needs_rebuild()` compares each wheel's mtime against `meta.yaml`'s mtime. Cached wheels (mtime 2099) are newer than any source file, so they are skipped. Uncached packages rebuild normally.
5. `tools/save_build_cache.py` collects all `dist/` directories into `.wheel-cache/` with a manifest, and `actions/cache/save` stores it.

## Fingerprint Computation

Each package's fingerprint captures every input that affects its build output:

```
fingerprint(P) = sha256(toolchain_hash, recipe_hash(P), sorted(fingerprint(D) for D in host_deps(P)))
```

**`toolchain_hash`** is global and shared across all packages:

| Input | Source |
|-------|--------|
| pyodide-build submodule commit | `git -C pyodide-build rev-parse HEAD` |
| Emscripten version | `pyodide config get emscripten_version` |
| Cross-build env URL | `pyproject.toml` → `default_cross_build_env_url` |
| Rust toolchain version | `pyproject.toml` → `rust_toolchain` |
| Python version | `environment.yml` |
| Build constraints | `tools/constraints.txt` content |
| Native tool versions | `environment.yml` content |

**`recipe_hash(P)`** is per-package:

| Input | Source |
|-------|--------|
| Recipe definition | `packages/{name}/meta.yaml` file content |
| Patches | Each file listed in `source.patches`, sorted |
| Extra files | Each file listed in `source.extras`, sorted |
| Upstream source identity | `source.url` and `source.sha256` strings |
| In-tree source | All files under `source.path`, if set |

**Host dependency propagation** — fingerprints are computed in topological order (leaves first). If numpy's fingerprint changes, scipy's automatically changes because scipy's hash includes `fingerprint(numpy)`. Only `requirements.host` dependencies propagate, not `requirements.run`, matching the existing `generate_needs_build_set()` semantics in `graph_builder.py`.

Run dependencies, test files, ccache settings, and the runner image are excluded — they don't affect wheel binary output.

## The mtime Trick

`needs_rebuild()` in `pyodide-build` determines whether to rebuild a package by checking if the wheel in `dist/` is newer than `meta.yaml` and its patches. On a fresh CI checkout, `git` resets all source file timestamps to "now", so any restored wheel would appear older and trigger a rebuild.

The restore script works around this by setting restored wheels' mtime to `4102444800` (2099-12-31). This is always newer than any source file timestamp, so `needs_rebuild()` returns `False` and the package is skipped.

`--force-rebuild` is not used because it operates at the `build_from_graph()` level and rebuilds all resolved dependencies, not just the target package.

## Cross-Build-Env Packages

Packages with `cross-build-env: true` in `meta.yaml` (numpy, scipy, pycparser, cffi) are **always rebuilt**. These packages install files into the host Python site-packages (headers, static libraries, `.pxd` files) that downstream packages link against during compilation. Restoring only the wheel from cache would leave those host files missing and break dependents.

The restore script identifies these packages via `build-plan.json` and skips them. Without a cached wheel in `dist/`, `needs_rebuild()` returns `True` and they rebuild naturally.

## Cache Storage

All wheels are stored in a single `.wheel-cache/` directory managed by `actions/cache`:

```
.wheel-cache/
├── manifest.json          # maps package names → fingerprints
├── numpy/
│   └── numpy-2.2.5-cp313-cp313-pyodide_2025_0_wasm32.whl
├── requests/
│   └── requests-2.32.4-py3-none-any.whl
├── .libs/                 # shared/static library outputs
│   └── ...
└── ...
```

**Cache key**: `wheel-cache-v1-{hashFiles('build-plan.json')}`. Any fingerprint change produces a new key. `restore-keys: wheel-cache-v1-` enables prefix matching, so a partial hit restores the most recent cache. The restore script then validates each wheel individually — stale wheels are not extracted and those packages rebuild.

**Sizing**: ~349 packages × ~2 MB average ≈ ~700 MB, well within the 10 GB per-repo limit. Upload/download takes ~30–60 seconds.

**Limits**: Cache keys are immutable (no overwrites). Entries unused for 7 days are evicted. Upload rate is capped at 200/minute/repo; the bundled approach uses 1 save + 1 restore per run.

**Branch scoping**: Caches from `main` are readable by PR branches. PR caches are isolated from other PRs and `main`.

## Scripts

| Script | Input | Output |
|--------|-------|--------|
| `tools/compute_build_plan.py` | `packages/*/meta.yaml`, `pyproject.toml`, `environment.yml`, `tools/constraints.txt` | `build-plan.json` |
| `tools/restore_build_cache.py` | `build-plan.json`, `.wheel-cache/` | Wheels in `packages/*/dist/` with mtime = 2099 |
| `tools/save_build_cache.py` | `build-plan.json`, `packages/*/dist/` | `.wheel-cache/` with `manifest.json` |

## Edge Cases

**`tag:always` packages** (hashlib, micropip, ssl, etc.) — the tag means "always include in the build set", not "always rebuild". They are fingerprinted and cached normally.

**Static/shared libraries** (libopenblas, libproj, etc.) — output goes to `packages/.libs/` instead of or in addition to `dist/`. The cache includes `.libs/` contents. Rebuild detection uses a `.packaged` token file.

**Partial build failures** — the save step runs after the build. Only packages with artifacts in `dist/` are cached. Failed packages have no cached entry and will be retried on the next run.

**Stale cache entries** — when `restore-keys` matches an older cache, it may contain wheels with outdated fingerprints. The restore script compares each cached fingerprint against the current `build-plan.json` and only extracts matches.

## Future Improvements

**Cache cross-build-env packages** — instead of always rebuilding them, cache their wheels plus their `cross-build-files` and replay the host site-packages installation on restore. This would eliminate the ~25 minute floor on cached builds.

**Per-package cache entries** — if the bundled approach causes too much churn, switch to per-package cache keys (`wheel-v1-{name}-{fingerprint[:16]}`) using the GitHub Actions internal cache API (`ACTIONS_CACHE_URL` + `ACTIONS_RUNTIME_TOKEN`).

**Content-based `needs_rebuild()`** — add a recipe hash check to `pyodide-build`'s `needs_rebuild()` to make it mtime-immune, removing the need for the 2099 timestamp workaround.
