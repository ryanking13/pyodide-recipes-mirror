# POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 POSTGRES_USER=postgres \
# POSTGRES_PASSWORD=password POSTGRES_DB=postgres pytest -m db \
# --runner=selenium --rt node packages/asyncpg/test_asyncpg_e2e.py

import os

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node


@pytest.fixture(scope="module")
def postgres_connection_config():
    required_names = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]
    missing = [name for name in required_names if not os.environ.get(name)]
    if missing:
        pytest.fail(
            "Missing required PostgreSQL test environment variables: "
            + ", ".join(missing)
        )

    return {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.environ["POSTGRES_PORT"]),
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "database": os.environ["POSTGRES_DB"],
    }


@run_in_pyodide(packages=["asyncpg"])
async def run_asyncpg_e2e(selenium, config):
    import uuid

    import asyncpg

    connection = await asyncpg.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        ssl=False,
    )
    table_name = f"pyodide_asyncpg_e2e_{uuid.uuid4().hex[:12]}"

    try:
        assert await connection.fetchval("SELECT $1::integer", 42) == 42

        async with connection.transaction():
            await connection.execute(
                f"CREATE TABLE {table_name} "
                "(id INTEGER PRIMARY KEY, note TEXT NOT NULL, amount INTEGER NOT NULL)"
            )
            await connection.execute(
                f"INSERT INTO {table_name} (id, note, amount) VALUES ($1, $2, $3)",
                3,
                "async connection",
                42,
            )

        row = await connection.fetchrow(
            f"SELECT id, note, amount FROM {table_name} WHERE id = $1", 3
        )
        assert tuple(row) == (3, "async connection", 42)
    finally:
        await connection.execute(f"DROP TABLE IF EXISTS {table_name}")
        await connection.close()


@pytest.mark.db
@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@only_node
def test_asyncpg_database_driver_e2e(selenium_nodesock, postgres_connection_config):
    run_asyncpg_e2e(selenium_nodesock, postgres_connection_config)
