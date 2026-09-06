# Parallel Testing Setup

The backend test suite runs under `pytest-xdist`; always pass `-n auto`.

## How isolation works

Every table lives in DynamoDB. Tests never touch AWS: the `dynamo_tables`
fixture in `backend/tests/conftest.py` starts `moto`'s `mock_aws()` context,
creates every table from `app/db/dynamo/tables.py`, and tears the mock down
afterwards. Each test therefore starts with empty tables, and each xdist
worker is a separate process with its own mock, so workers cannot see each
other's data.

The `db_session` fixture is a small marker object that depends on
`dynamo_tables`. It exists so tests can order their setup and derive unique
names with `id(db_session)`; it has no database behaviour of its own. The
`client` fixture gives you a `TestClient` bound to the same mocked tables.

## Commands

```bash
cd backend
pytest -n auto                              # whole suite, parallel
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto tests/api/endpoints/test_auth.py
pytest -n auto -k "test_name"
pytest -n 0                                 # sequential, for debugging
```

Rate limiting is disabled in tests by default; set `ENABLE_RATE_LIMITING=true`
to exercise it.

## Writing tests

- Depend on `dynamo_tables` (directly or through `client` / `db_session`)
  whenever a test reads or writes through a repository.
- Create data through the repositories in `app/db/dynamo/`, or the helpers in
  `tests/conftest.py` (`save_catalog`, `create_car_in_db`,
  `create_and_login_user`, ...).
- Keep tests independent: nothing persists between tests, and nothing is
  shared between workers.
