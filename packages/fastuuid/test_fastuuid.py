from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["fastuuid"])
def test_fastuuid(selenium):
    import pytest
    from fastuuid import UUID, uuid1, uuid3, uuid4, uuid5, uuid7, uuid_v1mc
    import re
    import uuid
    UUID_REGEX = re.compile("[0-F]{8}-([0-F]{4}-){3}[0-F]{12}", re.I)


    with pytest.raises(
        TypeError,
        match="one of the hex, bytes, bytes_le, fields, or int arguments must be given",
    ):
        UUID()

    expected = uuid4()
    actual = UUID(str(expected))
    other = uuid4()

    assert expected == actual
    assert expected != other
    a = UUID(int=10)
    b = UUID(int=20)
    c = UUID(int=20)

    assert a < b
    assert b > a
    assert a <= b
    assert b >= a
    assert c <= c
    assert c >= c

    expected = uuid_v1mc()
    assert expected.version == 1
    assert expected.variant == "specified in RFC 4122"
    assert UUID_REGEX.match(str(expected))
    assert str(expected) == str(uuid.UUID(str(expected)))

    expected = uuid3(uuid4(), b"foo")
    assert expected.version == 3
    assert expected.variant == "specified in RFC 4122"
    assert UUID_REGEX.match(str(expected))
    assert str(expected) == str(uuid.UUID(str(expected)))

    expected = uuid4()
    assert expected.version == 4
    assert expected.variant == "specified in RFC 4122"
    assert UUID_REGEX.match(str(expected))
    assert str(expected) == str(uuid.UUID(str(expected)))

    expected = uuid5(uuid4(), b"foo")
    assert expected.version == 5
    assert expected.variant == "specified in RFC 4122"
    assert UUID_REGEX.match(str(expected))
    assert str(expected) == str(uuid.UUID(str(expected)))

    expected = uuid7()
    assert expected.version == 7
    assert expected.variant == "specified in RFC 4122"
    assert UUID_REGEX.match(str(expected))
    assert str(expected) == str(uuid.UUID(str(expected)))
