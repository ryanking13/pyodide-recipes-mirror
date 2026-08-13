from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["psycopg"])
def test_psycopg_native_smoke(selenium):
    import psycopg
    from psycopg import conninfo, pq

    assert psycopg.pq.__impl__ == "c"
    assert pq.version() >= 180000
    assert pq.__build_version__ >= 180000

    parsed = conninfo.conninfo_to_dict(
        "host=localhost dbname=pyodide user=test_user connect_timeout=5"
    )
    assert parsed["host"] == "localhost"
    assert parsed["dbname"] == "pyodide"
    assert parsed["user"] == "test_user"
    assert parsed["connect_timeout"] == "5"

    options = {
        opt.keyword.decode(): opt.val.decode()
        for opt in pq.Conninfo.parse(b"dbname=demo application_name=pyodide")
        if opt.val is not None
    }
    assert options["dbname"] == "demo"
    assert options["application_name"] == "pyodide"
