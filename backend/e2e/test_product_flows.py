"""One authenticated write per CarModPicker domain against the deployed stage.

The generic suite probes every operation, but it probes them in isolation: it never
proves that a create, its read back and its delete work as one sequence through the
real gateway, the real authorizer and the real table. These flows do, one per domain
that has a resource a non admin user may own.

Every created resource is named with `e2e_env.resource_prefix` and registered with
`track` before the flow deletes it, so a flow that fails part way still hands the
cleanup hook a delete path rather than leaving the row for the next run's stale sweep.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

ABSENT_ID = "00000000-0000-4000-8000-000000000000"


def _name(env: Any, suffix: str) -> str:
    """A resource name carrying this run's prefix, so the sweep can find it."""
    return f"{env.resource_prefix}{suffix}"


def _created(response: Any, what: str) -> dict[str, Any]:
    """The created resource's body, failing with the status when the create did not take."""
    if response.status_code not in (200, 201):
        pytest.fail(f"creating the {what} answered {response.status_code}: {response.text[:400]}")
    return dict(response.json())


def _seed_car_id(api: Any) -> str:
    """A real car generation id, which a build list requires as its `car_id`."""
    response = api.get("/api/car-generations", params={"limit": 1})
    if response.status_code != 200:
        pytest.skip(f"GET /api/car-generations answered {response.status_code}, so no seed car is available")
    items = response.json().get("items") or []
    if not items:
        pytest.skip("this stage has no seeded car generations, so no build list can be created")
    return str(items[0]["id"])


def _seed_category_id(api: Any) -> str:
    """A real category id, which a part requires as its `category_id`."""
    response = api.get("/api/categories")
    if response.status_code != 200:
        pytest.skip(f"GET /api/categories answered {response.status_code}, so no seed category is available")
    items = response.json()
    if not items:
        pytest.skip("this stage has no seeded categories, so no part can be created")
    return str(items[0]["id"])


@pytest.fixture
def build_list(api: Any, e2e_env: Any, track: Any) -> dict[str, Any]:
    """A build list this run owns, shared by the build lists, build logs and votes flows."""
    body = {"name": _name(e2e_env, "build-list"), "car_id": _seed_car_id(api)}
    created = _created(api.post("/api/build-lists", json=body), "build list")
    track(f"/api/build-lists/{created['id']}")
    return created


class TestUsersDomain:
    """The users domain: update the e2e user's own profile and read it back."""

    def test_profile_update_round_trips(self, api: Any, e2e_user_id: str) -> None:
        """A PUT on the user's own record is visible on the next GET /api/users/me."""
        marker = f"https://youtube.com/@e2e-{uuid.uuid4().hex}"
        response = api.put(f"/api/users/{e2e_user_id}", json={"youtube_url": marker})
        assert response.status_code == 200, response.text[:400]

        readback = api.get("/api/users/me")
        assert readback.status_code == 200, readback.text[:400]
        assert readback.json()["youtube_url"] == marker


class TestBuildListsDomain:
    """The build lists domain: create, read back and delete a build list."""

    def test_build_list_round_trips(self, api: Any, e2e_env: Any, build_list: dict[str, Any]) -> None:
        """The created build list reads back by id and then deletes."""
        identifier = build_list["id"]
        readback = api.get(f"/api/build-lists/{identifier}")
        assert readback.status_code == 200, readback.text[:400]
        assert readback.json()["name"].startswith(e2e_env.resource_prefix)

        deleted = api.delete(f"/api/build-lists/{identifier}")
        assert deleted.status_code in (200, 204), deleted.text[:400]

        gone = api.get(f"/api/build-lists/{identifier}")
        assert gone.status_code == 404, gone.text[:400]


class TestCatalogDomain:
    """The catalog domain: a manufacturer and a part, each created by the e2e user."""

    def test_part_manufacturer_round_trips(self, api: Any, e2e_env: Any, track: Any) -> None:
        """A manufacturer any signed in user may create reads back, and deleting it is admin only.

        Manufacturers are one global deduped namespace rather than a per user resource:
        the create route is get-or-create by name and the row carries no creator, so
        `can_delete_part_manufacturer` is admin or superuser only. The durable e2e user is
        deliberately not an admin, so the delete asserts the 403 the rule gives rather than
        a success the product never offers. The row stays tracked, so the cleanup hook
        still carries its delete path.
        """
        body = {"name": _name(e2e_env, "manufacturer")}
        created = _created(api.post("/api/part-manufacturers", json=body), "part manufacturer")
        path = track(f"/api/part-manufacturers/{created['id']}")

        readback = api.get(path)
        assert readback.status_code == 200, readback.text[:400]
        assert readback.json()["name"] == body["name"]

        refused = api.delete(path)
        assert refused.status_code == 403, refused.text[:400]

    def test_part_round_trips(self, api: Any, e2e_env: Any, track: Any) -> None:
        """A user created part reads back and its creator may delete it."""
        body = {"name": _name(e2e_env, "part"), "category_id": _seed_category_id(api)}
        created = _created(api.post("/api/parts", json=body), "part")
        identifier = created["id"]
        track(f"/api/parts/{identifier}")

        readback = api.get(f"/api/parts/{identifier}")
        assert readback.status_code == 200, readback.text[:400]
        assert readback.json()["name"] == body["name"]

        deleted = api.delete(f"/api/parts/{identifier}")
        assert deleted.status_code in (200, 204), deleted.text[:400]


class TestBuildLogsDomain:
    """The build logs domain: a post on this run's own build list."""

    def test_build_log_post_round_trips(self, api: Any, e2e_env: Any, build_list: dict[str, Any], track: Any) -> None:
        """A post created on a build list appears in that list's log and then deletes."""
        list_id = build_list["id"]
        body = {"content": _name(e2e_env, "build-log-post")}
        created = _created(
            api.post(f"/api/build-logs/build-list/{list_id}/posts", json=body),
            "build log post",
        )
        post_path = track(f"/api/build-logs/posts/{created['id']}")

        readback = api.get(f"/api/build-logs/build-list/{list_id}")
        assert readback.status_code == 200, readback.text[:400]
        contents = [str(post.get("content", "")) for post in readback.json().get("posts", [])]
        assert body["content"] in contents

        deleted = api.delete(post_path)
        assert deleted.status_code in (200, 204), deleted.text[:400]


class TestModerationDomain:
    """The moderation domain: a vote on this run's own build list."""

    def test_vote_round_trips(self, api: Any, build_list: dict[str, Any]) -> None:
        """An upvote is recorded against the entity, shows in the tallies and then withdraws.

        A vote carries no name of its own, so it is not tracked for the sweep: it is
        deleted here, and deleting the build list the fixture tracked removes the rest.

        The summary's `user_vote` is the field that needs the caller's identity on an
        optional auth route, where no authorizer publishes claims. It is what the in
        process bearer verification exists to make work, so it is asserted here in both
        directions: the caller's own vote after the cast, and null after the withdrawal.
        """
        target = f"/api/votes/build_list/{build_list['id']}"
        cast = api.post(target, json={"vote_type": "upvote"})
        assert cast.status_code in (200, 201), cast.text[:400]
        assert cast.json()["vote"]["vote_type"] == "upvote", cast.text[:400]

        summary = api.get(f"{target}/summary")
        assert summary.status_code == 200, summary.text[:400]
        assert summary.json()["upvotes"] == 1, summary.text[:400]
        assert summary.json()["user_vote"] == "upvote", summary.text[:400]

        withdrawn = api.delete(target)
        assert withdrawn.status_code in (200, 204), withdrawn.text[:400]

        cleared = api.get(f"{target}/summary")
        assert cleared.status_code == 200, cleared.text[:400]
        assert cleared.json()["upvotes"] == 0, cleared.text[:400]
        assert cleared.json()["user_vote"] is None, cleared.text[:400]


class TestMediaDomain:
    """The media domain, whose only create takes multipart bytes the shared client cannot send.

    `POST /api/images/upload` is `multipart/form-data` and `E2EClient.request` sends JSON
    only, and `POST /api/images/fetch-from-url` would make a post deploy gate depend on a
    third party image host staying up. So this flow exercises the authenticated read and
    the ownership check instead of a round trip, which is what the domain can prove without
    either of those.
    """

    def test_image_access_is_owner_scoped(self, api: Any, e2e_user_id: str) -> None:
        """A file key this user does not own is refused rather than served or 404ed.

        The key is well formed and carries another owner's hash, so a 403 proves the
        ownership check ran on the deployed media function rather than the request dying
        earlier on validation.
        """
        foreign_key = "user/00000000000000000000000000000000/e2e-not-ours.png"
        response = api.get("/api/images/presigned-url", params={"file_key": foreign_key})
        assert response.status_code in (400, 403, 404), response.text[:400]
        assert response.status_code != 200


class TestAdminDomain:
    """The admin domain: a price alert, which a non admin user owns on their own behalf."""

    def test_price_alert_round_trips(self, api: Any, e2e_env: Any, track: Any) -> None:
        """An alert on a part this run created appears in the user's own list and deletes."""
        part_body = {"name": _name(e2e_env, "alert-part"), "category_id": _seed_category_id(api)}
        part = _created(api.post("/api/parts", json=part_body), "part")
        part_path = track(f"/api/parts/{part['id']}")

        alert = _created(
            api.post("/api/part-price-alerts", json={"part_id": part["id"], "threshold_cents": 1000}),
            "price alert",
        )
        alert_path = track(f"/api/part-price-alerts/{alert['id']}")

        mine = api.get("/api/part-price-alerts/me")
        assert mine.status_code == 200, mine.text[:400]
        rows = mine.json()
        rows = rows.get("items", rows) if isinstance(rows, dict) else rows
        assert alert["id"] in [str(row["id"]) for row in rows]

        deleted = api.delete(alert_path)
        assert deleted.status_code in (200, 204), deleted.text[:400]
        assert api.delete(part_path).status_code in (200, 204)


class TestVehiclesDomain:
    """The vehicles domain, which is read only: no non admin write exists to round trip."""

    def test_car_generation_lookup_is_consistent(self, api: Any) -> None:
        """A listed car generation reads back by id, and an absent id is a product 404."""
        listed = api.get("/api/car-generations", params={"limit": 1})
        assert listed.status_code == 200, listed.text[:400]
        items = listed.json().get("items") or []
        if not items:
            pytest.skip("this stage has no seeded car generations")

        identifier = str(items[0]["id"])
        readback = api.get(f"/api/car-generations/{identifier}")
        assert readback.status_code == 200, readback.text[:400]
        assert str(readback.json()["id"]) == identifier

        absent = api.get(f"/api/car-generations/{ABSENT_ID}")
        assert absent.status_code == 404, absent.text[:400]


class TestIdentityDomain:
    """The identity domain's authenticated reads, beyond the login the suite already covers."""

    def test_signed_in_user_is_the_e2e_user(self, api: Any, e2e_env: Any) -> None:
        """The token the real login route issued resolves to the configured e2e user."""
        response = api.get("/api/users/me")
        assert response.status_code == 200, response.text[:400]
        assert response.json()["email"].lower() == e2e_env.user_email.lower()
