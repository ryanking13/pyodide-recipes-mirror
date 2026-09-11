from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["coolname"])
def test_coolname(selenium):
    from coolname import generate, generate_slug, get_combinations_count, RandomGenerator

    words = generate()
    assert list
    assert isinstance(words, list)
    assert all(isinstance(word, str) for word in words)
    assert not any('-' in word for word in words)

    name = generate_slug()
    assert isinstance(name, str)
    assert '-' in name
    assert not name.startswith('-')
    assert not name.endswith('-')
    
    name = generate_slug(4)
    assert isinstance(name, str)
    assert '-' in name
    assert not name.startswith('-')
    assert not name.endswith('-')
    assert len(name.split('-')) >= 4

    n = get_combinations_count(4)
    assert isinstance(n, int)
    assert n > 10 ** 10

    generator = RandomGenerator({
        'all': {
          'type': 'cartesian',
          'lists': ['first_name', 'last_name']
        },
        'first_name': {
          'type': 'words',
          'words': ['james', 'john']
        },
        'last_name': {
          'type': 'words',
          'words': ['smith', 'brown']
        }
    })
    name = generator.generate_slug()
    assert isinstance(name, str)
    assert '-' in name
    assert not name.startswith('-')
    assert not name.endswith('-')
    assert len(name.split('-')) == 2
