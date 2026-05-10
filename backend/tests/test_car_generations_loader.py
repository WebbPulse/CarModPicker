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


def test_seed_directory_exists_and_each_file_parses() -> None:
    """Per-make JSON files all parse and merge into a dict containing expected makes."""
    import json
    from importlib.resources import files

    seed_dir = files("app.core").joinpath("car_generations_seed")
    merged: dict = {}
    file_count = 0
    for entry in seed_dir.iterdir():
        if not entry.name.endswith(".json"):
            continue
        file_count += 1
        payload = json.loads(entry.read_text(encoding="utf-8"))
        # Each per-make file is a single-key dict.
        assert len(payload) == 1, f"{entry.name} should have exactly one make key"
        merged.update(payload)
    assert file_count >= 40, f"expected at least 40 per-make files, got {file_count}"
    assert "Honda" in merged
    assert "Toyota" in merged
    assert "Plymouth" in merged  # Recently added — guards against accidental file deletion.
    assert "Chrysler" in merged
