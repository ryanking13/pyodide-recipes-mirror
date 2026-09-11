#!/usr/bin/env python3

# Create the psycopg-binary package by renaming and patching psycopg-c

# Adapted from https://github.com/psycopg/psycopg/blob/3.3.4/tools/ci/copy_to_binary.py

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

curdir = Path(__file__).parent


def sed_i(pattern: str, repl: str, filename: str | Path) -> None:
    with open(filename, "rb") as f:
        data = f.read()

    if (newdata := re.sub(pattern.encode("utf8"), repl.encode("utf8"), data)) != data:
        with open(filename, "wb") as f:
            f.write(newdata)


shutil.move(curdir / "psycopg_c", curdir / "psycopg_binary")
shutil.move(curdir / "README-binary.rst", curdir / "README.rst")
sed_i("psycopg-c", "psycopg-binary", curdir / "pyproject.toml")
sed_i("psycopg-c", "psycopg-binary", curdir / "psycopg_binary/version.py")
sed_i(r'"psycopg_c([\./][^"]+)?"', r'"psycopg_binary\1"', curdir / "pyproject.toml")
sed_i(r"__impl__\s*=.*", '__impl__ = "binary"', curdir / "psycopg_binary/pq.pyx")
for dirpath, dirnames, filenames in os.walk(curdir):
    for filename in filenames:
        if os.path.splitext(filename)[1] not in (".pyx", ".pxd", ".py"):
            continue
        sed_i(r"\bpsycopg_c\b", "psycopg_binary", Path(dirpath) / filename)