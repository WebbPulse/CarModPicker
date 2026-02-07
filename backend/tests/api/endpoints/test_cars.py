from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.core.config import settings
from tests.conftest import create_car_in_db


# Helper function to create and login an admin user
def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_car_test_{username_suffix}"
    email = f"admin_car_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
    admin_user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_admin=True,
        is_superuser=False,
        email_verified=True,
        disabled=False,
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    # Log in and get token
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login admin user: {token_response.text}"
    token = token_response.json()["access_token"]

    return admin_user.__dict__, token


# Helper function to create a user and log them in (returns user_id and token)
def create_and_login_user(
    client: TestClient, username_suffix: str, db_session: Session | None = None
) -> tuple[int, str]:  # Returns (user_id, token)
    username = f"car_test_user_{username_suffix}"
    email = f"car_test_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_info = response.json()
        user_id = user_info["id"]

        # Manually verify the email for testing purposes
        from app.api.models.user import User

        if db_session:
            user = db_session.query(User).filter(User.username == username).first()
            if user:
                user.email_verified = True
                db_session.commit()
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()  # Raise an exception for other errors

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    token_data = token_response.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    if user_id == -1:  # If user existed and was not created, fetch ID
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(f"Could not retrieve user_id for existing user {username} via /users/me.")

    if user_id == -1:
        raise Exception(f"User ID for {username} could not be determined.")
    return (user_id, token)


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


# --- Test Cases ---


def test_admin_create_car_removed(client: TestClient, db_session: Session) -> None:
    """Cars are seeded from backend source; admin create endpoint is removed."""
    _, admin_token = create_and_login_admin_user(client, db_session, "creator")
    headers = get_auth_headers(admin_token)
    car_data = {
        "make": "Honda",
        "model": "Civic",
        "generation_name": "10th Gen",
        "start_year": 2016,
        "end_year": 2021,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code in (404, 405)  # Endpoint removed (404 path not found or 405 method not allowed)


def test_read_car_success(client: TestClient, db_session: Session) -> None:
    """Test reading a car (public endpoint)."""
    car = create_car_in_db(db_session, "Mazda", "3", "4th Gen", 2019, 2023)

    # Reading a car is public, no auth needed
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/{car['id']}")
    assert response.status_code == 200, response.text
    read_car_data = response.json()
    assert read_car_data["id"] == car["id"]
    assert read_car_data["make"] == car["make"]
    assert read_car_data["model"] == car["model"]
    assert read_car_data["generation_name"] == car["generation_name"]
    # Cars no longer have user_id
    assert "user_id" not in read_car_data


def test_read_car_not_found(client: TestClient, db_session: Session) -> None:
    """Test reading a non-existent car."""
    response = client.get(f"{settings.API_STR}/cars/999999")  # Non-existent ID
    assert response.status_code == 404


def test_get_cars_by_make_success(client: TestClient, db_session: Session) -> None:
    """Test getting cars by make."""
    # Create cars in DB (cars are seeded from backend source; tests use create_car_in_db)
    create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)
    create_car_in_db(db_session, "Toyota", "Corolla", "12th Gen", 2019, 2022)
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)

    client.cookies.clear()

    # Get cars by make "Toyota"
    response = client.get(f"{settings.API_STR}/cars/make/Toyota")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert isinstance(cars, list)
    assert len(cars) >= 2

    for car in cars:
        assert car["make"] == "Toyota"


def test_get_cars_by_make_no_results(client: TestClient, db_session: Session) -> None:
    """Test getting cars by make with no results."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/cars/make/NonExistentMake")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert isinstance(cars, list)
    assert len(cars) == 0


def test_get_cars_by_make_model_success(client: TestClient, db_session: Session) -> None:
    """Test getting cars by make and model."""
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_in_db(db_session, "Honda", "Civic", "11th Gen", 2022, 2024)
    create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

    client.cookies.clear()

    # Get Honda Civics
    response = client.get(f"{settings.API_STR}/cars/make/Honda/model/Civic")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert isinstance(cars, list)
    assert len(cars) >= 2

    for car in cars:
        assert car["make"] == "Honda"
        assert car["model"] == "Civic"


def test_search_cars_by_make(client: TestClient, db_session: Session) -> None:
    """Test searching cars by make."""
    create_car_in_db(db_session, "Tesla", "Model 3", "1st Gen", 2017, 2023)
    create_car_in_db(db_session, "Toyota", "Corolla", "12th Gen", 2019, 2022)

    client.cookies.clear()

    # Search for "Tesla"
    response = client.get(f"{settings.API_STR}/cars/search?q=Tesla")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert isinstance(cars, list)
    assert len(cars) >= 1

    # Verify Tesla cars are in results
    tesla_found = any(car["make"] == "Tesla" for car in cars)
    assert tesla_found


def test_search_cars_by_model(client: TestClient, db_session: Session) -> None:
    """Test searching cars by model."""
    create_car_in_db(db_session, "BMW", "M3", "G80", 2021, 2024)
    create_car_in_db(db_session, "BMW", "M4", "G82", 2021, 2024)

    client.cookies.clear()

    # Search for "M3"
    response = client.get(f"{settings.API_STR}/cars/search?q=M3")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert len(cars) >= 1

    # Verify M3 is in results
    m3_found = any(car["model"] == "M3" for car in cars)
    assert m3_found


def test_search_cars_no_query(client: TestClient, db_session: Session) -> None:
    """Test search without query parameter."""
    client.cookies.clear()

    # The search endpoint requires a 'q' parameter
    response = client.get(f"{settings.API_STR}/cars/search")
    assert response.status_code == 422  # Validation error for missing required param


def test_search_cars_no_results(client: TestClient, db_session: Session) -> None:
    """Test search with no matching results."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/cars/search?q=NonExistentCarBrandXYZ123")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()
    assert isinstance(cars, list)
    assert len(cars) == 0


def test_get_car_make_stats(client: TestClient, db_session: Session) -> None:
    """Test getting car make statistics."""
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)
    create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

    client.cookies.clear()

    # Get make statistics
    response = client.get(f"{settings.API_STR}/cars/stats/makes")
    assert response.status_code == 200

    stats = response.json()
    assert isinstance(stats, dict)
    # Should have at least Honda and Toyota
    assert "Honda" in stats or "Toyota" in stats


def test_count_makes(client: TestClient, db_session: Session) -> None:
    """Test counting makes (Make entities)."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/cars/makes/count")
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0


def test_count_car_models(client: TestClient, db_session: Session) -> None:
    """Test counting car models (CarModel entities)."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/cars/car-models/count")
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0


def test_admin_car_write_endpoints_removed(client: TestClient, db_session: Session) -> None:
    """Cars are seeded from backend source; admin write endpoints are removed (405)."""
    car = create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    _, admin_token = create_and_login_admin_user(client, db_session, "write_removed")
    headers = get_auth_headers(admin_token)
    # PUT and DELETE should return 405
    response = client.put(
        f"{settings.API_STR}/cars/admin/cars/{car['id']}",
        json={"model": "Civic Si"},
        headers=headers,
    )
    assert response.status_code in (404, 405)
    response = client.delete(f"{settings.API_STR}/cars/admin/cars/{car['id']}", headers=headers)
    assert response.status_code in (404, 405)
    response = client.delete(f"{settings.API_STR}/cars/admin/cars", headers=headers)
    assert response.status_code in (404, 405)


def test_count_cars_success(client: TestClient, db_session: Session) -> None:
    """Test counting cars."""
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    initial_data = response.json()
    assert "count" in initial_data
    initial_count = initial_data["count"]
    assert isinstance(initial_count, int)
    assert initial_count >= 0

    car = create_car_in_db(db_session, "Tesla", "Model 3", "1st Gen", 2017, 2023)
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    assert response.json()["count"] == initial_count + 1

    # Remove car via DB (no delete API)
    from app.api.models.car import Car

    db_session.query(Car).filter(Car.id == car["id"]).delete()
    db_session.commit()
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    assert response.json()["count"] == initial_count


def test_count_cars_public_endpoint(client: TestClient, db_session: Session) -> None:
    """Test that counting cars works without authentication."""
    # Count cars (public endpoint, no auth required)
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0
