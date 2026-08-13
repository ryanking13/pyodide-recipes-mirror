"""
Various common utilities for testing.
"""

import re

import pytest
from pytest_pyodide import get_global_config
from pytest_pyodide.utils import package_is_built as _package_is_built


def maybe_skip_test(item, delayed=False):
    """If necessary skip test at the fixture level, to avoid
    loading the selenium_standalone fixture which takes a long time.
    """
    browsers = "|".join(["firefox", "chrome", "node", "safari"])
    is_common_test = str(item.fspath).endswith("test_packages_common.py")

    skip_msg = None
    # Testing a package. Skip the test if the package is not built.
    match = re.match(
        r".*/packages/(?P<name>[\w\-\.]+)/test_[\w\-]+\.py", str(item.parent.fspath)
    )
    if match and not is_common_test:
        package_name = match.group("name")
        if not package_is_built(package_name) and re.match(
            rf"test_[\w\-\.]+\[({browsers})[^\]]*\]", item.name
        ):
            skip_msg = f"package '{package_name}' is not built."

    # Common package import test. Skip it if the package is not built.
    if skip_msg is None and is_common_test and item.name.startswith("test_import"):
        if not pytest.pyodide_runtimes:
            skip_msg = "Not running browser tests"

        else:
            match = re.match(
                rf"test_import\[({browsers})-(?P<name>[\w\-\.]+)\]", item.name
            )
            if match:
                package_name = match.group("name")
                if not package_is_built(package_name):
                    # selenium_standalone as it takes a long time to initialize
                    skip_msg = f"package '{package_name}' is not built."
            else:
                raise AssertionError(
                    f"Couldn't parse package name from {item.name}. This should not happen!"
                )  # If the test is going to be skipped remove the

    # TODO: also use this hook to skip doctests we cannot run (or run them
    # inside the selenium wrapper)

    if skip_msg is not None:
        if delayed:
            item.add_marker(pytest.mark.skip(reason=skip_msg))
        else:
            pytest.skip(skip_msg)


def pytest_configure(config):
    """Monkey patch the function cwd_relative_nodeid

    returns the description of a test for the short summary table. Monkey patch
    it to reduce the verbosity of the test names in the table.  This leaves
    enough room to see the information about the test failure in the summary.
    """
    pytest.pyodide_dist_dir = config.getoption("--dist-dir")


def pytest_collection_modifyitems(config, items):
    """Called after collect is completed.
    Parameters
    ----------
    config : pytest config
    items : list of collected items
    """
    markexpr = config.getoption("-m", default="")
    for item in items:
        if item.get_closest_marker("db") and "db" not in markexpr:
            item.add_marker(
                pytest.mark.skip(reason="db test skipped (use '-m db' to run)")
            )
            continue
        maybe_skip_test(item, delayed=True)


def package_is_built(package_name):
    return _package_is_built(package_name, pytest.pyodide_dist_dir)


def set_configs():
    pytest_pyodide_config = get_global_config()

    pytest_pyodide_config.set_flags(
        "chrome",
        pytest_pyodide_config.get_flags("chrome")
        + [
            "--enable-features=WebAssemblyExperimentalJSPI",
            "--enable-experimental-webassembly-features",
        ],
    )

    pytest_pyodide_config.set_flags(
        "node",
        pytest_pyodide_config.get_flags("node")
        + ["--experimental-wasm-stack-switching"],
    )

    pytest_pyodide_config.set_load_pyodide_script(
        "chrome",
        """
        let pyodide = await loadPyodide({
            fullStdLib: false,
            jsglobals : self,
            enableRunUntilComplete: true,
        });
        """,
    )

    pytest_pyodide_config.set_load_pyodide_script(
        "node",
        """
        const {readFileSync} = require("fs");
        let pyodide = await loadPyodide({
            fullStdLib: false,
            jsglobals: self,
            enableRunUntilComplete: true,
        });
        """,
    )
    pytest_pyodide_config.add_node_extra_globals(["Request", "Response", "URL"])


set_configs()


only_node = pytest.mark.xfail_browsers(
    chrome="node only", firefox="node only", safari="node only"
)
only_chrome = pytest.mark.xfail_browsers(
    node="chrome only", firefox="chrome only", safari="chrome only"
)

requires_jspi = pytest.mark.xfail_browsers(
    firefox="requires jspi", safari="requires jspi"
)


@pytest.fixture(scope="function")
def selenium_nodesock(selenium_standalone_refresh, runtime):
    if runtime != "node":
        pytest.skip("Only works in node")

    selenium = selenium_standalone_refresh
    selenium.run_js(
        """
        await pyodide.useNodeSockFS();
        """
    )
    yield selenium
