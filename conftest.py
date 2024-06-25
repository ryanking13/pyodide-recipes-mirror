"""
Various common utilities for testing.
"""
import re

import pytest
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
        r".*/packages/(?P<name>[\w\-]+)/test_[\w\-]+\.py", str(item.parent.fspath)
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
    for item in items:
        maybe_skip_test(item, delayed=True)


def package_is_built(package_name):
    return _package_is_built(package_name, pytest.pyodide_dist_dir)


requires_jspi = pytest.mark.xfail_browsers(
    firefox="requires jspi", safari="requires jspi"
)
