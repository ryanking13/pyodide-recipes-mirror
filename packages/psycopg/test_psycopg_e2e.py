# POSTGRES_HOST=127.0.0.1 POSTGRES_VERIFY_HOST=localhost POSTGRES_PORT=5432 \
# POSTGRES_USER=postgres POSTGRES_PASSWORD=password POSTGRES_DB=postgres \
# POSTGRES_CA_FILE=/path/to/postgres-ca.pem pytest -m db --runner=selenium \
# --rt node packages/psycopg/test_psycopg_e2e.py

import os
from pathlib import Path

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node


@pytest.fixture(scope="module")
def postgres_connection_config():
    required_names = [
        "POSTGRES_HOST",
        "POSTGRES_VERIFY_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_CA_FILE",
    ]
    missing = [name for name in required_names if not os.environ.get(name)]
    if missing:
        pytest.fail(
            "Missing required PostgreSQL test environment variables: "
            + ", ".join(missing)
        )

    ca_file = Path(os.environ["POSTGRES_CA_FILE"])
    if not ca_file.is_file():
        pytest.fail(f"PostgreSQL CA file does not exist: {ca_file}")

    return {
        "host": os.environ["POSTGRES_HOST"],
        "verify_host": os.environ["POSTGRES_VERIFY_HOST"],
        "port": int(os.environ["POSTGRES_PORT"]),
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "dbname": os.environ["POSTGRES_DB"],
        "ca_pem": ca_file.read_text(encoding="utf-8"),
    }


@pytest.mark.db
@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@only_node
def test_psycopg_database_driver_e2e(selenium_nodesock, postgres_connection_config):
    @run_in_pyodide(packages=["psycopg", "psycopg-c"])
    def run(selenium, config):
        import uuid
        from contextlib import contextmanager
        from pathlib import Path

        import psycopg
        from psycopg import sql

        assert psycopg.pq.__impl__ == "c"

        ca_path = Path("/tmp/postgres-ca.pem")
        ca_path.write_text(config["ca_pem"], encoding="utf-8")

        def connect_postgres(host, sslmode, **kwargs):
            return psycopg.connect(
                host=host,
                port=config["port"],
                user=config["user"],
                password=config["password"],
                dbname=config["dbname"],
                sslmode=sslmode,
                autocommit=True,
                **kwargs,
            )

        def fetch_ssl_row(connection):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 42, ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
                )
                return cursor.fetchone()

        @contextmanager
        def drop_table(cursor, table_name):
            try:
                yield
            finally:
                cursor.execute(
                    sql.SQL("DROP TABLE IF EXISTS {}").format(
                        sql.Identifier(table_name)
                    )
                )

        # without ssl
        with connect_postgres(config["host"], "disable") as connection:
            row = fetch_ssl_row(connection)
            assert row[0] == 42
            assert row[1] is False
            assert row[2] in (None, "")
            assert row[3] in (None, "")

        with connect_postgres(config["host"], "require") as connection:
            row = fetch_ssl_row(connection)
            assert row[0] == 42
            assert row[1] is True
            assert row[2]
            assert row[3]

        table_name = f"pyodide_psycopg_e2e_{uuid.uuid4().hex[:12]}"
        with connect_postgres(
            config["verify_host"],
            "verify-full",
            sslrootcert=str(ca_path),
        ) as connection:
            row = fetch_ssl_row(connection)
            assert row[0] == 42
            assert row[1] is True
            assert row[2]
            assert row[3]

            with connection.cursor() as cursor:
                with drop_table(cursor, table_name):
                    cursor.execute(
                        sql.SQL(
                            "CREATE TABLE {} (id INTEGER PRIMARY KEY, note TEXT NOT NULL, amount INTEGER NOT NULL)"
                        ).format(sql.Identifier(table_name))
                    )
                    record = (3, "verified full", 42)
                    cursor.execute(
                        sql.SQL(
                            "INSERT INTO {} (id, note, amount) VALUES (%s, %s, %s)"
                        ).format(sql.Identifier(table_name)),
                        record,
                    )
                    cursor.execute(
                        sql.SQL("SELECT id, note, amount FROM {} WHERE id = %s").format(
                            sql.Identifier(table_name)
                        ),
                        (record[0],),
                    )
                    assert cursor.fetchone() == record

    run(selenium_nodesock, postgres_connection_config)
