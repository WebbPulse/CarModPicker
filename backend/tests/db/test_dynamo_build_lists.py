from typing import Any
from uuid import uuid4

import pytest

from app.db.dynamo.build_lists import (
    BuildList,
    BuildListLaborEstimate,
    BuildListLaborEstimateRepository,
    BuildListPart,
    BuildListPartRepository,
    BuildListPhase,
    BuildListPhaseRepository,
    BuildListRepository,
    delete_build_list_cascade,
)
from app.db.dynamo.repository import transact_write


@pytest.fixture
def build_lists(dynamo_tables: Any) -> BuildListRepository:
    return BuildListRepository()


@pytest.fixture
def parts(dynamo_tables: Any) -> BuildListPartRepository:
    return BuildListPartRepository()


@pytest.fixture
def phases(dynamo_tables: Any) -> BuildListPhaseRepository:
    return BuildListPhaseRepository()


@pytest.fixture
def labor_estimates(dynamo_tables: Any) -> BuildListLaborEstimateRepository:
    return BuildListLaborEstimateRepository()


def test_create_and_get_build_list(build_lists: BuildListRepository) -> None:
    user_id = uuid4()
    created = build_lists.create(BuildList(name="LS Swap", user_id=user_id, base_price_cents=500_000))

    fetched = build_lists.get(created.id)

    assert fetched is not None
    assert fetched.name == "LS Swap"
    assert fetched.user_id == user_id
    assert fetched.base_price_cents == 500_000


def test_list_by_user_returns_only_that_users_lists(build_lists: BuildListRepository) -> None:
    owner = uuid4()
    other = uuid4()
    build_lists.create(BuildList(name="Mine A", user_id=owner))
    build_lists.create(BuildList(name="Mine B", user_id=owner))
    build_lists.create(BuildList(name="Theirs", user_id=other))

    page = build_lists.list_by_user(owner)

    assert {item.name for item in page.items} == {"Mine A", "Mine B"}


def test_list_by_user_paginates_with_a_cursor(build_lists: BuildListRepository) -> None:
    owner = uuid4()
    for index in range(3):
        build_lists.create(BuildList(name=f"List {index}", user_id=owner))

    first = build_lists.list_by_user(owner, limit=2)
    assert len(first.items) == 2
    assert first.next_cursor is not None

    second = build_lists.list_by_user(owner, limit=2, cursor=first.next_cursor)
    assert len(second.items) == 1
    assert second.next_cursor is None

    seen = {item.id for item in first.items} | {item.id for item in second.items}
    assert len(seen) == 3


def test_list_by_car(build_lists: BuildListRepository) -> None:
    car_id = uuid4()
    build_lists.create(BuildList(name="For this car", user_id=uuid4(), car_id=car_id))
    build_lists.create(BuildList(name="For another", user_id=uuid4(), car_id=uuid4()))

    page = build_lists.list_by_car(car_id)

    assert [item.name for item in page.items] == ["For this car"]


def test_phases_come_back_in_sort_order(phases: BuildListPhaseRepository) -> None:
    build_list_id = uuid4()
    phases.create(BuildListPhase(build_list_id=build_list_id, name="Third", sort_order=3))
    phases.create(BuildListPhase(build_list_id=build_list_id, name="First", sort_order=1))
    phases.create(BuildListPhase(build_list_id=build_list_id, name="Second", sort_order=2))

    ordered = phases.ordered_for_build_list(build_list_id)

    assert [phase.name for phase in ordered] == ["First", "Second", "Third"]


def test_labor_estimates_come_back_in_sort_order(
    labor_estimates: BuildListLaborEstimateRepository,
) -> None:
    build_list_id = uuid4()
    labor_estimates.create(BuildListLaborEstimate(build_list_id=build_list_id, name="Paint", sort_order=2))
    labor_estimates.create(BuildListLaborEstimate(build_list_id=build_list_id, name="Tune", sort_order=1))

    ordered = labor_estimates.ordered_for_build_list(build_list_id)

    assert [estimate.name for estimate in ordered] == ["Tune", "Paint"]


def test_child_rows_scope_to_their_build_list(parts: BuildListPartRepository) -> None:
    mine = uuid4()
    theirs = uuid4()
    parts.create(BuildListPart(build_list_id=mine, part_id=uuid4(), added_by=uuid4()))
    parts.create(BuildListPart(build_list_id=theirs, part_id=uuid4(), added_by=uuid4()))

    assert len(parts.all_for_build_list(mine)) == 1
    assert len(parts.all_for_build_list(theirs)) == 1


def test_list_for_part_finds_every_build_list_using_it(parts: BuildListPartRepository) -> None:
    part_id = uuid4()
    parts.create(BuildListPart(build_list_id=uuid4(), part_id=part_id, added_by=uuid4()))
    parts.create(BuildListPart(build_list_id=uuid4(), part_id=part_id, added_by=uuid4()))
    parts.create(BuildListPart(build_list_id=uuid4(), part_id=uuid4(), added_by=uuid4()))

    page = parts.list_for_part(part_id)

    assert len(page.items) == 2


def test_clear_phase_detaches_parts_but_keeps_them(parts: BuildListPartRepository) -> None:
    build_list_id = uuid4()
    phase_id = uuid4()
    attached = parts.create(
        BuildListPart(
            build_list_id=build_list_id,
            part_id=uuid4(),
            added_by=uuid4(),
            build_list_phase_id=phase_id,
        )
    )
    untouched = parts.create(
        BuildListPart(
            build_list_id=build_list_id,
            part_id=uuid4(),
            added_by=uuid4(),
            build_list_phase_id=uuid4(),
        )
    )

    transact_write(parts.clear_phase(phase_id, build_list_id))

    assert parts.get_or_raise(attached.id).build_list_phase_id is None
    assert parts.get_or_raise(untouched.id).build_list_phase_id is not None


def test_clear_phase_detaches_labor_estimates(
    labor_estimates: BuildListLaborEstimateRepository,
) -> None:
    build_list_id = uuid4()
    phase_id = uuid4()
    estimate = labor_estimates.create(
        BuildListLaborEstimate(build_list_id=build_list_id, name="Install", build_list_phase_id=phase_id)
    )

    transact_write(labor_estimates.clear_phase(phase_id, build_list_id))

    assert labor_estimates.get_or_raise(estimate.id).build_list_phase_id is None


def test_delete_cascade_removes_the_list_and_all_children(
    build_lists: BuildListRepository,
    parts: BuildListPartRepository,
    phases: BuildListPhaseRepository,
    labor_estimates: BuildListLaborEstimateRepository,
) -> None:
    build_list = build_lists.create(BuildList(name="Doomed", user_id=uuid4()))
    parts.create(BuildListPart(build_list_id=build_list.id, part_id=uuid4(), added_by=uuid4()))
    phases.create(BuildListPhase(build_list_id=build_list.id, name="Phase 1"))
    labor_estimates.create(BuildListLaborEstimate(build_list_id=build_list.id, name="Labor"))

    delete_build_list_cascade(
        build_list.id,
        build_lists=build_lists,
        parts=parts,
        phases=phases,
        labor_estimates=labor_estimates,
    )

    assert build_lists.get(build_list.id) is None
    assert parts.all_for_build_list(build_list.id) == []
    assert phases.all_for_build_list(build_list.id) == []
    assert labor_estimates.all_for_build_list(build_list.id) == []


def test_delete_cascade_leaves_other_build_lists_alone(
    build_lists: BuildListRepository,
    parts: BuildListPartRepository,
    phases: BuildListPhaseRepository,
    labor_estimates: BuildListLaborEstimateRepository,
) -> None:
    doomed = build_lists.create(BuildList(name="Doomed", user_id=uuid4()))
    survivor = build_lists.create(BuildList(name="Survivor", user_id=uuid4()))
    parts.create(BuildListPart(build_list_id=doomed.id, part_id=uuid4(), added_by=uuid4()))
    kept = parts.create(BuildListPart(build_list_id=survivor.id, part_id=uuid4(), added_by=uuid4()))

    delete_build_list_cascade(
        doomed.id,
        build_lists=build_lists,
        parts=parts,
        phases=phases,
        labor_estimates=labor_estimates,
    )

    assert build_lists.get(survivor.id) is not None
    assert [item.id for item in parts.all_for_build_list(survivor.id)] == [kept.id]


def test_delete_cascade_falls_back_to_batches_past_the_transaction_cap(
    build_lists: BuildListRepository,
    parts: BuildListPartRepository,
    phases: BuildListPhaseRepository,
    labor_estimates: BuildListLaborEstimateRepository,
) -> None:
    """A build list with more than 100 children exceeds the transaction limit."""
    build_list = build_lists.create(BuildList(name="Huge", user_id=uuid4()))
    for _ in range(101):
        parts.create(BuildListPart(build_list_id=build_list.id, part_id=uuid4(), added_by=uuid4()))

    delete_build_list_cascade(
        build_list.id,
        build_lists=build_lists,
        parts=parts,
        phases=phases,
        labor_estimates=labor_estimates,
    )

    assert build_lists.get(build_list.id) is None
    assert parts.all_for_build_list(build_list.id) == []


def test_count_reflects_stored_build_lists(build_lists: BuildListRepository) -> None:
    assert build_lists.count() == 0
    build_lists.create(BuildList(name="One", user_id=uuid4()))
    build_lists.create(BuildList(name="Two", user_id=uuid4()))
    assert build_lists.count() == 2
