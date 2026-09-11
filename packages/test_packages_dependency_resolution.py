import functools
import os
from pathlib import Path
import subprocess as sp
import re

from pytest_pyodide.utils import package_is_built as _package_is_built
import pytest

from conftest import package_is_built

PKG_DIR = Path(__file__).parent
DIST_DIR = Path(__file__).parent.parent / "dist"


@functools.cache
def registered_packages() -> list[str]:
    """Returns a list of registered package names"""
    packages = []
    for name in os.listdir(PKG_DIR):
        if (PKG_DIR / name).is_dir() and (PKG_DIR / name / "meta.yaml").exists():
            packages.append(name)

    return packages


def package_is_built(package_name):
    return _package_is_built(package_name, pytest.pyodide_dist_dir)


@pytest.fixture(scope="module")
def pyodide_venv(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pyodide_venv")
    venv_path = tmp_path / "venv"
    sp.run(["pyodide", "venv", str(venv_path)], check=True, capture_output=True)

    # FIXME: when building packages in xbuildenv, the pip in the venv locates
    # the packages from our cdn URL.
    # but in this repository, we are building packages locally, so we need to
    # override the pip config to not use the cdn URL.
    pip_conf_path = venv_path / "pip.conf"
    assert pip_conf_path.exists()
    original_content = pip_conf_path.read_text()
    new_content = re.sub(
        r"extra-index-url=.*",
        F"find-links={DIST_DIR}",
        original_content,
    )

    pip_conf_path.write_text(new_content)

    yield venv_path

@pytest.mark.driver_timeout(120)
@pytest.mark.parametrize("name", registered_packages())
def test_pip_install(
    name: str,
    pyodide_venv: Path,
) -> None:
    """
    Install all the packages in the distribution and see if they install correctly.
    TODO: This makes a lot of requests to PyPI... how can we optimize this? Caching maybe?
    """
    if not package_is_built(name):
        pytest.skip(f"Package {name} is not built.")
    
    pip_path = pyodide_venv / "bin" / "pip"

    out = sp.run(
        [
            str(pip_path),
            "install",
            name,
        ],
        check=True,
        capture_output=True,
    )

    stdout = out.stdout.decode()
    assert f"Looking in links: {DIST_DIR}" in stdout
    assert f"Successfully installed" in stdout