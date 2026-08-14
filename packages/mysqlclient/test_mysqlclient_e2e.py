# MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD=password \
# MYSQL_CA_FILE=/path/to/mysql-ca.pem pytest -m db --runner=selenium --rt node \
# packages/mysqlclient/test_mysqlclient_e2e.py

import os
from pathlib import Path

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node


@pytest.fixture(scope="module")
def mysql_connection_config():
    required_names = [
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_CA_FILE",
    ]
    missing = [name for name in required_names if not os.environ.get(name)]
    if missing:
        pytest.fail(
            "Missing required MySQL test environment variables: " + ", ".join(missing)
        )

    ca_file = Path(os.environ["MYSQL_CA_FILE"])
    if not ca_file.is_file():
        pytest.fail(f"MySQL CA file does not exist: {ca_file}")

    return {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ["MYSQL_PORT"]),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "ca_pem": ca_file.read_text(encoding="utf-8"),
    }


@pytest.mark.db
@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@only_node
def test_mysqlclient_database_driver_e2e(selenium_nodesock, mysql_connection_config):
    @run_in_pyodide(packages=["mysqlclient"])
    def run(selenium, config):
        import uuid
        from contextlib import closing
        from pathlib import Path

        import MySQLdb

        ca_path = Path("/tmp/mysql-ca.pem")
        ca_path.write_text(config["ca_pem"], encoding="utf-8")

        def connect(*, ssl_mode, ssl=None):
            return MySQLdb.connect(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                passwd=config["password"],
                autocommit=True,
                ssl_mode=ssl_mode,
                ssl=ssl,
            )

        def assert_tls_state(connection, tls_expected):
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT 42")
                assert cursor.fetchone() == (42,)
                cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
                ssl_status = cursor.fetchone()
                assert ssl_status[0] == "Ssl_cipher"
                cipher = ssl_status[1] or ""
                if tls_expected:
                    assert cipher
                else:
                    assert cipher == ""

        with closing(connect(ssl_mode="DISABLED")) as connection:
            assert_tls_state(connection, tls_expected=False)

        with closing(connect(ssl_mode="REQUIRED")) as connection:
            assert_tls_state(connection, tls_expected=True)

        verify_connection = connect(
            ssl_mode="VERIFY_CA",
            ssl={"ca": str(ca_path)},
        )
        db_name = f"pyodide_mysqlclient_e2e_{uuid.uuid4().hex[:12]}"
        table_name = f"records_{uuid.uuid4().hex[:12]}"
        try:
            assert_tls_state(verify_connection, tls_expected=True)
            with closing(verify_connection.cursor()) as cursor:
                cursor.execute(f"CREATE DATABASE `{db_name}`")
                cursor.execute(f"USE `{db_name}`")
                cursor.execute(
                    f"CREATE TABLE `{table_name}` (id INTEGER PRIMARY KEY, label VARCHAR(64), amount INTEGER)"
                )
                row = (7, "verified tls", 42)
                cursor.execute(
                    f"INSERT INTO `{table_name}` (id, label, amount) VALUES (%s, %s, %s)",
                    row,
                )
                cursor.execute(
                    f"SELECT id, label, amount FROM `{table_name}` WHERE id = %s",
                    (row[0],),
                )
                assert cursor.fetchone() == row
                cursor.execute(f"DROP TABLE `{table_name}`")
        finally:
            with closing(verify_connection.cursor()) as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            verify_connection.close()

    run(selenium_nodesock, mysql_connection_config)
