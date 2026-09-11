from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["asyncpg"])
def test_asyncpg_native_modules(selenium):
    # Just a smoke test.
    # see e2e tests for a more comprehensive test
    from asyncpg.pgproto import pgproto
    from asyncpg.protocol import protocol, record

    assert pgproto.__file__.endswith(".so")
    assert protocol.__file__.endswith(".so")
    assert record.__file__.endswith(".so")
