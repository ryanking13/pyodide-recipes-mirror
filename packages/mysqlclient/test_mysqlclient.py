from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["mysqlclient"])
def test_mysqlclient_native_smoke(selenium):
    import MySQLdb
    import MySQLdb._mysql

    assert MySQLdb._mysql.version_info == MySQLdb.version_info

    client_info = MySQLdb.get_client_info()
    assert isinstance(client_info, str)
