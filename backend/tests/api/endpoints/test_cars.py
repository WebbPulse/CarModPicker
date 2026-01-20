from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.core.config import settings


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


# Helper function to create a car via admin endpoint
def create_car_via_admin(
    client: TestClient,
    admin_token: str,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a car via admin endpoint and return the created car data."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    car_data = {
        "make": make,
        "model": model,
        "generation_name": generation_name,
        "start_year": start_year,
        "end_year": end_year,
    }
    if description:
        car_data["description"] = description

    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 200, f"Failed to create car: {response.text}"
    return response.json()


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


def test_admin_create_car_success(client: TestClient, db_session: Session) -> None:
    """Test admin successfully creating a car generation."""
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
    assert response.status_code == 200, response.text
    created_car = response.json()
    assert created_car["make"] == car_data["make"]
    assert created_car["model"] == car_data["model"]
    assert created_car["generation_name"] == car_data["generation_name"]
    assert created_car["start_year"] == car_data["start_year"]
    assert created_car["end_year"] == car_data["end_year"]
    assert "id" in created_car
    # Cars no longer have user_id - they're centrally managed
    assert "user_id" not in created_car


def test_admin_create_car_unauthenticated(client: TestClient, db_session: Session) -> None:
    """Test that non-admin users cannot create cars."""
    client.cookies.clear()
    car_data = {
        "make": "Toyota",
        "model": "Corolla",
        "generation_name": "12th Gen",
        "start_year": 2019,
        "end_year": 2022,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data)
    assert response.status_code == 401  # Expect unauthorized


def test_admin_create_car_requires_admin(client: TestClient, db_session: Session) -> None:
    """Test that regular users cannot create cars even when authenticated."""
    _, token = create_and_login_user(client, "regular_user_car", db_session)
    headers = get_auth_headers(token)

    car_data = {
        "make": "Toyota",
        "model": "Corolla",
        "generation_name": "12th Gen",
        "start_year": 2019,
        "end_year": 2022,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 403  # Expect forbidden (not admin)


def test_read_car_success(client: TestClient, db_session: Session) -> None:
    """Test reading a car (public endpoint)."""
    _, admin_token = create_and_login_admin_user(client, db_session, "reader")
    car = create_car_via_admin(client, admin_token, "Mazda", "3", "4th Gen", 2019, 2023)

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


def test_admin_update_car_success(client: TestClient, db_session: Session) -> None:
    """Test admin successfully updating a car."""
    _, admin_token = create_and_login_admin_user(client, db_session, "updater")
    headers = get_auth_headers(admin_token)

    # Create a car first
    car = create_car_via_admin(client, admin_token, "Nissan", "Altima", "5th Gen", 2019, 2020)
    car_id = car["id"]

    # Update the car
    update_payload = {"model": "Maxima", "generation_name": "8th Gen"}
    response = client.put(f"{settings.API_STR}/cars/admin/cars/{car_id}", json=update_payload, headers=headers)
    assert response.status_code == 200, response.text
    updated_car = response.json()
    assert updated_car["model"] == update_payload["model"]
    assert updated_car["generation_name"] == update_payload["generation_name"]
    assert updated_car["make"] == car["make"]  # Make should be unchanged
    # Cars no longer have user_id - they're centrally managed
    assert "user_id" not in updated_car


def test_admin_delete_car_success(client: TestClient, db_session: Session) -> None:
    """Test admin successfully deleting a car."""
    _, admin_token = create_and_login_admin_user(client, db_session, "deleter")
    headers = get_auth_headers(admin_token)

    # Create a car first
    car = create_car_via_admin(client, admin_token, "Kia", "Stinger", "1st Gen", 2018, 2023)
    car_id = car["id"]

    # Delete the car
    response = client.delete(f"{settings.API_STR}/cars/admin/cars/{car_id}", headers=headers)
    assert response.status_code == 200, response.text

    # Verify car is deleted
    get_response = client.get(f"{settings.API_STR}/cars/{car_id}")
    assert get_response.status_code == 404


def test_admin_delete_car_with_build_lists_unlinks(client: TestClient, db_session: Session) -> None:
    """Test that deleting a car with build lists unlinks them (sets car_id to null) instead of failing."""

    _, admin_token = create_and_login_admin_user(client, db_session, "deleter_with_bl")
    headers = get_auth_headers(admin_token)

    # Create a car
    car = create_car_via_admin(client, admin_token)
    car_id = car["id"]

    # Create a build list for this car (requires a user)
    _, user_token = create_and_login_user(client, "builder", db_session)
    user_headers = get_auth_headers(user_token)

    build_list_data = {
        "name": "Test Build List",
        "description": "Test",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=user_headers)
    assert response.status_code == 200
    build_list_id = response.json()["id"]

    # Delete the car - should succeed and unlink the build list
    response = client.delete(f"{settings.API_STR}/cars/admin/cars/{car_id}", headers=headers)
    assert response.status_code == 200

    # Verify the build list still exists but car_id is now null
    response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}", headers=user_headers)
    assert response.status_code == 200
    build_list = response.json()
    assert build_list["id"] == build_list_id
    assert build_list["car_id"] is None, "Build list car_id should be null after car deletion"


def test_get_cars_by_make_success(client: TestClient, db_session: Session) -> None:
    """Test getting cars by make."""
    _, admin_token = create_and_login_admin_user(client, db_session, "make_user")

    # Create Toyota cars
    create_car_via_admin(client, admin_token, "Toyota", "Camry", "8th Gen", 2018, 2024)
    create_car_via_admin(client, admin_token, "Toyota", "Corolla", "12th Gen", 2019, 2022)
    create_car_via_admin(client, admin_token, "Honda", "Civic", "10th Gen", 2016, 2021)

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
    _, admin_token = create_and_login_admin_user(client, db_session, "make_model_user")

    # Create Honda Civics
    create_car_via_admin(client, admin_token, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_via_admin(client, admin_token, "Honda", "Civic", "11th Gen", 2022, 2024)
    create_car_via_admin(client, admin_token, "Honda", "Accord", "10th Gen", 2018, 2022)

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
    _, admin_token = create_and_login_admin_user(client, db_session, "search_user")

    # Create cars with searchable names
    create_car_via_admin(client, admin_token, "Tesla", "Model 3", "1st Gen", 2017, 2023)
    create_car_via_admin(client, admin_token, "Toyota", "Corolla", "12th Gen", 2019, 2022)

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
    _, admin_token = create_and_login_admin_user(client, db_session, "search_model_user")

    # Create cars with specific models
    create_car_via_admin(client, admin_token, "BMW", "M3", "G80", 2021, 2024)
    _ = create_car_via_admin(client, admin_token, "BMW", "M4", "G82", 2021, 2024)["id"]

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
    import os

    _, admin_token = create_and_login_admin_user(client, db_session, f"stats_test_{os.getpid()}")

    # Create cars with different makes
    create_car_via_admin(client, admin_token, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_via_admin(client, admin_token, "Honda", "Accord", "10th Gen", 2018, 2022)
    create_car_via_admin(client, admin_token, "Toyota", "Camry", "8th Gen", 2018, 2024)

    client.cookies.clear()

    # Get make statistics
    response = client.get(f"{settings.API_STR}/cars/stats/makes")
    assert response.status_code == 200

    stats = response.json()
    assert isinstance(stats, dict)
    # Should have at least Honda and Toyota
    assert "Honda" in stats or "Toyota" in stats


def test_create_car_invalid_year_range(client: TestClient, db_session: Session) -> None:
    """Test that creating a car with invalid year range fails."""
    _, admin_token = create_and_login_admin_user(client, db_session, "invalid_year")
    headers = get_auth_headers(admin_token)

    car_data = {
        "make": "Honda",
        "model": "Civic",
        "generation_name": "Test Gen",
        "start_year": 2021,  # start_year > end_year
        "end_year": 2020,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 400
    response_data = response.json()
    # Error response might be in "detail" field or as a message
    error_text = response_data.get("detail", response_data.get("message", "")).lower()
    assert "start_year" in error_text


def test_admin_delete_all_cars_success(client: TestClient, db_session: Session) -> None:
    """Test admin successfully deleting all cars."""
    _, admin_token = create_and_login_admin_user(client, db_session, "delete_all")
    headers = get_auth_headers(admin_token)

    # Create multiple cars
    car1 = create_car_via_admin(client, admin_token, "Honda", "Civic", "10th Gen", 2016, 2021)
    car2 = create_car_via_admin(client, admin_token, "Toyota", "Camry", "8th Gen", 2018, 2024)
    car3 = create_car_via_admin(client, admin_token, "Mazda", "3", "4th Gen", 2019, 2023)

    # Delete all cars
    response = client.delete(f"{settings.API_STR}/cars/admin/cars", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert "message" in result
    assert "deleted_count" in result
    assert "unlinked_build_lists" in result
    assert result["deleted_count"] >= 3
    assert isinstance(result["unlinked_build_lists"], int)
    assert result["unlinked_build_lists"] >= 0

    # Verify all cars are deleted
    for car_id in [car1["id"], car2["id"], car3["id"]]:
        get_response = client.get(f"{settings.API_STR}/cars/{car_id}")
        assert get_response.status_code == 404


def test_admin_delete_all_cars_with_build_lists_unlinks(client: TestClient, db_session: Session) -> None:
    """Test that deleting all cars with build lists unlinks them (sets car_id to null)."""
    _, admin_token = create_and_login_admin_user(client, db_session, "delete_all_with_bl")
    headers = get_auth_headers(admin_token)

    # Create a car
    car = create_car_via_admin(client, admin_token)
    car_id = car["id"]

    # Create build lists for this car
    _, user_token = create_and_login_user(client, "builder_all", db_session)
    user_headers = get_auth_headers(user_token)

    build_list_data1 = {
        "name": "Test Build List 1",
        "description": "Test",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data1, headers=user_headers)
    assert response.status_code == 200
    build_list_id1 = response.json()["id"]

    build_list_data2 = {
        "name": "Test Build List 2",
        "description": "Test",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data2, headers=user_headers)
    assert response.status_code == 200
    build_list_id2 = response.json()["id"]

    # Delete all cars - should succeed and unlink the build lists
    response = client.delete(f"{settings.API_STR}/cars/admin/cars", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert result["unlinked_build_lists"] >= 2

    # Verify the build lists still exist but car_id is now null
    for build_list_id in [build_list_id1, build_list_id2]:
        response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}", headers=user_headers)
        assert response.status_code == 200
        build_list = response.json()
        assert build_list["id"] == build_list_id
        assert build_list["car_id"] is None, "Build list car_id should be null after deleting all cars"


def test_admin_delete_all_cars_requires_admin(client: TestClient, db_session: Session) -> None:
    """Test that regular users cannot delete all cars even when authenticated."""
    _, token = create_and_login_user(client, "regular_user_delete_all", db_session)
    headers = get_auth_headers(token)

    response = client.delete(f"{settings.API_STR}/cars/admin/cars", headers=headers)
    assert response.status_code == 403  # Expect forbidden (not admin)


def test_admin_delete_all_cars_unauthenticated(client: TestClient, db_session: Session) -> None:
    """Test that unauthenticated users cannot delete all cars."""
    client.cookies.clear()
    response = client.delete(f"{settings.API_STR}/cars/admin/cars")
    assert response.status_code == 401  # Expect unauthorized


def test_count_cars_success(client: TestClient, db_session: Session) -> None:
    """Test counting cars."""
    # Get initial count (public endpoint, no auth required)
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    initial_data = response.json()
    assert "count" in initial_data
    initial_count = initial_data["count"]
    assert isinstance(initial_count, int)
    assert initial_count >= 0

    # Create a car as admin
    _, admin_token = create_and_login_admin_user(client, db_session, "count_creator")
    car = create_car_via_admin(client, admin_token, "Tesla", "Model 3", "1st Gen", 2017, 2023)

    # Count again (should be increased by 1)
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    updated_data = response.json()
    assert "count" in updated_data
    assert updated_data["count"] == initial_count + 1

    # Delete the car
    headers = get_auth_headers(admin_token)
    response = client.delete(f"{settings.API_STR}/cars/admin/cars/{car['id']}", headers=headers)
    assert response.status_code == 200

    # Count again (should be back to initial count)
    response = client.get(f"{settings.API_STR}/cars/count")
    assert response.status_code == 200
    final_data = response.json()
    assert final_data["count"] == initial_count


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
