"""Patch rdkit/__init__.py for emscripten/Pyodide support.

The librdkit_core.so shared library is loaded by Pyodide via the librdkit
shared_library package (asynchronously during loadPackage). Each wrapper
.so.wasm module links against librdkit_core.so directly (like scipy links
against libopenblas), so no RTLD_GLOBAL hack is needed.

This patch:
1. Sets RDBASE for RDConfig.py path resolution
2. Registers a custom MetaPathFinder to load .so.wasm wrapper modules
"""

init_path = "rdkit/__init__.py"
init = open(init_path).read()

loader = '''import sys as _sys

if _sys.platform == 'emscripten':
    import os as _os
    import importlib.abc
    import importlib.machinery

    # Set RDBASE so RDConfig.py finds Data/, Docs/, etc. relative to this package
    _os.environ['RDBASE'] = _os.path.dirname(__file__)

    class _RDKitExtensionFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            parts = fullname.split('.')
            if parts[0] != 'rdkit':
                return None
            modname = parts[-1]
            if path:
                for d in path:
                    candidate = _os.path.join(d, modname + '.so.wasm')
                    if _os.path.exists(candidate):
                        loader = importlib.machinery.ExtensionFileLoader(
                            fullname, candidate
                        )
                        return importlib.util.spec_from_file_location(
                            fullname, candidate, loader=loader,
                        )
            return None

    import importlib.util
    _sys.meta_path.insert(0, _RDKitExtensionFinder())

'''

open(init_path, "w").write(loader + init)
print("Patched rdkit/__init__.py")
