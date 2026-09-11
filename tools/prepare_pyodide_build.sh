#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python -m pip install "${repo_root}/pyodide-build/"
pyodide xbuildenv install

# Work around an xbuildenv generation bug: the xbuildenv's requirements.txt
# pins the versions pyodide-build uses for "unisolated" cross-build packages
# (numpy, scipy, ...). Those pins are captured from the *native* venv used to
# generate the xbuildenv rather than from the recipes whose cross-build files it
# ships, so numpy can be pinned to a release newer than the one we build and
# ship. pyodide-build then rewrites e.g. pandas' `numpy>=2.0.0` build
# requirement to that pin, so packages compile against numpy headers that do not
# match the numpy they run against.
#
# That silently miscompiles code rather than failing loudly. numpy 2.5 started
# including __multiarray_api.h from ndarraytypes.h, which defeats the
# NO_IMPORT_ARRAY + PY_ARRAY_UNIQUE_SYMBOL pattern in any file that defines
# those macros after its first numpy include (pandas' vendored np_datetime.c
# does). Such a file gets a translation-unit-local `static int
# PyArray_RUNTIME_VERSION = 0` that import_array() never writes, so the version
# dispatch in PyDataType_C_METADATA() constant-folds to the NumPy 1.x
# descriptor layout. The descriptor's c_metadata is then read at the wrong
# offset, comes back NULL, and every datetime64 unit decodes as NPY_FR_Y
# ("Converting from M or Y units is not supported").
#
# Pin the unisolated numpy back to the version our recipe actually builds.
requirements_txt="$(python -c 'from pyodide_build.build_env import get_pyodide_root; print((get_pyodide_root() / ".." / "requirements.txt").resolve())')"
numpy_version="$(python -c 'import sys; from pathlib import Path; from pyodide_build.recipe.spec import MetaConfig; print(MetaConfig.from_yaml(Path(sys.argv[1])).package.version)' "${repo_root}/packages/numpy/meta.yaml")"

echo "Pinning unisolated numpy to the version built by packages/numpy: ${numpy_version}"
sed -i -E "s/^numpy==.*/numpy==${numpy_version}/" "${requirements_txt}"
grep -E "^numpy==" "${requirements_txt}"
