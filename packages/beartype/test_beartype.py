from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["beartype"])
def test_beartype(selenium):
    from beartype import beartype
    from beartype.roar import BeartypeException

    @beartype
    def test1() -> int:
        return 5
    test1()

    try:
        @beartype
        def test2() -> int:
            return 'notInt'
        test2()
        assert False
    except BeartypeException:
        pass
