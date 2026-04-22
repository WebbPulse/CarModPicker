"""QUAL-01: car_generations JSON loader + @lru_cache memoization + shim equivalence."""


def test_load_returns_dict_with_expected_top_level_makes() -> None:
    """Loader returns a dict containing verified top-level make keys."""
    from app.core.car_generations import load_car_generations

    data = load_car_generations()
    assert isinstance(data, dict)
    # Keys verified by grep of current car_generations_data.py:
    assert "Honda" in data
    assert "Toyota" in data
    assert "BMW" in data


def test_lru_cache_single_load() -> None:
    """@lru_cache(maxsize=1) returns the SAME object reference on repeated calls."""
    from app.core.car_generations import load_car_generations

    a = load_car_generations()
    # Identity, not equality: @lru_cache(maxsize=1) must return the same object.
    assert a is load_car_generations()
    assert load_car_generations() is load_car_generations()


def test_shim_and_loader_agree() -> None:
    """CR-4: car_generations_data.CAR_GENERATIONS IS the loader's cached output."""
    from app.core.car_generations import load_car_generations
    from app.core.car_generations_data import CAR_GENERATIONS

    assert CAR_GENERATIONS is load_car_generations()


def test_json_file_exists_and_parses() -> None:
    """The JSON asset exists, is valid JSON, and includes the expected top-level makes."""
    import json
    from importlib.resources import files

    resource = files("app.core").joinpath("car_generations_data.json")
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert "Honda" in parsed
    assert "Toyota" in parsed
